"""One-shot staging integration check for SMS recap, cart durability, and submit sync.

Run from repo root:
  .venv\\Scripts\\python.exe tests/repro_prompting_merge.py
"""

import asyncio
import json
import logging
import os
import random
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.int.poshub_service import pos_service
from src.text_agent.engine import _append_sms_cart_footer_if_needed
from src.text_agent.state import _sms_order_last_activity_at, normalize_sms_phone
from src.text_agent.tools import execute_tool


STRESS_CART = [
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
        "name": "500ml Bottles",
        "qty": 1,
        "mods": ["DR Pepper"],
    },
    {
        "name": "Meal Deal 3",
        "qty": 1,
        "mods": [
            '16" London',
            "BBQ Base",
            "Standard Crust",
            '16" Meat Lovers',
            "Standard Base",
            "Stuffed Crust",
            "Half Donner Baked In Parmo & Chips",
            "Salad",
            "Half Original Parmo & Chips",
            "No Salad",
            "Garlic Dip",
            "BBQ Dip",
            "Garlic Dip",
            "BBQ Dip",
            "Garlic Dip",
            "BBQ Dip",
            "2x Bottles Of Coke",
        ],
    },
]


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def run_single_staging_flow() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    await pos_service.warmup()

    suffix = random.randint(1000, 9999)
    phone = f"+4477009{suffix:04d}"
    norm_phone = normalize_sms_phone(phone)
    _sms_order_last_activity_at[norm_phone] = time.time()

    session_metadata = {
        "phone_number": phone,
        "phone": phone,
        "canonical_cart_json": "[]",
        "last_quoted_items": "[]",
    }

    print("STEP 1: Start order session")
    start_res = await execute_tool("start_order_session", "{}", session_metadata)
    _assert("ORDER_SESSION_STARTED" in start_res, f"start_order_session failed: {start_res}")

    print("STEP 2: Duplicate recap guard checks")
    footer_meta = {
        "last_quoted_items": json.dumps([{"name": "Meal Deal 3", "qty": 1, "mods": []}]),
        "last_quoted_bill_lines": ["1x Meal Deal 3 (GBP14.99)"],
        "last_quoted_food_total_pence": 1499,
    }
    t1 = "Your order so far:\n  - 1x Meal Deal 3\nWhat would you like next?"
    t2 = "Here is your current order:\n  - 1x Meal Deal 3\nAnything else?"
    t3 = "What would you like next?"
    _assert(
        _append_sms_cart_footer_if_needed(t1, footer_meta, session_active=True) == t1,
        "Footer dedupe failed for 'your order so far' wording.",
    )
    _assert(
        _append_sms_cart_footer_if_needed(t2, footer_meta, session_active=True) == t2,
        "Footer dedupe failed for 'current order' wording.",
    )
    t3_out = _append_sms_cart_footer_if_needed(t3, footer_meta, session_active=True)
    _assert(t3_out.startswith("---\nOrder so far:\n"), "Footer prepend missing when recap absent.")

    print("STEP 3: Quote full stress cart")
    session_metadata["_last_inbound_sms"] = "add these items"
    quote_res = await execute_tool(
        "quote_order",
        json.dumps({"items": json.dumps(STRESS_CART)}),
        session_metadata,
    )
    print("QUOTE RESULT:", quote_res[:500].replace("\n", " "))
    _assert(
        "ACTION REQUIRED" not in quote_res and "SYSTEM INSTRUCTION" not in quote_res,
        f"quote_order returned unfinished-choice gate: {quote_res[:900]}",
    )

    cart_json = session_metadata.get("canonical_cart_json") or "[]"
    cart = json.loads(cart_json)
    cart_names = {str(x.get("name", "")).strip().lower() for x in cart if isinstance(x, dict)}
    required_names = {
        "cheese and tomato garlic bread",
        "original parmo",
        "explosive parmo & chips",
        "500ml bottles",
        "meal deal 3",
    }
    missing_names = sorted(required_names - cart_names)
    _assert(not missing_names, f"Durability failure: cart missing lines after quote: {missing_names}")

    print("STEP 4: Record checkout details")
    session_metadata["_last_inbound_sms"] = "Shoraim"
    chk1 = await execute_tool(
        "record_checkout_details",
        json.dumps({"customer_name": "Shoraim"}),
        session_metadata,
    )
    _assert("CHECKOUT_RECORDED" in chk1, f"record_checkout_details(name) failed: {chk1}")

    session_metadata["_last_inbound_sms"] = "collection"
    chk2 = await execute_tool(
        "record_checkout_details",
        json.dumps({"delivery_type": "pickup"}),
        session_metadata,
    )
    _assert("CHECKOUT_RECORDED" in chk2, f"record_checkout_details(type) failed: {chk2}")

    print("STEP 5: Submit order to staging from the same cart")
    # Test cart is intentionally large; bypass collection cash cap for this staging durability run.
    old_cash_cap = os.environ.get("SMS_STAGING_SKIP_CASH_COLLECTION_LIMIT")
    os.environ["SMS_STAGING_SKIP_CASH_COLLECTION_LIMIT"] = "1"
    try:
        session_metadata["_last_inbound_sms"] = "cash"
        submit_res = await execute_tool(
            "submit_order",
            json.dumps(
                {
                    "items": "[]",
                    "customer_name": "Shoraim",
                    "delivery_type": "pickup",
                    "user_payment_response": "cash",
                    "postal_code": "N/A",
                    "house_number": "N/A",
                    "street_name": "N/A",
                }
            ),
            session_metadata,
        )
    finally:
        if old_cash_cap is None:
            os.environ.pop("SMS_STAGING_SKIP_CASH_COLLECTION_LIMIT", None)
        else:
            os.environ["SMS_STAGING_SKIP_CASH_COLLECTION_LIMIT"] = old_cash_cap

    print("SUBMIT RESULT:", submit_res[:1200])
    _assert(submit_res.startswith("SUCCESS:"), f"submit_order failed: {submit_res[:1200]}")

    for expected in (
        "Cheese And Tomato Garlic Bread",
        "Original Parmo",
        "Explosive Parmo & Chips",
        "500ml Bottles",
        "Meal Deal 3",
    ):
        _assert(expected in submit_res, f"Submit recap missing expected line: {expected}")

    m = re.search(r"Order\s+(\d+)", submit_res)
    order_no = m.group(1) if m else "UNKNOWN"
    print("PASS: Single-flow staging check completed.")
    print("ORDER NUMBER:", order_no)
    print("PHONE:", phone)
    print("CART LINES:", len(cart))


if __name__ == "__main__":
    asyncio.run(run_single_staging_flow())
