"""
Place a test order through the same path as SMS cash submit:
  cart JSON → agent._parse_order_text → pos_service.calculate_order_totals
  → sanitize_payload → create_order

Default cart matches the session that produced Order #5049 (Faraz / +447700900001 flow).

Usage (repo root):
  python scripts/place_order_via_agent_parse.py --dry-run
  python scripts/place_order_via_agent_parse.py
  python scripts/place_order_via_agent_parse.py --cart-file path/to/cart.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

# Same cart shape as quote_order / submit_order (from successful session logs).
DEFAULT_CART = [
    {
        "name": "Cheese And Tomato Garlic Bread",
        "qty": 1,
        "mods": ['12"', "Standard Crust"],
    },
    {
        "name": "Original Parmo",
        "qty": 1,
        "mods": ["X Large", "Salad"],
    },
    {
        "name": "Explosive Parmo & Chips",
        "qty": 1,
        "mods": ["Half", "Salad"],
    },
    {
        "name": "Meal Deal 3",
        "qty": 1,
        "mods": [
            '16" Prosciutto Funghi',
            '16" Captain Inferno',
            "Standard Base",
            "BBQ Base",
            "Standard Crust",
            "Stuffed Crust",
            "Half Explosive Parmo & Chips",
            "Half Donner Baked In Parmo & Chips",
            "Salad",
            "Salad",
            "Chilli Dip",
            "Chilli Dip",
            "Chilli Dip",
            "Garlic Dip",
            "Garlic Dip",
            "Garlic Dip",
            "2x Bottles Of Coke",
        ],
    },
]


def _get_iso_timestamps(delay_minutes: int = 20):
    now = datetime.now(timezone.utc)
    eta = now + timedelta(minutes=delay_minutes)
    fmt = "%Y-%m-%dT%H:%M:%S.%f"
    return now.strftime(fmt)[:-3] + "Z", eta.strftime(fmt)[:-3] + "Z"


def _build_charges_for_payload(pricing: dict, fulfillment_type: str) -> list:
    charges = []
    if (pricing.get("serviceCharge") or 0) > 0:
        charges.append(
            {
                "name": "SERVICE",
                "displayName": "Service",
                "amount": pricing["serviceCharge"],
            }
        )
    if fulfillment_type == "DELIVERY" and (pricing.get("deliveryFee") or 0) > 0:
        charges.append(
            {
                "name": "DELIVERY",
                "displayName": "Delivery Fee",
                "amount": pricing["deliveryFee"],
            }
        )
    return charges


async def _run(*, dry_run: bool, cart_path: Path | None) -> None:
    from src.agent import _parse_order_text
    from src.int.poshub_service import pos_service

    if cart_path:
        cart = json.loads(cart_path.read_text(encoding="utf-8"))
        if isinstance(cart, dict):
            cart = [cart]
    else:
        cart = list(DEFAULT_CART)

    items_str = json.dumps(cart)
    print("Cart lines:", len(cart))
    print("---")

    await pos_service.warmup()
    if not pos_service.is_ready:
        print("POS menu not ready after warmup.", file=sys.stderr)
        sys.exit(1)

    mapped_items, food_total, bill_lines, missing_items, dropped_mods = _parse_order_text(
        items_str
    )
    if missing_items:
        print("PARSE blocked — missing_items:", missing_items, file=sys.stderr)
        if dropped_mods:
            print("dropped_mods:", dropped_mods, file=sys.stderr)
        sys.exit(2)

    if dropped_mods:
        print("Note — dropped_mods (non-fatal):", dropped_mods)

    print("Bill lines:")
    for ln in bill_lines:
        print(" ", ln)
    print("food_total_pence", food_total)

    pricing = pos_service.calculate_order_totals(
        mapped_items,
        fulfillment_type="PICKUP",
        delivery_postcode=None,
    )
    grand_total = pricing["total"]
    print("calculate_order_totals total_pence", grand_total)

    placed_on, eta = _get_iso_timestamps(delay_minutes=20)
    draft_id = str(uuid.uuid4())
    simple_id = str(random.randint(9000, 9999))

    payload = {
        "sourceName": "DIRECT",
        "sourceDeviceType": "CHAT",
        "partnerId": f"ORD_{draft_id[:8].upper()}",
        "friendlyId": f"T-{simple_id}",
        "orderNumber": simple_id,
        "isPaid": False,
        "isScheduledOrder": False,
        "utensilsRequested": False,
        "notes": "scripts/place_order_via_agent_parse.py — agent parse path test",
        "placedOn": placed_on,
        "timezone": "Europe/London",
        "fulfillmentType": "PICKUP",
        "currency": "GBP",
        "subTotal": pricing["subTotal"],
        "totalTax": pricing["taxAmount"],
        "total": grand_total,
        "charges": _build_charges_for_payload(pricing, "PICKUP"),
        "discounts": [],
        "payments": [{"name": "CASH", "amount": grand_total}],
        "tax": (
            [
                {
                    "name": "VAT",
                    "displayName": "Tax",
                    "amount": pricing["taxAmount"],
                }
            ]
            if pricing["taxAmount"] > 0
            else []
        ),
        "customer": {
            "id": f"cust_{draft_id[:8]}",
            "firstName": "AgentParse",
            "phone": "+447700900099",
        },
        "items": mapped_items,
        "estimatedPickupTime": eta,
    }

    clean = pos_service.sanitize_payload(payload)

    if dry_run:
        print("--- DRY RUN: not calling create_order ---")
        print("subTotal", pricing["subTotal"], "total", grand_total)
        print("sanitized items[0] keys:", list(clean.get("items", [{}])[0].keys()))
        return

    api_response = await pos_service.create_order(clean)
    if api_response and not api_response.get("error"):
        oid = api_response.get("id") or api_response.get("orderId")
        print("OK create_order id:", oid)
        print("orderNumber", simple_id)
    else:
        print("create_order failed:", api_response, file=sys.stderr)
        sys.exit(3)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse + price only; do not POST to POSHub",
    )
    ap.add_argument(
        "--cart-file",
        type=Path,
        default=None,
        help="JSON array of {name, qty, mods} lines (overrides built-in #5049 cart)",
    )
    args = ap.parse_args()
    asyncio.run(_run(dry_run=args.dry_run, cart_path=args.cart_file))


if __name__ == "__main__":
    main()
