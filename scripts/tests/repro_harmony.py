import asyncio
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.int.poshub_service import pos_service
from src.text_agent import tools as t
from src.int.meal_deal_intent import (
    should_merge_pizza_categories_for_listing,
    should_merge_all_meal_deal_categories,
    build_combined_pizza_option_list,
    build_combined_all_meal_deals_option_list
)

async def warmup():
    await pos_service.warmup()

def test_repro_issue_3_add_intent_lost():
    """
    Scenario: User says 'add a donner pizza'. 
    Then selects 'donner pizza' from the list.
    The 'add' intent should be preserved even though the last message is just 'donner pizza'.
    """
    # Simulate first turn: "add a donner pizza"
    # (In real life, LLM might call quote_order with name="Donner Pizza")
    old_cart = '[{"name": "Meal Deal 3", "qty": 1, "mods": []}, {"name": "Donner Pizza", "qty": 1, "mods": ["10\\"", "Standard Base", "Standard Crust"]}]'
    
    # Simulate second turn: User selects "donner pizza" (or "1")
    # session_metadata['_last_inbound_sms'] = "donner pizza"
    metadata = {
        "_last_inbound_sms": "donner pizza"
    }
    
    new_cart = '[{"name": "Donner Pizza", "qty": 1, "mods": []}]'
    
    # Currently, this will likely NOT increment quantity because it doesn't see "add" in the last message
    merged = t._merge_cart_with_previous(old_cart, new_cart, metadata)
    data = json.loads(merged)
    
    # We WANT 2x Donner Pizza (or two separate lines if the logic dictates)
    # But current logic (max(1, 1)) will keep it at 1x if it doesn't see 'add'
    donner_qty = sum(x.get("qty", 1) for x in data if x.get("name") == "Donner Pizza")
    
    print(f"DEBUG: Donner Qty: {donner_qty}")
    # EXPECTED: 2 (Failure if 1)
    # assert donner_qty == 2 

def test_repro_issue_2_md3_parmo_duplicate():
    """
    Scenario: Meal Deal 3 with 2 Parmo slots.
    Ensure that selecting the same Parmo twice doesn't get dropped.
    """
    asyncio.run(warmup())
    
    # MD3 product (mock or real)
    # We need to simulate the state where one parmo is picker
    # and we select the same one for second slot.
    
    # This is harder to test without full deal state, but we can test the normalizer
    from src.int.poshub_service import _deal_normalize_excess_slot_selections
    
    # Mock a real product that has 2 parmo slots
    p_md3 = pos_service.product_by_display_name("Meal Deal 3")
    if not p_md3:
        print("Meal Deal 3 not found in menu index")
        return

    item = {
        "name": "Meal Deal 3",
        "options": [
            {"name": "Half Explosive Parmo & Chips", "menuModifierGroupId": "parmo_group"},
            {"name": "Half Explosive Parmo & Chips", "menuModifierGroupId": "parmo_group"}
        ]
    }
    
    # Current logic might drop the second one because it's a "duplicate" in the same group
    _deal_normalize_excess_slot_selections(item, p_md3)
    
    parmo_count = len(item["options"])
    print(f"DEBUG: Parmo Count: {parmo_count}")
    # EXPECTED: 2 (Failure if 1)
    # assert parmo_count == 2

def test_repro_issue_1_robust_categories():
    """
    Verify that current category merging is keyword-based and could be better.
    """
    asyncio.run(warmup())
    
    # If we have a category "Stone Baked Specialities" that contains pizzas but not the word "pizza"
    # it would not be merged currently.
    
    # Mock check:
    res = should_merge_pizza_categories_for_listing(pos_service, "Stone Baked Specialities")
    print(f"DEBUG: Should merge 'Stone Baked Specialities' as pizza: {res}")
    # Currently False (would be True if robust)

if __name__ == "__main__":
    print("Running Repro Tests...")
    test_repro_issue_3_add_intent_lost()
    test_repro_issue_2_md3_parmo_duplicate()
    test_repro_issue_1_robust_categories()
