"""Merge duplicate Meal Deal rows from LLM (same SKU, split mods)."""
import asyncio
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.int.poshub_service import pos_service
from src.text_agent import tools as t
from src.int.poshub_service import (
    _deal_catchall_extra_names_lower,
    _deal_max_pizza_flavour_slots_cap_from_item_name,
    _deal_pizza_flavour_pick_count_for_upsell,
    _deal_should_defer_single_option_autofill,
)


async def _warmup():
    await pos_service.warmup()


def test_consolidate_consecutive_meal_deal_3_lines():
    """Same merge path as MD6 — any numbered meal deal / bundle name."""
    lines = [
        {"name": "Meal Deal 3", "qty": 1, "mods": ["Side A"]},
        {"name": "Meal Deal 3", "qty": 1, "mods": ["Pizza Pick", "Standard Base"]},
    ]
    out = t._consolidate_duplicate_meal_deal_lines(lines)
    assert len(out) == 1
    assert out[0]["name"] == "Meal Deal 3"
    assert "Side A" in out[0]["mods"]
    assert "Pizza Pick" in out[0]["mods"]


def test_is_pizza_menu_line_excludes_deal_structured_products():
    orig = pos_service.product_by_display_name
    try:
        pos_service.product_by_display_name = lambda _name: {
            "name": "Meal Deal 2",
            "categoryName": "Meal Deals",
            "printable_groups": [
                {"name": "Please select your pizza base"},
                {"name": "Please select your crust"},
            ],
        }
        assert not pos_service.is_pizza_menu_line("Meal Deal 2")
    finally:
        pos_service.product_by_display_name = orig


def test_non_deal_lines_not_merged():
    two_pepsi = [
        {"name": "1.5ltr Pepsi Max Bottle", "qty": 1, "mods": []},
        {"name": "1.5ltr Pepsi Max Bottle", "qty": 1, "mods": []},
    ]
    out = t._consolidate_duplicate_meal_deal_lines(two_pepsi)
    assert len(out) == 2


def test_catchall_extra_names_include_live_group_variants():
    product = {
        "printable_groups": [
            {
                "name": "Please select your first pizza",
                "options": [{"name": '16" London'}],
            },
            {
                "name": "Please select your items",
                "options": [{"name": "4x Chips"}, {"name": "Large Portion Of Donner Meat"}],
            },
            {
                "name": "Please select one of the following",
                "options": [{"name": "1x Wine Bottle"}],
            },
            {
                "name": "Please select the drink choice",
                "options": [{"name": "2x 500ml Bottle"}],
            },
            {
                "name": "Please select your wine",
                "options": [{"name": "Rose Wine"}],
            },
        ]
    }
    names = _deal_catchall_extra_names_lower(product)
    assert "4x chips" in names
    assert "large portion of donner meat" in names
    assert "1x wine bottle" in names
    assert "2x 500ml bottle" in names
    assert "rose wine" in names
    assert '16" london' not in names


def test_cap_incremental_deal_pizza_flavours_llm_spam():
    """One customer turn may add at most one new pizza-flavour line vs prior cart."""
    old = ['16" London', "BBQ Base", "Standard Crust"]
    new = [
        '16" London',
        "BBQ Base",
        "Standard Crust",
        '16" Prosciutto Funghi',
        "Standard Base",
        "Stuffed Crust",
        '16" Parmo',
        "BBQ Base",
        "Stuffed Crust",
    ]
    out = t._cap_incremental_deal_pizza_flavours(old, new)
    assert t._count_deal_pizza_flavour_mod_strings(out) == 2


def test_submultiset_deal_line_uses_incremental_pizza_cap():
    old_list = [{"name": "Meal Deal 6", "qty": 1, "mods": ['16" London', "BBQ Base"]}]
    new_list = [
        {
            "name": "Meal Deal 6",
            "qty": 1,
            "mods": [
                '16" London',
                "BBQ Base",
                '16" Prosciutto Funghi',
                '16" Parmo',
            ],
        }
    ]
    out = t._apply_submultiset_cart(old_list, new_list)
    assert len(out) == 1
    assert t._count_deal_pizza_flavour_mod_strings(out[0]["mods"]) == 2


