"""
Place a test order on POSHub staging/prod using the same payload shape as cash checkout
(sanitize_payload), without importing or changing the voice/text agent flow.

Usage (from repo root):
  .venv\\Scripts\\python.exe scripts\\poshub_place_test_order.py
  .venv\\Scripts\\python.exe scripts\\poshub_place_test_order.py --mode varied
  .venv\\Scripts\\python.exe scripts\\poshub_place_test_order.py --sku "Meal Deal 1" --mode dual-pepperoni
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

import httpx  # noqa: E402

from src.int.poshub_service import POSHubService  # noqa: E402


async def _fetch_paginated(
    client: httpx.AsyncClient, url: str, headers: dict
) -> list:
    out: list = []
    next_key = None
    while True:
        params: dict = {"limit": 50}
        if next_key:
            params["nextPageKey"] = next_key
        resp = await client.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        out.extend(data.get("data", []))
        if not data.get("hasNextPage"):
            break
        next_key = data.get("nextPageKey")
    return out


def _modifier_id(mlink: dict) -> str | None:
    mid = mlink.get("menuModifierId") or mlink.get("catalogModifierId")
    return str(mid) if mid else None


def _option_dict(
    mlink: dict,
    mod_by_id: dict,
    gid: str,
    gname: str,
) -> dict:
    pick = _modifier_id(mlink)
    m = mod_by_id.get(pick or "", {})
    price = POSHubService.modifier_link_price_pence(mlink, m)
    return {
        "name": m.get("name", ""),
        "price": price,
        "quantity": 1,
        "partnerId": pick,
        "menuModifierGroupId": gid,
        "modifierGroupName": gname,
    }


def _build_options_meal_deal_3(
    item: dict,
    gid_to_name: dict,
    mod_by_id: dict,
    mode: str,
) -> list[dict]:
    """
    mode 'first': first modifier in every required group (min>0); dip x6 same first dip.
    mode 'varied': first pizza = mods[0], second pizza = mods[1] if present; dip = rotate 6 across modifiers.
    """
    options: list[dict] = []
    pizza_slots: list[tuple[int, str]] = []  # (selection_index, role) for first/second pizza groups

    for si, sel in enumerate(item.get("selections") or []):
        gid = str(sel.get("menuModifierGroupId") or sel.get("catalogModifierGroupId") or "")
        min_q = sel.get("minPermitted")
        if min_q is None:
            min_q = 0
        max_q = sel.get("maxPermitted")
        gname = gid_to_name.get(gid, "?")
        if min_q == 0:
            continue
        mods_links = sel.get("modifiers") or []
        if not mods_links:
            continue

        gnl = gname.lower()
        if "first pizza" in gnl:
            pizza_slots.append((si, "first"))
        elif "second pizza" in gnl:
            pizza_slots.append((si, "second"))

        if min_q == 6 and max_q == 6:
            if mode == "varied" and len(mods_links) > 1:
                for j in range(6):
                    mlink = mods_links[j % len(mods_links)]
                    options.append(_option_dict(mlink, mod_by_id, gid, gname))
            else:
                mlink0 = mods_links[0]
                m = mod_by_id.get(_modifier_id(mlink0) or "", {})
                price = POSHubService.modifier_link_price_pence(mlink0, m)
                pick = _modifier_id(mlink0)
                for _ in range(6):
                    options.append(
                        {
                            "name": m.get("name", "Dip"),
                            "price": price,
                            "quantity": 1,
                            "partnerId": pick,
                            "menuModifierGroupId": gid,
                            "modifierGroupName": gname,
                        }
                    )
            continue

        if mode == "varied" and len(pizza_slots) >= 2:
            first_si, _ = pizza_slots[0]
            second_si, _ = pizza_slots[1]
            if si == first_si:
                mlink = mods_links[0]
            elif si == second_si:
                mlink = mods_links[1] if len(mods_links) > 1 else mods_links[0]
            else:
                mlink = mods_links[0]
        else:
            mlink = mods_links[0]
        options.append(_option_dict(mlink, mod_by_id, gid, gname))

    return options


def _build_meal_deal_1_dual_pepperoni(
    item: dict,
    gid_to_name: dict,
    mod_by_id: dict,
) -> list[dict]:
    """
    Required groups: first modifier on each link (matches menu flow).
    First two optional extra-topping groups: Pepperoni on each — link prices differ (e.g. 99p vs 120p).
    Dips (min 2): two of the first dip.
    """
    options: list[dict] = []
    et_pepperoni_slot = 0
    for sel in item.get("selections") or []:
        gid = str(sel.get("menuModifierGroupId") or sel.get("catalogModifierGroupId") or "")
        min_q = sel.get("minPermitted")
        if min_q is None:
            min_q = 0
        max_q = sel.get("maxPermitted")
        gname = gid_to_name.get(gid, "?")
        mods_links = sel.get("modifiers") or []
        if not mods_links:
            continue

        if min_q == 0:
            pepperoni_links = [
                m
                for m in mods_links
                if (mod_by_id.get(_modifier_id(m) or "", {}).get("name") or "").strip().lower()
                == "pepperoni"
            ]
            if pepperoni_links and et_pepperoni_slot < 2:
                options.append(_option_dict(pepperoni_links[0], mod_by_id, gid, gname))
                et_pepperoni_slot += 1
            continue

        if min_q == 2 and max_q == 2:
            mlink0 = mods_links[0]
            for _ in range(2):
                options.append(_option_dict(mlink0, mod_by_id, gid, gname))
            continue

        mlink0 = mods_links[0]
        options.append(_option_dict(mlink0, mod_by_id, gid, gname))

    return options


async def _run(mode: str, notes: str, sku_name: str) -> None:
    base = os.environ.get("POSHUB_BASE_URL", "").rstrip("/")
    token_url = os.environ.get("POSHUB_AUTH_URL", "")
    acc = os.environ["POSHUB_ACCOUNT_ID"]
    loc = os.environ["POSHUB_LOCATION_ID"]
    menu = os.environ["POSHUB_MENU_ID"]
    cid = os.environ["POSHUB_CLIENT_ID"]
    csec = os.environ["POSHUB_CLIENT_SECRET"]

    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            token_url,
            json={
                "grant_type": "client_credentials",
                "client_id": cid,
                "client_secret": csec,
                "scope": "menus.read orders.read orders.write locations.read",
            },
        )
        r.raise_for_status()
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        items = await _fetch_paginated(
            client,
            f"{base}/v1/accounts/{acc}/locations/{loc}/menus/{menu}/items",
            headers,
        )
        want = sku_name.strip().lower()
        item = None
        for it in items:
            if (it.get("name") or "").strip().lower() == want:
                item = it
                break
        if not item:
            print(f"Item {sku_name!r} not found in menu", file=sys.stderr)
            sys.exit(1)

        groups = await _fetch_paginated(
            client,
            f"{base}/v1/accounts/{acc}/locations/{loc}/menus/{menu}/modifier-groups",
            headers,
        )
        gid_to_name = {str(g.get("id")): g.get("name", "") for g in groups}

        mods = await _fetch_paginated(
            client,
            f"{base}/v1/accounts/{acc}/locations/{loc}/menus/{menu}/modifiers",
            headers,
        )
        mod_by_id = {str(m.get("id")): m for m in mods}

        if want == "meal deal 1" and mode == "dual-pepperoni":
            options = _build_meal_deal_1_dual_pepperoni(item, gid_to_name, mod_by_id)
        elif want == "meal deal 3":
            options = _build_options_meal_deal_3(item, gid_to_name, mod_by_id, mode=mode)
        else:
            print(
                "Use --sku 'Meal Deal 3' with --mode first|varied, "
                "or --sku 'Meal Deal 1' with --mode dual-pepperoni",
                file=sys.stderr,
            )
            sys.exit(2)

        cat_id = (item.get("categories") or [None])[0]
        line = {
            "name": item.get("name"),
            "quantity": 1,
            "price": int(item.get("price", 0)),
            "partnerId": str(item.get("id")),
            "parentPosReference": str(cat_id) if cat_id else "",
            "taxRateIds": [],
            "options": options,
            "customerNotes": "",
            "containsAlcohol": False,
        }

        sub = int(item.get("price", 0)) + sum(int(o.get("price", 0)) for o in options)
        placed = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        )

        payload = {
            "sourceName": "DIRECT",
            "sourceDeviceType": "VOICE",
            "partnerId": f"TEST_{uuid.uuid4().hex[:12]}",
            "orderNumber": str(8000 + (hash(uuid.uuid4().hex) % 1999)),
            "isScheduledOrder": False,
            "placedOn": placed,
            "timezone": os.environ.get("RESTAURANT_TIMEZONE", "Europe/London"),
            "fulfillmentType": "PICKUP",
            "currency": "GBP",
            "subTotal": sub,
            "totalTax": 0,
            "total": sub,
            "utensilsRequested": False,
            "notes": notes,
            "charges": [],
            "discounts": [],
            "payments": [{"name": "CASH", "amount": sub}],
            "tax": [],
            "customer": {
                "id": f"cust_{uuid.uuid4().hex[:8]}",
                "firstName": "Test",
                "lastName": "Order",
                "email": os.environ.get("ORDER_CONTACT_EMAIL", "test@example.com"),
                "phone": "+447700900002",
            },
            "items": [line],
            "estimatedPickupTime": placed,
        }

        clean = POSHubService.sanitize_payload(payload)
        ep = f"{base}/v1/accounts/{acc}/locations/{loc}/orders"
        resp = await client.post(ep, json=clean, headers=headers, timeout=30.0)
        print("HTTP", resp.status_code)
        try:
            body = resp.json()
        except Exception:
            body = {"raw": resp.text[:2000]}
        if resp.status_code >= 400:
            print(json.dumps(body, indent=2)[:4000], file=sys.stderr)
            sys.exit(1)
        oid = resp.headers.get("X-Audit-Metadata-orderId") or (
            body.get("id") if isinstance(body, dict) else None
        )
        print("order_id", oid)
        print("mode", mode, "options", len(options), "sub_pence", sub)
        print(
            "modifier_sample",
            [o.get("name") for o in options[:4]],
            "...",
            [o.get("name") for o in options[-4:]],
        )
        pep_prices = [
            o.get("price")
            for o in options
            if (o.get("name") or "").strip().lower() == "pepperoni"
        ]
        if pep_prices:
            print("pepperoni_option_prices_pence", pep_prices, "sum", sum(pep_prices))


def main() -> None:
    p = argparse.ArgumentParser(description="POSHub test order (does not use agent flow)")
    p.add_argument(
        "--sku",
        default="Meal Deal 3",
        help="Exact menu item name (e.g. Meal Deal 3, Meal Deal 1)",
    )
    p.add_argument(
        "--mode",
        choices=("first", "varied", "dual-pepperoni"),
        default="varied",
        help="Meal Deal 3: first | varied. Meal Deal 1: dual-pepperoni (two ET slots, Pepperoni 99p+120p).",
    )
    p.add_argument(
        "--note",
        default="Script test order (scripts/poshub_place_test_order.py) — agent flow unchanged.",
        help="Order notes field",
    )
    args = p.parse_args()
    asyncio.run(_run(args.mode, args.note, args.sku))


if __name__ == "__main__":
    main()