def test_consolidate_consecutive_meal_deal_6_lines():
    lines = [
        {"name": "Meal Deal 6", "qty": 1, "mods": ["Large Portion Of Donner Meat", "4x Chips"]},
        {"name": "Meal Deal 6", "qty": 1, "mods": ['16" London', "Stuffed Crust"]},
    ]
    out = t._consolidate_duplicate_meal_deal_lines(lines)
    assert len(out) == 1
    assert out[0]["name"] == "Meal Deal 6"
    mods = out[0]["mods"]
    assert "16\" London" in mods
    assert "Stuffed Crust" in mods
    assert "Large Portion Of Donner Meat" in mods


def test_len_new_gt_old_reattaches_drinks_omitted_from_llm():
    """
    When new_list has more lines than old_list, merge must not return new_list alone
    (that dropped drinks). Re-attach preserved lines omitted from the longer JSON.
    """
    asyncio.run(_warmup())
    old = [
        {"name": "1.5ltr Pepsi Max Bottle", "qty": 3, "mods": []},
        {"name": "500ml Bottles", "qty": 2, "mods": ["Coke"]},
        {"name": "330ml Cans", "qty": 2, "mods": ["Coke Can"]},
    ]
    new = [
        {"name": "1.5ltr Pepsi Max Bottle", "qty": 3, "mods": []},
        {"name": "330ml Cans", "qty": 2, "mods": ["Coke Can"]},
        {"name": "330ml Cans", "qty": 5, "mods": ["Cherry Coke"]},
        {"name": "Meal Deal 6", "qty": 1, "mods": ['16" London', "Standard Base", "Stuffed Crust"]},
    ]
    assert len(new) > len(old)
    out = t._merge_cart_with_previous(json.dumps(old), json.dumps(new), None)
    data = json.loads(out)
    names_lower = [str(x.get("name", "")).strip().lower() for x in data]
    assert "500ml bottles" in names_lower
    assert any("meal deal 6" in n for n in names_lower)


def test_add_intent_duplicate_size_synonyms_increment_once():
    """
    LLM can emit both ["12\""] and ["Medium"] for one add-intent pizza.
    Treat that as one added item, not two.
    """
    asyncio.run(_warmup())
    old = [
        {
            "name": "Pepperoni Pizza",
            "qty": 1,
            "mods": ['12"', "Standard Base", "Standard Crust"],
        }
    ]
    new = [
        {"name": "Pepperoni Pizza", "qty": 1, "mods": ['12"']},
        {"name": "Pepperoni Pizza", "qty": 1, "mods": ["Medium"]},
    ]
    md = {
        "_last_inbound_sms": "add a medium pepperoni pizza",
        "_user_signaled_add_intent": True,
    }
    out = t._merge_cart_with_previous(json.dumps(old), json.dumps(new), md)
    data = json.loads(out)
    peps = [x for x in data if str(x.get("name", "")).strip().lower() == "pepperoni pizza"]
    assert len(peps) == 1
    assert int(peps[0].get("qty", 1) or 1) == 2


def test_add_intent_explicit_two_allows_two_increments():
    """
    If user explicitly asks for two items, do not collapse equivalent size-synonym rows.
    """
    asyncio.run(_warmup())
    old = [
        {
            "name": "Pepperoni Pizza",
            "qty": 1,
            "mods": ['12"', "Standard Base", "Standard Crust"],
        }
    ]
    new = [
        {"name": "Pepperoni Pizza", "qty": 1, "mods": ['12"']},
        {"name": "Pepperoni Pizza", "qty": 1, "mods": ["Medium"]},
    ]
    md = {
        "_last_inbound_sms": "add two medium pepperoni pizzas",
        "_user_signaled_add_intent": True,
    }
    out = t._merge_cart_with_previous(json.dumps(old), json.dumps(new), md)
    data = json.loads(out)
    peps = [x for x in data if str(x.get("name", "")).strip().lower() == "pepperoni pizza"]
    assert len(peps) == 1
    assert int(peps[0].get("qty", 1) or 1) == 3


def test_defer_single_option_false_when_opt_names_empty_but_options_have_pizza_lines():
    """
    Regression: _deal_pizza_flavour_pick_count_for_upsell used to return 0 when
    opt_names was empty, so defer never cleared and single-option rows (donner, chips)
    always prompted.
    """
    item = {
        "name": "Meal Deal 6",
        "options": [
            {"name": '16" Margherita'},
            {"name": "BBQ Base"},
            {"name": "Standard Crust"},
        ],
    }
    assert _deal_pizza_flavour_pick_count_for_upsell(item, []) >= 1


def test_defer_respects_meal_deal_slot_cap_when_group_count_inflated():
    """If POS duplicates pizza groups, cap total slots so tail single-options are not deferred forever."""
    groups = [{"name": f"slot {i}", "description": f"{i}th pizza"} for i in range(1, 12)]
    for g in groups:
        g["name"] = f"Please select your {g['name']} pizza"
        g["description"] = f"MD6 - {g['description']} type"
    item = {
        "name": "Meal Deal 6",
        "options": [{"name": f'16" P{i}'} for i in range(1, 6)],
    }
    assert _deal_max_pizza_flavour_slots_cap_from_item_name(item) == 5
    assert not _deal_should_defer_single_option_autofill(groups, item)


def test_incremental_meal_deal_keeps_prior_slots_when_llm_sends_flavour_first_tail():
    """
    Model often emits [P1,P2,P3, bases..., crusts...]; splice prior interleaved mods
    with tail starting at the newly added pizza line so agent reorder can zip slots.
    """
    old_line = {
        "name": "Meal Deal 6",
        "qty": 1,
        "mods": [
            '16" Margherita',
            "BBQ Base",
            "Standard Crust",
            '16" London',
            "Standard Base",
            "Stuffed Crust",
        ],
    }
    new_line = {
        "name": "Meal Deal 6",
        "qty": 1,
        "mods": [
            '16" Margherita',
            '16" London',
            '16" Prosciutto Funghi',
            "BBQ Base",
            "Standard Base",
            "Standard Crust",
            "Stuffed Crust",
        ],
    }
    out = t._merge_deal_line_with_previous(old_line, new_line)
    assert out["mods"][: len(old_line["mods"])] == old_line["mods"]
    assert any("Prosciutto" in str(m) for m in out["mods"])


def test_merge_cart_collapses_duplicate_meal_deal():
    prev = '[{"name":"Pepsi","qty":1,"mods":[]}]'
    new = (
        '[{"name":"Meal Deal 6","qty":1,"mods":["Chips"]},'
        '{"name":"Meal Deal 6","qty":1,"mods":["16\\" London","Standard Base"]}]'
    )
    merged = t._merge_cart_with_previous(prev, new, session_metadata=None)
    import json

    data = json.loads(merged)
    assert sum(1 for x in data if str(x.get("name", "")).strip().lower() == "meal deal 6") == 1


def test_meal_deal_append_guard_skips_parmo_phase_even_if_shape_matches_delta():
    """
    Non-pizza phases (e.g. 16" Parmo) should not trigger old+new append, even when
    length/prefix checks resemble a pizza-slot delta.
    """
    old_line = {
        "name": "Meal Deal 3",
        "qty": 1,
        "mods": [
            '16" Margherita',
            "BBQ Base",
            "Standard Crust",
            '16" London',
            "Standard Base",
            "Stuffed Crust",
        ],
    }
    new_line = {
        "name": "Meal Deal 3",
        "qty": 1,
        "mods": ['16" Parmo', "BBQ Base"],
    }
    assert not t._meal_deal_should_append_mods(old_line, new_line)


def test_merge_deal_line_with_parmo_phase_does_not_duplicate_old_history():
    old_line = {
        "name": "Meal Deal 3",
        "qty": 1,
        "mods": [
            '16" Margherita',
            "BBQ Base",
            "Standard Crust",
            '16" London',
            "Standard Base",
            "Stuffed Crust",
        ],
    }
    new_line = {
        "name": "Meal Deal 3",
        "qty": 1,
        "mods": ['16" Parmo', "BBQ Base"],
    }
    out = t._merge_deal_line_with_previous(old_line, new_line)
    assert out["mods"] == ['16" Parmo', "BBQ Base"]
    assert out["mods"].count('16" Parmo') == 1
