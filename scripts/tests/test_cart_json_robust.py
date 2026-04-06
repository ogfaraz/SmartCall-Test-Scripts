"""Smoke tests for LLM cart JSON repair (inch quotes, merge path). Run from repo root:
    .venv\\Scripts\\python.exe tests/test_cart_json_robust.py
"""
import json
import asyncio
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.agent import (
    build_bill_lines_from_mapped_items,
    _inbound_requests_standalone_garlic_dip,
    _collapse_extra_middle_pizza_flavour_mod,
    _deal_remap_bare_chips_to_included_qty_line,
    _drink_container_suffix_alias,
    _printable_row_max_for_match,
    _try_match_modifier_printable_group_scoped,
    _upgrade_bare_chips_to_qty_sku,
    _classify_deal_mod_string,
    _consolidate_pepsi_bottle_cart_lines,
    _deal_collapse_slot_bases,
    _deal_collapse_slot_crusts,
    _deal_modifier_misclassified_side_phrase,
    _dedupe_identical_cart_lines,
    _is_drink_intent_phrase,
    _meal_deal_max_pizza_slots,
    _reorder_deal_string_mods_for_matching,
    _resolve_soft_drink_single_bottle_sku,
    _trim_excess_meal_deal_pizza_mod_strings,
    parse_cart_json_robust,
    sanitize_llm_cart_json,
)












from src.order_flow import (
    build_quote_success_response,
    pending_opts_are_salad_binary,
    pending_opts_look_like_deal_dips,
)
from src.text_agent import tools as t
from src.text_agent import canonical_cart as cc
from src.text_agent.engine import (
    _append_sms_cart_footer_if_needed,
    _extract_explicit_item_quantity,
)
from src.text_agent.state import sms_start_order_session
from src.int.poshub_service import (
    _sel_mod_matches_group_option,
    _wrap_group_requires_sauce_selection,
)


def test_drink_intent_phrase_does_not_match_pepperoni():
    assert not _is_drink_intent_phrase("Pepperoni Pizza")
    assert _is_drink_intent_phrase("Dr Pepper")
    assert _is_drink_intent_phrase("add a bottle of coke")


def test_drink_container_suffix_alias_for_drinks():
    assert _drink_container_suffix_alias("dr pepper", "Dr. Pepper Can")
    assert _drink_container_suffix_alias("coke", "Coke Can")
    assert _drink_container_suffix_alias("pepsi max", "Pepsi Max Bottle")
    assert not _drink_container_suffix_alias("sauces", "Tomato Sauce")


def test_skip_dropped_mod_promotion_for_drink_flavour_terms():
    cart = [{"name": "330ml Cans", "qty": 2, "mods": []}]
    assert t._should_skip_dropped_mod_product_promotion(
        "dr pepper",
        cart,
        "add 2 cans of dr pepper",
    )
    assert t._should_skip_dropped_mod_product_promotion(
        "coke",
        cart,
        "coke",
    )
    assert not t._should_skip_dropped_mod_product_promotion(
        "pepperoni nduja tomato pasta",
        [{"name": "Al Funghi Pizza", "qty": 1, "mods": []}],
        "add pepperoni nduja tomato pasta",
    )


def test_broken_inch_in_mod_string():
    broken = '[{"name":"Tomato Garlic Bread","qty":1,"mods":["Medium (12")]}]'
    r = parse_cart_json_robust(broken)
    assert r is not None and isinstance(r, list), r
    assert r[0]["mods"][0] == "Medium (12 inch)"


def test_parse_simple_cart_merge_path():
    broken = '[{"name":"Tomato Garlic Bread","qty":1,"mods":["Medium (12")]}]'
    lines = t._parse_simple_cart(broken)
    assert len(lines) == 1
    assert lines[0]["mods"][0] == "Medium (12 inch)"


def test_sanitize_idempotent():
    s = '[{"name":"X","qty":1,"mods":["Large (16 inch)"]}]'
    assert sanitize_llm_cart_json(s) == sanitize_llm_cart_json(sanitize_llm_cart_json(s))


def test_dedupe_identical_cart_lines_merges_qty():
    dup = [
        {"name": "500ml Bottles", "qty": 2, "mods": ["Coke"]},
        {"name": "500ml Bottles", "qty": 2, "mods": ["Coke"]},
        {"name": "1.5ltr Pepsi Max Bottle", "qty": 3, "mods": []},
    ]
    out = _dedupe_identical_cart_lines(dup)
    assert len(out) == 2
    bottle = next(x for x in out if x["name"] == "500ml Bottles")
    assert bottle["qty"] == 4


def test_dedupe_merges_display_parenthetical_with_bare_parent_sku():
    dup = [
        {"name": "500ml Bottles (Coke)", "qty": 4, "mods": ["Coke"]},
        {"name": "500ml Bottles", "qty": 4, "mods": ["Coke"]},
    ]
    out = _dedupe_identical_cart_lines(dup)
    assert len(out) == 1
    assert out[0]["name"] == "500ml Bottles"
    assert out[0]["qty"] == 8


def test_soft_bottle_sku_pepsi_must_be_on_line_not_sms_context():
    """Tango / other lines must not inherit 'bottles of pepsi' from the rest of the message."""
    lookup = {"x": {"name": "1.5ltr Pepsi Max Bottle", "categoryName": "Drinks"}}
    assert (
        _resolve_soft_drink_single_bottle_sku(
            "330ml Cans (Tango)",
            lookup,
            container_context="2x 1.5ltr Pepsi Max Bottle 2x 500ml Bottles (Coke)",
        )
        is None
    )
    got = _resolve_soft_drink_single_bottle_sku(
        "Pepsi",
        lookup,
        container_context="add 3 bottles of pepsi",
    )
    assert got is not None and got.get("name") == "1.5ltr Pepsi Max Bottle"


def test_reorder_two_pizzas_then_one_base_one_crust_pairs_slots():
    """
    LLM often sends [P1, P2, base, crust]. Without this, both modifiers attach to P2.
    """
    pd = {
        "printable_groups": [
            {
                "name": "Please select your first pizza",
                "options": [
                    {"name": '16" London'},
                    {"name": '16" Prosciutto Funghi'},
                ],
            },
            {
                "name": "Choose base",
                "options": [{"name": "BBQ Base"}, {"name": "Standard Base"}],
            },
            {
                "name": "Choose crust",
                "options": [{"name": "Standard Crust"}, {"name": "Stuffed Crust"}],
            },
        ],
    }
    mods = ['16" London', '16" Prosciutto Funghi', "BBQ Base", "Stuffed Crust"]
    out = _reorder_deal_string_mods_for_matching(mods, pd)
    assert len(out) == 6
    assert "London" in out[0]
    assert "BBQ" in out[1]
    assert "Standard" in out[2] and "Crust" in out[2]
    assert "Prosciutto" in out[3]
    assert "Standard" in out[4] and "Base" in out[4]
    assert "Stuffed" in out[5]


def test_reorder_p_base_crust_p2_stuffed_moves_crust_to_second_pizza():
    """
    LLM often sends [P1, base, stuffed crust, P2]. Sequential parse would put Stuffed on P1.
    """
    pd = {
        "printable_groups": [
            {
                "name": "Please select your first pizza",
                "options": [
                    {"name": '16" London'},
                    {"name": '16" Prosciutto Funghi'},
                ],
            },
            {
                "name": "Choose base",
                "options": [{"name": "BBQ Base"}, {"name": "Standard Base"}],
            },
            {
                "name": "Choose crust",
                "options": [{"name": "Standard Crust"}, {"name": "Stuffed Crust"}],
            },
        ],
    }
    mods = ['16" London', "BBQ Base", "Stuffed Crust", '16" Prosciutto Funghi']
    out = _reorder_deal_string_mods_for_matching(mods, pd)
    assert len(out) == 6
    assert "London" in out[0]
    assert "BBQ" in out[1]
    assert "Standard" in out[2] and "Crust" in out[2]
    assert "Prosciutto" in out[3]
    assert "Standard" in out[4] and "Base" in out[4]
    assert "Stuffed" in out[5]


def test_reorder_p1_base_crust_then_p2_base_keeps_first_crust_on_p1():
    """
    Sequence [P1, base, stuffed crust, P2, BBQ base] means stuffed belongs to P1,
    while P2 has its own base and should get default crust.
    """
    pd = {
        "printable_groups": [
            {
                "name": "Please select your first pizza",
                "options": [
                    {"name": '12" Prosciutto Funghi'},
                    {"name": '12" Donner On Top'},
                ],
            },
            {
                "name": "Choose base",
                "options": [{"name": "BBQ Base"}, {"name": "Standard Base"}],
            },
            {
                "name": "Choose crust",
                "options": [{"name": "Standard Crust"}, {"name": "Stuffed Crust"}],
            },
        ],
    }
    mods = [
        '12" Prosciutto Funghi',
        "Standard Base",
        "Stuffed Crust",
        '12" Donner On Top',
        "BBQ Base",
    ]
    out = _reorder_deal_string_mods_for_matching(mods, pd)
    p2_idx = out.index('12" Donner On Top')
    stuffed_idx = out.index("Stuffed Crust")
    assert stuffed_idx < p2_idx


def test_pepsi_bottle_consolidate_does_not_drop_500ml_coke():
    """
    '3 bottles of pepsi' must not remove an unrelated 500ml Bottles (Coke) row.
    Previously the first 500ml line was mistaken for the spurious Pepsi split.
    """
    lookup = {"p1": {"name": "1.5ltr Pepsi Max Bottle", "categoryName": "Drinks"}}
    entries = [
        {"name": "500ml Bottles", "qty": 2, "mods": ["Coke"]},
        {"name": "330ml Cans", "qty": 2, "mods": ["Coke Can"]},
        {"name": "1.5ltr Pepsi Max Bottle", "qty": 3, "mods": []},
    ]
    out = _consolidate_pepsi_bottle_cart_lines(entries, "3 bottles of pepsi", lookup)
    assert len(out) == 3
    assert any(
        e["name"] == "500ml Bottles" and e["mods"] == ["Coke"] for e in out
    )
    pepsi = next(e for e in out if e["name"] == "1.5ltr Pepsi Max Bottle")
    assert pepsi["qty"] == 3


def test_double_quote_after_inch_digit_in_mod():
    # LLM duplicates closing quote: "10"" should become JSON string 10"
    broken = '[{"name":"Cheese And Tomato Garlic Bread","qty":1,"mods":["10""]}]'
    r = parse_cart_json_robust(broken)
    assert r is not None and isinstance(r, list), r
    assert r[0]["mods"][0] == '10"'


def test_multi_item_cart_inch_dup_quote_does_not_drop_other_lines():
    s = (
        '[{"name":"Parmo","qty":1,"mods":[]},'
        '{"name":"Cheese And Tomato Garlic Bread","qty":1,"mods":["10""]},'
        '{"name":"Meal Deal 3","qty":1,"mods":[]}]'
    )
    r = parse_cart_json_robust(s)
    assert r is not None and len(r) == 3, r
    assert r[0]["name"] == "Parmo"
    assert r[1]["mods"][0] == '10"'
    assert r[2]["name"] == "Meal Deal 3"


def test_multi_item_cart_missing_mods_close_bracket():
    # LLM omits ] so "mods":["..."] merges into next object — sanitize repairs.
    broken = (
        '[{"name":"Cheese Garlic Bread","qty":1,"mods":["Medium (12 inch)"},'
        '{"name":"Meal Deal 6","qty":1,"mods":[]}]'
    )
    r = parse_cart_json_robust(broken)
    assert r is not None and isinstance(r, list) and len(r) == 2, r
    assert r[0]["name"] == "Cheese Garlic Bread"
    assert r[0]["mods"] == ["Medium (12 inch)"]
    assert r[1]["name"] == "Meal Deal 6"


def test_deal_collapse_replaces_standard_base_crust():
    assert _deal_collapse_slot_bases(["Standard Base", "BBQ Base"]) == ["BBQ Base"]
    assert _deal_collapse_slot_crusts(["Standard Crust", "Stuffed Crust"]) == [
        "Stuffed Crust"
    ]
    assert _deal_collapse_slot_bases(["Standard Base"]) == ["Standard Base"]


def test_classify_bbq_sauce_as_deal_base():
    pn, pzn = frozenset(), frozenset()
    bn, cn = frozenset({"bbq base"}), frozenset()
    assert _classify_deal_mod_string("BBQ Sauce", pn, pzn, bn, cn) == "base"


def test_classify_parmo_distinct_from_pizza_slot():
    pizza = frozenset({"16\" margherita"})
    parmo = frozenset({"half original parmo & chips"})
    bn, cn = frozenset(), frozenset()
    assert (
        _classify_deal_mod_string(
            "Half Original Parmo & Chips", pizza, parmo, bn, cn
        )
        == "parmo"
    )


def test_deal_guard_garlic_bread_not_mapped_to_garlic_dip():
    assert _deal_modifier_misclassified_side_phrase("Garlic Bread", {"name": "Garlic Dip"})
    assert _deal_modifier_misclassified_side_phrase(
        "add a garlic bread", {"name": "Garlic Dip"}
    )
    assert not _deal_modifier_misclassified_side_phrase(
        "Garlic Dip", {"name": "Garlic Dip"}
    )
    assert not _deal_modifier_misclassified_side_phrase(
        "Cheese And Tomato Garlic Bread",
        {"name": "Cheese And Tomato Garlic Bread"},
    )


def test_inbound_requests_standalone_garlic_dip_detects_item_level_garlic():
    assert _inbound_requests_standalone_garlic_dip("add 4 garlics")
    assert _inbound_requests_standalone_garlic_dip("2 garlic dips")
    assert _inbound_requests_standalone_garlic_dip("garlic")
    assert not _inbound_requests_standalone_garlic_dip("add garlic bread")


def test_merge_multi_line_meal_deal_appends_second_pizza_slot():
    """LLM must not replace entire deal mods when user picks pizza 2 (multi-item cart)."""
    old = [
        {
            "name": "Meal Deal 3",
            "qty": 1,
            "mods": ['16" Parmo', "BBQ Base", "Standard Crust"],
        },
        {"name": "Margherita Pizza", "qty": 1, "mods": ['16"', "Standard Base", "Standard Crust"]},
    ]
    new = [
        {
            "name": "Meal Deal 3",
            "qty": 1,
            "mods": ['16" Veggie Delight', "Stuffed Crust"],
        },
        {"name": "Margherita Pizza", "qty": 1, "mods": ['16"', "Standard Base", "Standard Crust"]},
    ]
    out = t._merge_multi_line_authoritative(old, new)
    md = next(x for x in out if x.get("name") == "Meal Deal 3")
    assert len(md["mods"]) == 5, md["mods"]
    assert md["mods"][0] == '16" Parmo'
    assert "Veggie Delight" in md["mods"][3]


def test_printable_row_max_for_numbered_deal_slots_is_single_pick():
    assert _printable_row_max_for_match(
        {"name": 'MD6 - 4th 16" Pizza Type', "max": 0}
    ) == 1
    assert _printable_row_max_for_match(
        {"name": "Please select your second half parmo", "max": 0}
    ) == 1


def test_printable_row_max_for_numbered_side_slots_is_single_pick():
    assert _printable_row_max_for_match(
        {
            "name": "CN - Side2",
            "description": "Please select your 2nd side",
            "max": 0,
        }
    ) == 1
    assert _printable_row_max_for_match(
        {
            "name": "Please select your dips",
            "description": "Choose your dips",
            "max": 0,
        }
    ) == 999


def test_printable_row_max_for_compact_side_row_names_is_single_pick():
    assert _printable_row_max_for_match(
        {
            "name": "CN - Side1",
            "description": "",
            "max": 0,
        }
    ) == 1
    assert _printable_row_max_for_match(
        {
            "name": "CN - Side2",
            "description": "",
            "max": 0,
        }
    ) == 1


def test_group_scoped_match_avoids_reusing_completed_meal_deal_pizza_slots():
    """
    MD6 regression: when earlier pizza slot rows share the same option names,
    a new pizza flavour must bind to the next open slot, not overwrite slot 2/3.
    """
    product_data = {
        "printable_groups": [
            {
                "name": 'MD6 - 1st 16" Pizza Type',
                "max": 0,
                "options": [
                    {"name": '16" Bbq Chicken', "menuModifierId": "g1_p11"},
                    {"name": '16" Tandoori Chicken', "menuModifierId": "g1_p17"},
                ],
            },
            {
                "name": 'MD6 - 2nd 16" Pizza Type',
                "required_parent": "rp2",
                "max": 0,
                "options": [
                    {"name": '16" Tandoori Chicken', "menuModifierId": "g2_p17"},
                ],
            },
            {
                "name": 'MD6 - 3rd 16" Pizza Type',
                "required_parent": "rp3",
                "max": 0,
                "options": [
                    {"name": '16" Tandoori Chicken', "menuModifierId": "g3_p17"},
                ],
            },
            {
                "name": 'MD6 - 4th 16" Pizza Type',
                "required_parent": "rp4",
                "max": 0,
                "options": [
                    {"name": '16" Tandoori Chicken', "menuModifierId": "g4_p17"},
                ],
            },
        ]
    }
    # First three slots already filled; 4th parent id drifts/mismatches in some POS payloads.
    picks_per_slot = [1, 1, 1, 0]
    selected_mod_ids = {"rp2", "rp3"}

    mod_data, scoped_slot = _try_match_modifier_printable_group_scoped(
        '16" Tandoori Chicken',
        product_data,
        picks_per_slot,
        selected_mod_ids,
        min_score=80,
    )

    assert mod_data is not None
    assert scoped_slot == 3
    assert mod_data.get("menuModifierId") == "g4_p17"


def test_group_scoped_match_allows_side2_after_side1_when_parent_id_drifts():
    product_data = {
        "printable_groups": [
            {
                "name": "CN - Side1",
                "description": "Please select your 1st side",
                "max": 0,
                "options": [
                    {
                        "name": "Chips",
                        "menuModifierId": "s1_chips",
                        "menuModifierGroupId": "g_side",
                    }
                ],
            },
            {
                "name": "CN - Side2",
                "description": "Please select your 2nd side",
                "required_parent": "parent-does-not-match",
                "max": 0,
                "options": [
                    {
                        "name": "Chips",
                        "menuModifierId": "s2_chips",
                        "menuModifierGroupId": "g_side",
                    }
                ],
            },
        ]
    }
    picks_per_slot = [1, 0]
    selected_mod_ids: set[str] = set()

    mod_data, scoped_slot = _try_match_modifier_printable_group_scoped(
        "chips",
        product_data,
        picks_per_slot,
        selected_mod_ids,
        min_score=65,
    )

    assert mod_data is not None
    assert scoped_slot == 1
    assert mod_data.get("menuModifierId") == "s2_chips"


def test_sel_mod_matcher_does_not_cross_claim_duplicate_name_with_different_id():
    sel = {"name": "Chips", "partnerId": "side2_chips_id"}
    side1_ids = {"side1_chips_id", "side1_cheese_chips_id"}
    side_names = {"chips", "cheese and chips", "cheese, chips and garlic"}
    assert not _sel_mod_matches_group_option(sel, side1_ids, side_names)
    side2_ids = {"side2_chips_id", "side2_cheese_chips_id"}
    assert _sel_mod_matches_group_option(sel, side2_ids, side_names)


def test_group_scoped_prefers_slot_flavour_over_prior_topping_row():
    """
    Regression: flavour-like slot picks (e.g. 16" Tandoori Chicken) must bind to
    the next numbered pizza-type row, not an earlier topping row with similar text.
    """
    product_data = {
        "printable_groups": [
            {
                "name": 'MD6 - 1st 16" Pizza Type',
                "max": 0,
                "options": [
                    {"name": '16" Bbq Chicken', "menuModifierId": "s1"},
                ],
            },
            {
                "name": 'MD6 - 2nd 16" Pizza Type',
                "required_parent": "rp2",
                "max": 0,
                "options": [
                    {"name": '16" Naples Special', "menuModifierId": "s2"},
                ],
            },
            {
                "name": 'MD6 - 3rd 16" Pizza Type',
                "required_parent": "rp3",
                "max": 0,
                "options": [
                    {"name": '16" Donner Baked In', "menuModifierId": "s3"},
                ],
            },
            {
                "name": 'MD6 - 3rd 16" Pizza Extra Topping',
                "required_parent": "rp3",
                "max": 5,
                "options": [
                    {"name": "Tandoori Chicken", "menuModifierId": "t3"},
                ],
            },
            {
                "name": 'MD6 - 4th 16" Pizza Type',
                "required_parent": "rp4",
                "max": 0,
                "options": [
                    {"name": '16" Tandoori Chicken', "menuModifierId": "s4"},
                ],
            },
        ]
    }

    picks_per_slot = [1, 1, 1, 0, 0]
    selected_mod_ids = {"rp2", "rp3"}

    mod_data, scoped_slot = _try_match_modifier_printable_group_scoped(
        '16" Tandoori Chicken',
        product_data,
        picks_per_slot,
        selected_mod_ids,
        min_score=80,
    )

    assert mod_data is not None
    assert scoped_slot == 4
    assert mod_data.get("menuModifierId") == "s4"

    mod_data2, scoped_slot2 = _try_match_modifier_printable_group_scoped(
        "Tandoori Chicken",
        product_data,
        picks_per_slot,
        selected_mod_ids,
        min_score=80,
    )

    assert mod_data2 is not None
    assert scoped_slot2 == 4
    assert mod_data2.get("menuModifierId") == "s4"


def test_map_inbound_pending_size_synonyms():
    opts = ["Small", "Medium", "Large"]
    assert t._map_inbound_to_pending_option("2", opts) == "Medium"
    assert t._map_inbound_to_pending_option("#3", opts) == "Large"
    assert t._map_inbound_to_pending_option("the medium", opts) == "Medium"
    assert t._map_inbound_to_pending_option("twelve inch", opts) == "Medium"


def test_map_inbound_number_with_extras_meal_deal_pizza_list():
    opts = ['16" Margherita', '16" Al Funghi', '16" London']
    extras: list[str] = []
    assert (
        t._map_inbound_to_pending_option(
            "2 with BBQ base", opts, extra_mods_out=extras
        )
        == '16" Al Funghi'
    )
    assert extras == ["BBQ base"]
    extras2: list[str] = []
    assert (
        t._map_inbound_to_pending_option(
            "2 bbq base", opts, extra_mods_out=extras2
        )
        == '16" Al Funghi'
    )
    assert extras2 == ["bbq base"]


def test_pending_opts_are_salad_binary():
    assert pending_opts_are_salad_binary(["Salad", "No Salad"])
    assert not pending_opts_are_salad_binary(["Salad"])
    assert not pending_opts_are_salad_binary(["Salad", "No Salad", "Extra"])


def test_build_quote_success_response_handles_deal_flow_tagged_action_required():
    suggestion = (
        "[DEAL FLOW] ACTION REQUIRED: 'Feed The Fam' [DEAL CONTEXT: FF - 1st 12\" Pizza Type 1] is missing a required choice.\n"
        "SPEAK NOW: \"For your Feed The Fam, please choose your first pizza.\"\n"
        "Options (for matching customer's answer; list ONLY if user asks 'What are my options?' — otherwise just ask, do NOT add to mods proactively): "
        "12\" Margherita, 12\" Al Funghi, 12\" London"
    )
    mapped_items = [
        {
            "name": "Feed The Fam",
            "quantity": 1,
            "options": [],
        }
    ]
    msg, pending = build_quote_success_response(
        channel="text",
        mapped_items=mapped_items,
        bill_lines=["1x Feed The Fam (£29.99)"],
        food_total=2999,
        suggestion_instruction=suggestion,
        breakdown="1x Feed The Fam (£29.99)",
    )
    assert pending is not None
    assert pending.get("item") == "Feed The Fam"
    assert pending.get("options") == ['12" Margherita', '12" Al Funghi', '12" London']
    assert "COMPLETE CHOICES" in msg


def test_build_quote_success_response_recovers_options_from_speak_now_when_options_line_missing():
    suggestion = (
        "ACTION REQUIRED: 'Couples Night With 2x 500ml Soft Drinks' is missing a required choice.\n"
        "SPEAK NOW: \"For your Couples Night, please select the drink choice: "
        "1. 2x 500ml Bottle; 2. 1x Wine Bottle. Which would you like?\"\n"
        "RESUME RULE: call quote_order after the customer replies."
    )
    _msg, pending = build_quote_success_response(
        channel="text",
        mapped_items=[
            {
                "name": "Couples Night With 2x 500ml Soft Drinks",
                "quantity": 1,
                "options": [],
            }
        ],
        bill_lines=["1x Couples Night With 2x 500ml Soft Drinks (£26.99)"],
        food_total=2699,
        suggestion_instruction=suggestion,
        breakdown="1x Couples Night With 2x 500ml Soft Drinks (£26.99)",
    )
    assert pending is not None
    assert pending.get("item") == "Couples Night With 2x 500ml Soft Drinks"
    assert pending.get("options") == ["2x 500ml Bottle", "1x Wine Bottle"]
    assert pending.get("append_same_option_group") is not True


def test_build_quote_success_response_sets_append_for_second_side():
    class _PosStub:
        global_modifier_names = {
            "chips",
            "cheese and chips",
            "cheese, chips and garlic",
            "potato wedges",
            "mozzarella sticks",
        }

    suggestion = (
        "ACTION REQUIRED: 'Couples Night With Bottle Wine' is missing a required choice.\n"
        "SPEAK NOW: \"For your Couples Night With Bottle Wine, please select your 2nd side.\"\n"
        "Options (for matching customer's answer; list ONLY if user asks 'What are my options?' — otherwise just ask, do NOT add to mods proactively): "
        "Chips, Cheese And Chips, Cheese, Chips And Garlic, Potato Wedges, Mozzarella Sticks"
    )
    msg, pending = build_quote_success_response(
        channel="text",
        mapped_items=[{"name": "Couples Night With Bottle Wine", "quantity": 1, "options": []}],
        bill_lines=["1x Couples Night With Bottle Wine (£26.99)"],
        food_total=2699,
        suggestion_instruction=suggestion,
        breakdown="1x Couples Night With Bottle Wine (£26.99)",
        pos_service=_PosStub(),
    )
    assert pending is not None
    assert pending.get("append_same_option_group") is True
    assert pending.get("options") == [
        "Chips",
        "Cheese And Chips",
        "Cheese, Chips And Garlic",
        "Potato Wedges",
        "Mozzarella Sticks",
    ]
    assert "COMPLETE CHOICES" in msg


def test_build_quote_success_response_sets_append_for_third_pizza():
    suggestion = (
        "ACTION REQUIRED: 'Meal Deal 6' is missing a required choice.\n"
        "SPEAK NOW: \"For Meal Deal 6, please select your 3rd pizza.\"\n"
        "Options (for matching customer's answer; list ONLY if user asks 'What are my options?' — otherwise just ask, do NOT add to mods proactively): "
        "16\" Margherita, 16\" Pepperoni, 16\" Philly Cheesesteak"
    )
    msg, pending = build_quote_success_response(
        channel="text",
        mapped_items=[{"name": "Meal Deal 6", "quantity": 1, "options": []}],
        bill_lines=["1x Meal Deal 6 (£59.99)"],
        food_total=5999,
        suggestion_instruction=suggestion,
        breakdown="1x Meal Deal 6 (£59.99)",
    )
    assert pending is not None
    assert pending.get("append_same_option_group") is True
    assert pending.get("options") == [
        '16" Margherita',
        '16" Pepperoni',
        '16" Philly Cheesesteak',
    ]
    assert "COMPLETE CHOICES" in msg


def test_inject_pending_required_choice_second_dip_appends_not_replaces():
    md = {
        "_last_inbound_sms": "bbq dip",
        "pending_required_choice": {
            "item": "Couples Night With Bottle Wine",
            "options": ["Chilli Dip", "Garlic Dip", "BBQ Dip", "Ketchup", "No Dip"],
            "append_same_option_group": True,
        },
        "canonical_cart_json": json.dumps(
            [
                {
                    "name": "Couples Night With Bottle Wine",
                    "qty": 1,
                    "mods": ["12\" Parmo", "Garlic Dip"],
                }
            ]
        ),
        "last_quoted_items": "[]",
    }
    out = t._inject_inbound_pending_required_choice(
        '[{"name":"Couples Night With Bottle Wine","qty":1,"mods":["Garlic Dip"]}]',
        md,
    )
    parsed = json.loads(out)
    assert len(parsed) == 1
    mods = parsed[0].get("mods") or []
    assert "Garlic Dip" in mods
    assert "BBQ Dip" in mods


def test_inject_pending_required_choice_third_pizza_appends_not_replaces():
    pending_opts = ['16" Margherita', '16" Pepperoni', '16" Philly Cheesesteak']
    md = {
        "_last_inbound_sms": "3 with stuffed crust",
        "pending_required_choice": {
            "item": "Meal Deal 6",
            "options": pending_opts,
            "append_same_option_group": True,
        },
        "canonical_cart_json": json.dumps(
            [
                {
                    "name": "Meal Deal 6",
                    "qty": 1,
                    "mods": [
                        '16" Margherita',
                        "Standard Base",
                        "Standard Crust",
                        '16" Pepperoni',
                        "BBQ Base",
                        "Standard Crust",
                    ],
                }
            ]
        ),
        "last_quoted_items": "[]",
    }
    # Simulate common LLM partial rewrite while answering the 3rd pizza step.
    incoming = (
        '[{"name":"Meal Deal 6","qty":1,'
        '"mods":["16\\\" Margherita","16\\\" Philly Cheesesteak","stuffed crust",'
        '"Standard Base","Standard Crust","BBQ Base","Standard Crust"]}]'
    )
    out = t._inject_inbound_pending_required_choice(incoming, md)
    parsed = json.loads(out)
    assert len(parsed) == 1
    mods = parsed[0].get("mods") or []
    lower_mods = [str(m).strip().lower() for m in mods]
    assert '16" margherita' in lower_mods
    assert '16" pepperoni' in lower_mods
    assert '16" philly cheesesteak' in lower_mods
    assert sum(1 for m in lower_mods if m in {x.lower() for x in pending_opts}) >= 3


def test_inject_pending_required_choice_third_pizza_appends_without_flag():
    pending_opts = ['16" Margherita', '16" Pepperoni', '16" Philly Cheesesteak']
    md = {
        "_last_inbound_sms": "3 with stuffed crust",
        "pending_required_choice": {
            "item": "Meal Deal 6",
            "options": pending_opts,
            # Intentionally missing append_same_option_group to exercise fallback.
        },
        "canonical_cart_json": json.dumps(
            [
                {
                    "name": "Meal Deal 6",
                    "qty": 1,
                    "mods": [
                        '16" Margherita',
                        "Standard Base",
                        "Standard Crust",
                        '16" Pepperoni',
                        "BBQ Base",
                        "Standard Crust",
                    ],
                }
            ]
        ),
        "last_quoted_items": "[]",
    }
    incoming = (
        '[{"name":"Meal Deal 6","qty":1,'
        '"mods":["16\\\" Margherita","16\\\" Philly Cheesesteak","stuffed crust",'
        '"Standard Base","Standard Crust","BBQ Base","Standard Crust"]}]'
    )
    out = t._inject_inbound_pending_required_choice(incoming, md)
    parsed = json.loads(out)
    assert len(parsed) == 1
    mods = parsed[0].get("mods") or []
    lower_mods = [str(m).strip().lower() for m in mods]
    assert '16" margherita' in lower_mods
    assert '16" pepperoni' in lower_mods
    assert '16" philly cheesesteak' in lower_mods
    assert sum(1 for m in lower_mods if m in {x.lower() for x in pending_opts}) >= 3


def test_inject_pending_required_choice_unmatched_short_reply_preserves_previous_cart():
    prev = [
        {
            "name": "Couples Night With Bottle Wine",
            "qty": 1,
            "mods": [
                '12" Prosciutto Funghi',
                "Standard Base",
                "Stuffed Crust",
                '12" Donner On Top',
                "BBQ Base",
                "Standard Crust",
                "Mozzarella Sticks",
                "750ml Rose Wine Echo Falls",
            ],
        }
    ]
    md = {
        "_last_inbound_sms": "bbq",
        "pending_required_choice": {
            "item": "Couples Night With Bottle Wine",
            "options": [
                "Chips",
                "Cheese And Chips",
                "Cheese, Chips And Garlic",
                "Potato Wedges",
                "Mozzarella Sticks",
            ],
            "append_same_option_group": True,
        },
        "canonical_cart_json": json.dumps(prev),
        "last_quoted_items": "[]",
    }
    # Simulate an LLM-hallucinated rewrite that would incorrectly mutate deal mods.
    bad_items = json.dumps(
        [
            {
                "name": "Couples Night With Bottle Wine",
                "qty": 1,
                "mods": [
                    '12" Prosciutto Funghi',
                    "Standard Base",
                    "Stuffed Crust",
                    '12" Donner On Top',
                    "BBQ Base",
                    "Standard Crust",
                    "BBQ Base",
                ],
            }
        ]
    )
    out = t._inject_inbound_pending_required_choice(bad_items, md)
    assert json.loads(out) == prev


def test_remove_cart_lines_blocked_when_inbound_not_removal_intent():
    phone = "+447700959921"
    sms_start_order_session(phone)
    md = {
        "phone_number": phone,
        "_last_inbound_sms": "chips",
        "canonical_cart_json": json.dumps(
            [{"name": "Potato Wedges", "qty": 1, "mods": []}]
        ),
        "last_quoted_items": json.dumps(
            [{"name": "Potato Wedges", "qty": 1, "mods": []}]
        ),
    }
    out = asyncio.run(
        t.execute_tool(
            "remove_cart_lines",
            json.dumps({"name_substrings": "potato"}),
            md,
        )
    )
    assert out.startswith("CART_REMOVE_BLOCKED")
    assert "Potato Wedges" in (md.get("canonical_cart_json") or "")


def test_remove_cart_lines_allowed_when_explicit_remove_intent():
    phone = "+447700959922"
    sms_start_order_session(phone)
    md = {
        "phone_number": phone,
        "_last_inbound_sms": "remove potato wedges",
        "canonical_cart_json": json.dumps(
            [{"name": "Potato Wedges", "qty": 1, "mods": []}]
        ),
        "last_quoted_items": json.dumps(
            [{"name": "Potato Wedges", "qty": 1, "mods": []}]
        ),
    }
    out = asyncio.run(
        t.execute_tool(
            "remove_cart_lines",
            json.dumps({"name_substrings": "potato"}),
            md,
        )
    )
    assert out.startswith("CART_REMOVE")


def test_optional_upsell_turn_clears_stale_pending_required_state():
    phone = "+447700959923"
    sms_start_order_session(phone)
    md = {
        "phone_number": phone,
        "_last_inbound_sms": "chips",
        "pending_required_choice": {
            "item": "Couples Night With Bottle Wine",
            "options": ["Chilli Dip", "Garlic Dip", "BBQ Dip", "Ketchup", "No Dip"],
        },
        "pending_category_choice": {"categories": ["Side Dishes"], "prompt": "category_disambiguation"},
        "standard_optional_asked_keys": [],
    }

    orig_parse = t._parse_order_text
    orig_totals = t.pos_service.calculate_order_totals
    orig_ups = t.pos_service.get_upsell_suggestions
    orig_prompt = t.pos_service.get_specific_upsell_prompt
    try:
        t._parse_order_text = lambda items, _ctx=None: (
            [
                {
                    "name": "Chips",
                    "quantity": 1,
                    "options": [],
                }
            ],
            299,
            ["1x Chips (£2.99)"],
            [],
            [],
        )
        t.pos_service.calculate_order_totals = lambda _mapped, fulfillment_type="PICKUP": {"subTotal": 299}
        t.pos_service.get_upsell_suggestions = lambda _mapped, standard_optional_asked_keys=None: (
            "OPTIONAL UPSELL [GLOBAL]: 'Menu extras available.'"
        )
        t.pos_service.get_specific_upsell_prompt = lambda mapped_items=None: (
            "Would you like anything else from the menu?"
        )

        out = asyncio.run(
            t.execute_tool(
                "quote_order",
                json.dumps({"items": [{"name": "Chips", "qty": 1, "mods": []}], "postal_code": "TS"}),
                md,
            )
        )
        assert out.startswith("SUCCESS. Cart Total")
        assert (md.get("pending_required_choice") or {}).get("options") == []
        assert (md.get("pending_category_choice") or {}).get("categories") == []
    finally:
        t._parse_order_text = orig_parse
        t.pos_service.calculate_order_totals = orig_totals
        t.pos_service.get_upsell_suggestions = orig_ups
        t.pos_service.get_specific_upsell_prompt = orig_prompt


def test_merge_salad_binary_append_same_preserves_first_slot():
    """Second half-parmo salad must append Salad, not replace first slot No Salad."""
    opts = ["Salad", "No Salad"]
    existing = ["Half Explosive Parmo & Chips", "No Salad", "Half Parmo In A Bun & Chips"]
    out = t._merge_mods_with_pending_choice(
        existing, opts, "Salad", append_same_group=True
    )
    assert out == existing + ["Salad"]


def test_merge_salad_binary_fallback_when_two_half_parmos_one_salad_line():
    """If append_same_option_group was not set, still append second Salad/No Salad when two half parmos exist."""
    opts = ["Salad", "No Salad"]
    existing = ["Half Explosive Parmo & Chips", "No Salad", "Half Parmo In A Bun & Chips"]
    out = t._merge_mods_with_pending_choice(
        existing, opts, "Salad", append_same_group=False
    )
    assert out == existing + ["Salad"]


def test_merge_mods_repeated_slot_infers_append_without_flag():
    opts = ['16" Margherita', '16" Pepperoni', '16" Philly Cheesesteak']
    existing = [
        '16" Margherita',
        "Standard Base",
        "Standard Crust",
        '16" Pepperoni',
        "BBQ Base",
        "Standard Crust",
    ]
    out = t._merge_mods_with_pending_choice(
        existing,
        opts,
        '16" Philly Cheesesteak',
        append_same_group=False,
    )
    lower = [str(m).strip().lower() for m in out]
    assert '16" margherita' in lower
    assert '16" pepperoni' in lower
    assert '16" philly cheesesteak' in lower
    assert sum(1 for m in lower if m in {x.lower() for x in opts}) >= 3


def test_merge_mods_append_same_group_allows_same_option_duplicate():
    opts = ["Chips", "Cheese And Chips", "Potato Wedges"]
    out = t._merge_mods_with_pending_choice(
        ["Chips"],
        opts,
        "Chips",
        append_same_group=True,
    )
    assert out == ["Chips", "Chips"]


def test_meal_deal_max_pizza_slots_default_and_trim():
    """MD6: consecutive duplicate pizza flavours collapse; tail drops extras beyond cap 5."""
    pd = {
        "name": "Meal Deal 6",
        "printable_groups": [
            {
                "name": "MD6 - pizza type",
                "options": [{"name": '16" Margherita'}],
            },
        ],
    }
    assert _meal_deal_max_pizza_slots(pd) == 5
    # Six identical in a row → one slot; no tail trim
    mods = ['16" Margherita'] * 6 + ["BBQ Base"]
    out = _trim_excess_meal_deal_pizza_mod_strings(mods, pd)
    assert out == ['16" Margherita'] + ["BBQ Base"]
    # Six distinct flavours → drop last (tail trim)
    pd2 = {
        "name": "Meal Deal 6",
        "printable_groups": [
            {
                "name": "pizza pick",
                "options": [{"name": f'16" L{i}'} for i in range(6)],
            },
        ],
    }
    mods2 = [f'16" L{i}' for i in range(6)]
    out2 = _trim_excess_meal_deal_pizza_mod_strings(mods2, pd2)
    assert out2 == [f'16" L{i}' for i in range(5)]


def test_remove_meal_deal_n_is_not_full_cart_clear():
    """'remove meal deal 6' must strip one line, not wipe cart (see engine pre-merge)."""
    assert not t._inbound_signals_empty_cart("remove meal deal 6")
    assert "6" in t._rejected_meal_deal_numbers_from_inbound("remove meal deal 6")
    assert t._inbound_signals_empty_cart("remove everything")


def test_inject_pending_required_choice_preserves_other_lines_when_llm_sends_deal_only():
    """Pending inject must not replace last_quoted with LLM-only bundle line (drops drinks)."""
    md = {
        "pending_required_choice": {
            "item": "meal deal 6",
            "options": ['16" Margherita'],
        },
        "_last_inbound_sms": "1",
        "last_quoted_items": json.dumps(
            [
                {"name": "1.5ltr Pepsi Max Bottle", "qty": 2, "mods": []},
                {"name": "Meal Deal 6", "qty": 1, "mods": []},
            ]
        ),
    }
    items_str = '[{"name":"Meal Deal 6","qty":1,"mods":[]}]'
    out = t._inject_inbound_pending_required_choice(items_str, md)
    parsed = json.loads(out)
    assert len(parsed) == 2
    assert parsed[0]["name"] == "1.5ltr Pepsi Max Bottle"
    assert parsed[0]["qty"] == 2
    assert parsed[1]["name"] == "Meal Deal 6"
    assert parsed[1]["mods"] == ['16" Margherita']


def test_drop_cart_lines_that_duplicate_deal_mod_strings():
    cart = [
        {"name": "Meal Deal 6", "qty": 1, "mods": ["Large Portion Of Donner Meat", "Chilli Dip"]},
        {"name": "Large Portion Of Donner Meat", "qty": 1, "mods": []},
        {"name": "Extra Garlic Bread", "qty": 1, "mods": []},
    ]
    out = t._drop_cart_lines_that_duplicate_deal_mod_strings(cart)
    names = [x["name"] for x in out]
    assert "Large Portion Of Donner Meat" not in names
    assert "Extra Garlic Bread" in names
    assert any(x["name"] == "Meal Deal 6" for x in out)


def test_remove_lines_matches_name_plus_mods_bottles_of_coke():
    md = {
        "canonical_cart_json": json.dumps(
            [
                {"name": "Original Parmo", "qty": 1, "mods": ["Full"]},
                {
                    "name": "500ml Bottles",
                    "qty": 2,
                    "mods": ["Coke"],
                },
            ]
        ),
        "last_quoted_items": "[]",
    }
    out, n = cc.remove_lines_by_name_substrings(md, ["bottles of coke"])
    assert n == 1
    data = json.loads(out)
    assert len(data) == 1
    assert data[0]["name"] == "Original Parmo"


def test_extract_line_removal_targets_is_conservative_for_modifier_only_text():
    assert t._extract_line_removal_targets_from_inbound(
        {"_last_inbound_sms": "without salad"}
    ) == []
    assert t._extract_line_removal_targets_from_inbound(
        {"_last_inbound_sms": "remove tomato garlic"}
    ) == ["tomato garlic"]


def test_is_safe_auto_append_system_instruction_target_bread_defaults_only():
    orig_is_pizza = t.pos_service.is_pizza_menu_line
    orig_prod = t.pos_service.product_by_display_name
    orig_is_bread = t.pos_service._is_non_pizza_bread_side_product
    try:
        t.pos_service.is_pizza_menu_line = lambda _n: False
        t.pos_service.product_by_display_name = lambda _n: {
            "name": "Cheese And Tomato Garlic Bread",
            "categoryName": "Garlic Bread",
        }
        t.pos_service._is_non_pizza_bread_side_product = lambda _p, _i: True

        assert t._is_safe_auto_append_system_instruction_target(
            "Cheese And Tomato Garlic Bread",
            ["Standard Crust"],
        )
        assert not t._is_safe_auto_append_system_instruction_target(
            "Cheese And Tomato Garlic Bread",
            ["Stuffed Crust"],
        )

        t.pos_service.is_pizza_menu_line = lambda _n: True
        assert t._is_safe_auto_append_system_instruction_target(
            "Al Funghi Pizza",
            ["Standard Base"],
        )
    finally:
        t.pos_service.is_pizza_menu_line = orig_is_pizza
        t.pos_service.product_by_display_name = orig_prod
        t.pos_service._is_non_pizza_bread_side_product = orig_is_bread


def test_expand_dip_picks_for_remaining_six_two_types():
    exp = t._expand_dip_picks_for_remaining(["Chilli Dip", "Garlic Dip"], 6)
    assert len(exp) == 6
    assert exp.count("Chilli Dip") == 3
    assert exp.count("Garlic Dip") == 3


def test_pending_opts_look_like_deal_dips():
    assert pending_opts_look_like_deal_dips(
        ["Chilli Dip", "Garlic Dip", "BBQ Dip", "Ketchup", "No Dip"]
    )
    assert not pending_opts_look_like_deal_dips(["Small", "Medium", "Large"])


def test_collapse_middle_pizza_flavour_md3():
    """Remove stray middle pizza flavour when LLM emits one extra (cap+1)."""
    pd = {
        "name": "Meal Deal 3",
        "printable_groups": [
            {
                "name": 'MD3 - 1st 16" Pizza Type',
                "options": [
                    {"name": '16" Al Funghi'},
                    {"name": '16" Pollo'},
                    {"name": '16" Philly Cheesesteak'},
                ],
            },
        ],
    }
    mods = [
        '16" Al Funghi',
        "Standard Base",
        '16" Pollo',
        "BBQ Base",
        '16" Philly Cheesesteak',
    ]
    out = _collapse_extra_middle_pizza_flavour_mod(mods, pd)
    assert '16" Pollo' not in out
    assert sum(1 for m in out if '16"' in str(m)) == 2


def test_upgrade_bare_chips_to_4x_when_only_qty_option():
    allowed = {"4x Chips": {"id": "x"}, "Chips": {"id": "y"}}
    out = _upgrade_bare_chips_to_qty_sku(["Large Portion", "Chips"], allowed)
    assert "4x Chips" in out
    assert out[-1] == "4x Chips"


def test_merge_mods_repeat_dip_appends():
    opts = ["Chilli Dip", "Garlic Dip"]
    m = t._merge_mods_with_pending_choice(
        ["Chilli Dip"],
        opts,
        "Chilli Dip",
        append_same_group=True,
        repeat_same_option=True,
    )
    assert m == ["Chilli Dip", "Chilli Dip"]


def test_inbound_signals_show_cart_only():
    assert t._inbound_signals_show_cart_only("show my full cart")
    assert t._inbound_signals_show_cart_only("what's in my order")
    assert not t._inbound_signals_show_cart_only("remove bottles of coke")
    assert not t._inbound_signals_show_cart_only("add 2 dips")


def test_canonical_cart_refuses_accidental_shrink():
    md = {
        "canonical_cart_json": json.dumps(
            [
                {"name": "Meal Deal 6", "qty": 1, "mods": ["a"]},
                {"name": "500ml Bottles", "qty": 2, "mods": ["Coke"]},
            ]
        ),
        "last_quoted_items": json.dumps(
            [
                {"name": "Meal Deal 6", "qty": 1, "mods": ["a"]},
                {"name": "500ml Bottles", "qty": 2, "mods": ["Coke"]},
            ]
        ),
    }
    bad = json.dumps([{"name": "500ml Bottles", "qty": 2, "mods": ["Coke"]}])
    out = cc.commit_cart_after_successful_quote(md, bad, allow_shrink=False)
    assert cc.cart_line_count(out) == 2


def test_merge_cart_keeps_drinks_when_new_is_meal_deal_delta():
    prev = json.dumps(
        [
            {"name": "1.5ltr Pepsi Max Bottle", "qty": 2, "mods": []},
            {
                "name": "Meal Deal 6",
                "qty": 1,
                "mods": ['16" Margherita', "BBQ Base"],
            },
        ]
    )
    new = json.dumps(
        [
            {
                "name": "Meal Deal 6",
                "qty": 1,
                "mods": ['16" Margherita', "BBQ Base", "Standard Crust"],
            }
        ]
    )
    merged = t._merge_cart_with_previous(prev, new, None)
    ml = json.loads(merged)
    assert len(ml) == 2
    assert ml[0]["name"] == "1.5ltr Pepsi Max Bottle"


def test_merge_cart_remove_targeted_line_without_collapsing_full_cart():
    prev = json.dumps(
        [
            {
                "name": "Meal Deal 3",
                "qty": 1,
                "mods": ['16" Hawaiian', '16" Farmyard Special'],
            },
            {
                "name": "Al Funghi Pizza",
                "qty": 1,
                "mods": ['16"', "Standard Base", "Standard Crust"],
            },
            {"name": "500ml Bottles", "qty": 1, "mods": ["Coke"]},
            {"name": "330ml Cans", "qty": 2, "mods": ["Dr. Pepper Can"]},
            {"name": "330ml Cans", "qty": 4, "mods": ["Coke Can"]},
            {
                "name": "Tomato Garlic Bread",
                "qty": 2,
                "mods": ["Garlic Butter And Cheese Stuffed Crust"],
            },
            {"name": "Garlic Bread", "qty": 1, "mods": []},
        ]
    )
    new = json.dumps([{"name": "Garlic Bread", "qty": 1, "mods": []}])
    md = {"_last_inbound_sms": "remove tomato garlic"}

    out = t._merge_cart_with_previous(prev, new, md)
    parsed = json.loads(out)
    names = [str(x.get("name", "")).strip().lower() for x in parsed if isinstance(x, dict)]

    assert "tomato garlic bread" not in names
    assert "meal deal 3" in names
    assert "al funghi pizza" in names
    assert "500ml bottles" in names
    assert "garlic bread" in names
    assert len(parsed) == 6


def test_merge_cart_short_numeric_multiline_delta_keeps_unmentioned_mains():
    prev = json.dumps(
        [
            {
                "name": "Meal Deal 3",
                "qty": 1,
                "mods": ['16" Hawaiian', '16" Farmyard Special'],
            },
            {
                "name": "Al Funghi Pizza",
                "qty": 1,
                "mods": ['16"', "Standard Base", "Standard Crust"],
            },
            {"name": "500ml Bottles", "qty": 1, "mods": ["Coke"]},
            {"name": "330ml Cans", "qty": 2, "mods": ["Dr. Pepper Can"]},
            {"name": "330ml Cans", "qty": 4, "mods": ["Coke Can"]},
            {"name": "Garlic Bread", "qty": 1, "mods": ['12"', "Standard Crust"]},
        ]
    )
    new = json.dumps(
        [
            {"name": "Garlic Bread", "qty": 1, "mods": ['12"', "Standard Crust"]},
            {"name": "Portion Of Donner Meat", "qty": 1, "mods": []},
        ]
    )
    md = {"_last_inbound_sms": "3"}

    out = t._merge_cart_with_previous(prev, new, md)
    parsed = json.loads(out)
    names = [str(x.get("name", "")).strip().lower() for x in parsed if isinstance(x, dict)]

    assert "meal deal 3" in names
    assert "al funghi pizza" in names
    assert "portion of donner meat" in names
    assert "500ml bottles" in names
    assert names.count("garlic bread") == 1
    assert len(parsed) == 7


def test_inject_pending_category_numeric_choice_with_extras_uses_pending_index():
    """Pending category choice must map number + keep inline extras like 'with bbq base'."""
    orig = t._sku_list_for_pending_categories
    try:
        t._sku_list_for_pending_categories = lambda _cats: [
            "Alpha Pizza",
            "Bravo Pizza",
            "Charlie Pizza",
        ]
        md = {
            "pending_category_choice": {"categories": ["Pizzas"], "prompt": "category_disambiguation"},
            "_last_inbound_sms": "2 with BBQ base",
            "canonical_cart_json": "[]",
            "last_quoted_items": "[]",
        }
        out = t._inject_inbound_pending_category_numeric_choice(
            '[{"name":"Donner Pizza","qty":1,"mods":[]}]', md
        )
        parsed = json.loads(out)
        assert len(parsed) == 1
        assert parsed[0]["name"] == "Bravo Pizza"
        assert any(str(m).strip().lower() == "bbq base" for m in parsed[0].get("mods") or [])
        assert md.get("pending_category_choice", {}).get("categories") == []
    finally:
        t._sku_list_for_pending_categories = orig


def test_resolve_pending_category_option_from_inbound_side_dishes_context():
    orig = t._sku_list_for_pending_categories
    try:
        t._sku_list_for_pending_categories = lambda _cats: [
            "Cheese, Chips And Garlic",
            "Loaded Chips",
            "Chips",
        ]
        md = {
            "pending_category_choice": {
                "categories": ["Side Dishes"],
                "prompt": "category_disambiguation",
            }
        }
        assert (
            t._resolve_pending_category_option_from_inbound(
                "cheese chips and garlics",
                md,
            )
            == "Cheese, Chips And Garlic"
        )
        assert (
            t._resolve_pending_category_option_from_inbound(
                "loaded chips",
                md,
            )
            == "Loaded Chips"
        )
    finally:
        t._sku_list_for_pending_categories = orig


def test_resolve_pending_category_option_from_inbound_drinks_context():
    orig = t._sku_list_for_pending_categories
    try:
        t._sku_list_for_pending_categories = lambda _cats: [
            "Coke Can",
            "Dr. Pepper Can",
            "Fanta Can",
        ]
        md = {
            "pending_category_choice": {
                "categories": ["Drinks"],
                "prompt": "category_disambiguation",
            }
        }
        assert (
            t._resolve_pending_category_option_from_inbound(
                "dr pepper",
                md,
            )
            == "Dr. Pepper Can"
        )
    finally:
        t._sku_list_for_pending_categories = orig


def test_merge_cart_add_identical_item_increments_qty():
    prev = json.dumps(
        [
            {
                "name": "Donner Pizza",
                "qty": 1,
                "mods": ['16"', "Standard Base", "Standard Crust"],
            }
        ]
    )
    new = json.dumps(
        [
            {
                "name": "Donner Pizza",
                "qty": 1,
                "mods": ['16"', "Standard Base", "Standard Crust"],
            }
        ]
    )
    md = {"_last_inbound_sms": 'add a 16" donner pizza'}
    out = t._merge_cart_with_previous(prev, new, md)
    parsed = json.loads(out)
    assert len(parsed) == 1
    assert parsed[0]["name"] == "Donner Pizza"
    assert int(parsed[0].get("qty", 0)) == 2


def test_merge_cart_add_same_sku_different_size_keeps_both_lines():
    prev = json.dumps(
        [
            {
                "name": "Donner Pizza",
                "qty": 1,
                "mods": ['16"', "Standard Base", "Standard Crust"],
            }
        ]
    )
    new = json.dumps(
        [
            {
                "name": "Donner Pizza",
                "qty": 1,
                "mods": ['10"'],
            }
        ]
    )
    md = {"_last_inbound_sms": 'add 10" donner pizza'}
    out = t._merge_cart_with_previous(prev, new, md)
    parsed = json.loads(out)
    assert len(parsed) == 2
    mod_sets = [set(str(m) for m in (x.get("mods") or [])) for x in parsed]
    assert any('16"' in ms for ms in mod_sets)
    assert any('10"' in ms for ms in mod_sets)


def test_merge_cart_modifier_change_still_merges_structural_slots():
    prev = json.dumps(
        [
            {
                "name": "Donner Pizza",
                "qty": 1,
                "mods": ['16"', "Standard Base", "Standard Crust"],
            }
        ]
    )
    new = json.dumps(
        [
            {
                "name": "Donner Pizza",
                "qty": 1,
                "mods": ["BBQ Base"],
            }
        ]
    )
    md = {"_last_inbound_sms": "change the base to bbq"}
    out = t._merge_cart_with_previous(prev, new, md)
    parsed = json.loads(out)
    assert len(parsed) == 1
    mods = parsed[0].get("mods") or []
    assert "BBQ Base" in mods
    assert "Standard Crust" in mods


def test_merge_cart_multiline_add_same_pizza_keeps_new_placeholder_for_customization():
    prev = json.dumps(
        [
            {
                "name": "Hawaiian Pizza",
                "qty": 1,
                "mods": ['12"', "BBQ Base", "Standard Crust"],
            },
            {
                "name": "Donner Pizza",
                "qty": 1,
                "mods": ['16"', "Standard Base", "Standard Crust"],
            },
        ]
    )
    # LLM commonly echoes existing lines + a same-name placeholder for the new add.
    new = json.dumps(
        [
            {
                "name": "Hawaiian Pizza",
                "qty": 1,
                "mods": ['12"', "BBQ Base", "Standard Crust"],
            },
            {"name": "Donner Pizza", "qty": 1, "mods": []},
        ]
    )
    md = {"_last_inbound_sms": "add a donner pizza"}
    out = t._merge_cart_with_previous(prev, new, md)
    parsed = json.loads(out)
    hawaiian = [
        x for x in parsed if str(x.get("name", "")).strip().lower() == "hawaiian pizza"
    ]
    donner = [x for x in parsed if str(x.get("name", "")).strip().lower() == "donner pizza"]
    assert len(parsed) == 3
    assert len(hawaiian) == 1
    assert int(hawaiian[0].get("qty", 0)) == 1
    assert len(donner) == 2
    assert any(not (x.get("mods") or []) for x in donner)
    assert any(any('16"' in str(m) for m in (x.get("mods") or [])) for x in donner)


def test_merge_cart_multiline_add_same_pizza_same_as_before_increments_qty():
    prev = json.dumps(
        [
            {
                "name": "Hawaiian Pizza",
                "qty": 1,
                "mods": ['12"', "BBQ Base", "Standard Crust"],
            },
            {
                "name": "Donner Pizza",
                "qty": 1,
                "mods": ['16"', "Standard Base", "Standard Crust"],
            },
        ]
    )
    new = json.dumps(
        [
            {
                "name": "Hawaiian Pizza",
                "qty": 1,
                "mods": ['12"', "BBQ Base", "Standard Crust"],
            },
            {"name": "Donner Pizza", "qty": 1, "mods": []},
        ]
    )
    md = {"_last_inbound_sms": "add the same donner pizza as before"}
    out = t._merge_cart_with_previous(prev, new, md)
    parsed = json.loads(out)
    hawaiian = [
        x for x in parsed if str(x.get("name", "")).strip().lower() == "hawaiian pizza"
    ]
    donner = [x for x in parsed if str(x.get("name", "")).strip().lower() == "donner pizza"]
    assert len(parsed) == 2
    assert len(hawaiian) == 1
    assert int(hawaiian[0].get("qty", 0)) == 1
    assert len(donner) == 1
    assert int(donner[0].get("qty", 0)) == 2


def test_merge_cart_add_same_pizza_qty_bump_from_model_becomes_placeholder():
    """If model jumps to qty+1 with old mods, force a new configurable pizza line."""
    prev = json.dumps(
        [
            {
                "name": "Al Funghi Pizza",
                "qty": 1,
                "mods": ['12"', "Standard Base", "Standard Crust"],
            },
            {
                "name": "Pepperoni Pizza",
                "qty": 1,
                "mods": ['16"', "Standard Base", "Standard Crust"],
            },
        ]
    )
    new = json.dumps(
        [
            {
                "name": "Al Funghi Pizza",
                "qty": 2,
                "mods": ['12"', "Standard Base", "Standard Crust"],
            },
            {
                "name": "Pepperoni Pizza",
                "qty": 1,
                "mods": ['16"', "Standard Base", "Standard Crust"],
            },
        ]
    )
    md = {"_last_inbound_sms": "add an al funghi pizza"}
    out = t._merge_cart_with_previous(prev, new, md)
    parsed = json.loads(out)
    al_funghi = [
        x for x in parsed if str(x.get("name", "")).strip().lower() == "al funghi pizza"
    ]
    pepperoni = [
        x for x in parsed if str(x.get("name", "")).strip().lower() == "pepperoni pizza"
    ]
    assert len(al_funghi) == 2
    assert any(not (x.get("mods") or []) for x in al_funghi)
    assert any(any('12"' in str(m) for m in (x.get("mods") or [])) for x in al_funghi)
    assert len(pepperoni) == 1
    assert int(pepperoni[0].get("qty", 0)) == 1


def test_merge_cart_add_same_configured_non_pizza_keeps_placeholder():
    prev = json.dumps(
        [
            {
                "name": "500ml Bottles",
                "qty": 1,
                "mods": ["Coke"],
            },
            {
                "name": "Donner Pizza",
                "qty": 1,
                "mods": ['16"', "Standard Base", "Standard Crust"],
            },
        ]
    )
    new = json.dumps(
        [
            {
                "name": "500ml Bottles",
                "qty": 2,
                "mods": ["Coke"],
            },
            {
                "name": "Donner Pizza",
                "qty": 1,
                "mods": ['16"', "Standard Base", "Standard Crust"],
            },
        ]
    )
    md = {"_last_inbound_sms": "add a 500ml bottles"}
    out = t._merge_cart_with_previous(prev, new, md)
    parsed = json.loads(out)
    bottles = [x for x in parsed if str(x.get("name", "")).strip().lower() == "500ml bottles"]
    pizza = [x for x in parsed if str(x.get("name", "")).strip().lower() == "donner pizza"]
    assert len(bottles) == 2
    assert any((x.get("mods") or []) == ["Coke"] for x in bottles)
    assert any(not (x.get("mods") or []) for x in bottles)
    assert len(pizza) == 1 and int(pizza[0].get("qty", 0)) == 1


def test_merge_cart_add_same_configured_non_pizza_same_as_before_increments_qty():
    prev = json.dumps(
        [
            {
                "name": "500ml Bottles",
                "qty": 1,
                "mods": ["Coke"],
            }
        ]
    )
    new = json.dumps(
        [
            {
                "name": "500ml Bottles",
                "qty": 2,
                "mods": ["Coke"],
            }
        ]
    )
    md = {"_last_inbound_sms": "add the same 500ml bottles as before"}
    out = t._merge_cart_with_previous(prev, new, md)
    parsed = json.loads(out)
    bottles = [x for x in parsed if str(x.get("name", "")).strip().lower() == "500ml bottles"]
    assert len(bottles) == 1
    assert int(bottles[0].get("qty", 0)) == 2


def test_merge_cart_add_meal_deal_qty_bump_stays_compacted_line():
    """Meal deal merge path should remain compact; new generic add normalization must not split deals."""
    prev = json.dumps(
        [
            {
                "name": "Meal Deal 3",
                "qty": 1,
                "mods": ['16" Margherita', "BBQ Base", "Standard Crust"],
            }
        ]
    )
    new = json.dumps(
        [
            {
                "name": "Meal Deal 3",
                "qty": 2,
                "mods": ['16" Margherita', "BBQ Base", "Standard Crust"],
            }
        ]
    )
    md = {"_last_inbound_sms": "add meal deal 3"}
    out = t._merge_cart_with_previous(prev, new, md)
    parsed = json.loads(out)
    deals = [x for x in parsed if str(x.get("name", "")).strip().lower() == "meal deal 3"]
    assert len(deals) == 1
    assert int(deals[0].get("qty", 0)) == 2


def test_drop_deal_mod_duplicate_keeps_line_when_user_explicitly_adds_it():
    lines = [
        {
            "name": "Meal Deal 3",
            "qty": 1,
            "mods": ["Garlic Dip"],
        },
        {
            "name": "Garlic Dip",
            "qty": 1,
            "mods": [],
        },
    ]
    md = {"_last_inbound_sms": "add a garlic dip"}
    out = t._drop_cart_lines_that_duplicate_deal_mod_strings(lines, md)
    names = [str(x.get("name", "")).strip().lower() for x in out if isinstance(x, dict)]
    assert "meal deal 3" in names
    assert "garlic dip" in names


def test_merge_cart_preserves_explicit_add_on_even_if_name_matches_deal_mod():
    prev = json.dumps(
        [
            {
                "name": "Meal Deal 3",
                "qty": 1,
                "mods": ["Garlic Dip"],
            }
        ]
    )
    new = json.dumps(
        [
            {
                "name": "Meal Deal 3",
                "qty": 1,
                "mods": ["Garlic Dip"],
            },
            {
                "name": "Garlic Dip",
                "qty": 1,
                "mods": [],
            },
        ]
    )
    md = {"_last_inbound_sms": "add a garlic dip"}
    out = t._merge_cart_with_previous(prev, new, md)
    parsed = json.loads(out)
    names = [str(x.get("name", "")).strip().lower() for x in parsed if isinstance(x, dict)]
    assert "meal deal 3" in names
    assert "garlic dip" in names


def test_drop_deal_mod_duplicate_keeps_line_when_explicit_quantity_requested():
    lines = [
        {
            "name": "Meal Deal 3",
            "qty": 1,
            "mods": ["Chips"],
        },
        {
            "name": "Chips",
            "qty": 2,
            "mods": [],
        },
    ]
    md = {"_last_inbound_sms": "meal deal 3 and 2x chips"}
    out = t._drop_cart_lines_that_duplicate_deal_mod_strings(lines, md)
    chips = [x for x in out if str(x.get("name", "")).strip().lower() == "chips"]
    assert len(chips) == 1
    assert int(chips[0].get("qty", 0)) == 2


def test_merge_cart_preserves_explicit_quantity_add_on_when_name_collides_with_deal_mod():
    prev = json.dumps(
        [
            {
                "name": "Meal Deal 3",
                "qty": 1,
                "mods": ["Chips"],
            }
        ]
    )
    new = json.dumps(
        [
            {
                "name": "Meal Deal 3",
                "qty": 1,
                "mods": ["Chips"],
            },
            {
                "name": "Chips",
                "qty": 2,
                "mods": [],
            },
        ]
    )
    md = {"_last_inbound_sms": "meal deal 3 and 2x chips"}
    out = t._merge_cart_with_previous(prev, new, md)
    parsed = json.loads(out)
    chips = [x for x in parsed if str(x.get("name", "")).strip().lower() == "chips"]
    assert len(chips) == 1
    assert int(chips[0].get("qty", 0)) == 2


def test_merge_cart_add_non_deal_keeps_existing_meal_deal_line():
    prev = json.dumps(
        [
            {
                "name": "Meal Deal 2",
                "qty": 1,
                "mods": ['16" Parmo', "Standard Base", "Stuffed Crust", "2x Chips"],
            }
        ]
    )
    new = json.dumps(
        [
            {
                "name": "Donner Pizza",
                "qty": 1,
                "mods": ["Stuffed Crust"],
            }
        ]
    )
    md = {
        "_last_inbound_sms": "add a donner pizza with stuffed crust",
        "_user_signaled_add_intent": True,
    }
    out = t._merge_cart_with_previous(prev, new, md)
    parsed = json.loads(out)
    names = [str(x.get("name", "")).strip().lower() for x in parsed]
    assert "meal deal 2" in names
    assert "donner pizza" in names


def test_merge_cart_single_pizza_progression_does_not_double_qty():
    prev = json.dumps(
        [
            {
                "name": "Donner Pizza",
                "qty": 1,
                "mods": ["Stuffed Crust"],
            }
        ]
    )
    new = json.dumps(
        [
            {
                "name": "Donner Pizza",
                "qty": 1,
                "mods": ["Stuffed Crust", '12"'],
            }
        ]
    )
    md = {"_last_inbound_sms": "2"}
    out = t._merge_cart_with_previous(prev, new, md)
    parsed = json.loads(out)
    donner = [x for x in parsed if str(x.get("name", "")).strip().lower() == "donner pizza"]
    assert len(donner) == 1
    assert int(donner[0].get("qty", 0)) == 1


def test_deal_pizza_flavour_detector_ignores_structural_base_rows():
    assert t._first_mod_looks_like_deal_pizza_flavour_pick('16" Parmo')
    assert not t._first_mod_looks_like_deal_pizza_flavour_pick('12" BBQ Base')
    assert not t._first_mod_looks_like_deal_pizza_flavour_pick('16" Stuffed Crust')


def test_merge_cart_multiline_add_same_name_with_different_mods_keeps_separate_lines():
    prev = json.dumps(
        [
            {
                "name": "Hawaiian Pizza",
                "qty": 1,
                "mods": ['12"', "BBQ Base", "Standard Crust"],
            },
            {
                "name": "Donner Pizza",
                "qty": 1,
                "mods": ['16"', "Standard Base", "Standard Crust"],
            },
        ]
    )
    new = json.dumps(
        [
            {
                "name": "Hawaiian Pizza",
                "qty": 1,
                "mods": ['12"', "BBQ Base", "Standard Crust"],
            },
            {
                "name": "Donner Pizza",
                "qty": 1,
                "mods": ['10"', "Standard Base", "Standard Crust"],
            },
        ]
    )
    md = {"_last_inbound_sms": 'add a 10" donner pizza'}
    out = t._merge_cart_with_previous(prev, new, md)
    parsed = json.loads(out)
    donner = [x for x in parsed if str(x.get("name", "")).strip().lower() == "donner pizza"]
    assert len(donner) == 2
    sizes = [set(str(m) for m in (x.get("mods") or [])) for x in donner]
    assert any('16"' in s for s in sizes)
    assert any('10"' in s for s in sizes)


def test_merge_cart_add_intent_merges_complementary_partial_pizza_rows():
    """
    LLM can split one add-intent pizza into two same-name rows ([BBQ Base] + [16"]).
    Merge those partial rows first so we don't get stuck re-asking size forever.
    """
    prev = json.dumps(
        [
            {
                "name": "Donner Pizza",
                "qty": 1,
                "mods": ['16"'],
            }
        ]
    )
    new = json.dumps(
        [
            {"name": "Donner Pizza", "qty": 1, "mods": ["BBQ Base"]},
            {"name": "Donner Pizza", "qty": 1, "mods": ['16"']},
        ]
    )
    md = {"_last_inbound_sms": "add a donner pizza with bbq base"}
    out = t._merge_cart_with_previous(prev, new, md)
    parsed = json.loads(out)
    donner = [x for x in parsed if str(x.get("name", "")).strip().lower() == "donner pizza"]
    assert len(donner) == 2
    bbq_line = next(
        x
        for x in donner
        if any(str(m).strip().lower() == "bbq base" for m in (x.get("mods") or []))
    )
    assert any(
        ('16"' in str(m)) or ("large" in str(m).lower())
        for m in (bbq_line.get("mods") or [])
    )


def test_deterministic_category_listing_reply_uses_pending_categories_for_list_request():
    orig_pending = t._sku_list_for_pending_categories
    try:
        t._sku_list_for_pending_categories = lambda _cats: [
            "Alpha Pizza",
            "Bravo Pizza",
            "Charlie Pizza",
        ]
        md = {
            "pending_category_choice": {
                "categories": ["Pizzas"],
                "prompt": "category_disambiguation",
            }
        }
        out = t._deterministic_category_listing_reply("list em", md)
        assert out is not None
        assert "1. Alpha Pizza" in out
        assert "3. Charlie Pizza" in out
    finally:
        t._sku_list_for_pending_categories = orig_pending


def test_deterministic_category_listing_reply_sets_pending_for_generic_category_request():
    orig_detect = t._detect_generic_category_request_from_inbound
    orig_sku = t._sku_list_for_category_disambiguation
    try:
        t._detect_generic_category_request_from_inbound = lambda _m: "Pizzas"
        t._sku_list_for_category_disambiguation = lambda _c: [
            "Hawaiian Pizza",
            "Donner Pizza",
            "Parmo Pizza",
        ]
        md = {"pending_category_choice": {"categories": [], "prompt": ""}}
        out = t._deterministic_category_listing_reply("add a pizza", md)
        assert out is not None
        assert "1. Hawaiian Pizza" in out
        assert md["pending_category_choice"]["categories"] == ["Pizzas"]
    finally:
        t._detect_generic_category_request_from_inbound = orig_detect
        t._sku_list_for_category_disambiguation = orig_sku


def test_detect_generic_category_request_supports_terse_kebab_turn():
    orig_idx = t.pos_service.available_lookup_index
    try:
        t.pos_service.available_lookup_index = {
            "a": {"categoryName": "Kebabs", "name": "Donner Kebab"},
            "b": {"categoryName": "Pizzas", "name": "Pepperoni Pizza"},
        }
        out = t._detect_generic_category_request_from_inbound("kebab")
        assert out == "Kebabs"
    finally:
        t.pos_service.available_lookup_index = orig_idx


def test_detect_generic_category_request_prefers_wrap_it_up_for_plain_wraps():
    orig_idx = t.pos_service.available_lookup_index
    try:
        t.pos_service.available_lookup_index = {
            "a": {"categoryName": "Wrap It Up", "name": "Chicken Wrap"},
            "b": {"categoryName": "Wrap It Up", "name": "Parmo Wrap"},
            "c": {
                "categoryName": "Parmo Time Wraps",
                "name": "Wrapped Donner Parmo",
            },
            "d": {
                "categoryName": "Parmo Time Wraps",
                "name": "Wrapped Explosive Parmo",
            },
        }
        assert t._detect_generic_category_request_from_inbound("wrap") == "Wrap It Up"
        assert t._detect_generic_category_request_from_inbound("wraps") == "Wrap It Up"
        assert t._detect_generic_category_request_from_inbound("parmo wrap") is None
    finally:
        t.pos_service.available_lookup_index = orig_idx


def test_detect_generic_category_request_ignores_only_one_of_it_phrase():
    orig_idx = t.pos_service.available_lookup_index
    try:
        t.pos_service.available_lookup_index = {
            "a": {"categoryName": "Wrap It Up", "name": "Chicken Wrap"},
            "b": {"categoryName": "Pizzas", "name": "Pepperoni Pizza"},
        }
        assert t._detect_generic_category_request_from_inbound("i only want one of it") is None
    finally:
        t.pos_service.available_lookup_index = orig_idx


def test_wrap_group_requires_sauce_selection_for_wrap_sauce_group():
    assert _wrap_group_requires_sauce_selection(
        "Chicken Wrap",
        "Wrap It Up",
        "Please choose your sauce",
        "",
        [
            {"name": "BBQ Sauce"},
            {"name": "Chilli Sauce"},
        ],
    )


def test_wrap_group_requires_sauce_selection_for_wrap_salad_and_sauce_group_min_zero():
    assert _wrap_group_requires_sauce_selection(
        "Mixed Wrap",
        "Wrap It Up",
        "Please select your salad and sauce",
        "Wrap Salad & Sauce",
        [
            {"name": "Cheese"},
            {"name": "All Salad"},
            {"name": "No Salad"},
            {"name": "Chilli Sauce"},
            {"name": "Garlic Sauce"},
            {"name": "No Sauce"},
        ],
    )


def test_wrap_group_requires_sauce_selection_ignores_non_wrap_items():
    assert not _wrap_group_requires_sauce_selection(
        "Pepperoni Pizza",
        "Pizzas",
        "Please choose your sauce",
        "",
        [
            {"name": "BBQ Sauce"},
            {"name": "Chilli Sauce"},
        ],
    )


def test_detect_generic_category_request_handles_not_these_the_sides():
    orig_idx = t.pos_service.available_lookup_index
    try:
        t.pos_service.available_lookup_index = {
            "a": {"categoryName": "Garlic Bread", "name": "Garlic Bread"},
            "b": {"categoryName": "Garlic Bread", "name": "Cheese Garlic Bread"},
            "c": {
                "categoryName": "Side Dishes",
                "name": "Cheese, Chips And Garlic",
            },
            "d": {"categoryName": "Side Dishes", "name": "Loaded Chips"},
        }
        assert (
            t._detect_generic_category_request_from_inbound("not these the sides")
            == "Side Dishes"
        )
    finally:
        t.pos_service.available_lookup_index = orig_idx


def test_resolve_specific_product_name_feed_the_fam_without_add_verb():
    orig_get_names = t.pos_service.get_all_product_names
    try:
        t.pos_service.get_all_product_names = lambda: [
            "Feed The Fam",
            "Meal Deal 3",
            "Home Alone",
        ]
        assert t._resolve_specific_product_name_from_inbound("feed the fam") == "Feed The Fam"
    finally:
        t.pos_service.get_all_product_names = orig_get_names


def test_resolve_specific_product_name_cheese_chips_and_garlics_side_not_bread():
    orig_get_names = t.pos_service.get_all_product_names
    try:
        t.pos_service.get_all_product_names = lambda: [
            "Garlic Bread",
            "Cheese Garlic Bread",
            "Cheese And Tomato Garlic Bread",
            "Cheese, Chips And Garlic",
            "Garlic Dip",
        ]
        assert (
            t._resolve_specific_product_name_from_inbound("add cheese chips and garlics")
            == "Cheese, Chips And Garlic"
        )
    finally:
        t.pos_service.get_all_product_names = orig_get_names


def test_resolve_specific_product_name_standalone_garlic_prefers_dip():
    orig_get_names = t.pos_service.get_all_product_names
    try:
        t.pos_service.get_all_product_names = lambda: [
            "Garlic Bread",
            "Cheese Garlic Bread",
            "Garlic Dip",
            "Cheese, Chips And Garlic",
        ]
        assert t._resolve_specific_product_name_from_inbound("garlic") == "Garlic Dip"
        assert t._resolve_specific_product_name_from_inbound("garlic dips") == "Garlic Dip"
        assert t._resolve_specific_product_name_from_inbound("add 3 garlics") == "Garlic Dip"
        assert t._resolve_specific_product_name_from_inbound("3 garlic dip") == "Garlic Dip"
        assert t._resolve_specific_product_name_from_inbound("garlic bread") is None
        assert t._resolve_specific_product_name_from_inbound("add 2 garlic breads") is None
    finally:
        t.pos_service.get_all_product_names = orig_get_names


def test_deterministic_category_listing_correction_turn_switches_to_sides():
    orig_sku = t._sku_list_for_category_disambiguation
    orig_idx = t.pos_service.available_lookup_index
    try:
        t.pos_service.available_lookup_index = {
            "a": {"categoryName": "Garlic Bread", "name": "Garlic Bread"},
            "b": {
                "categoryName": "Side Dishes",
                "name": "Cheese, Chips And Garlic",
            },
            "c": {"categoryName": "Side Dishes", "name": "Loaded Chips"},
        }
        t._sku_list_for_category_disambiguation = lambda cat: (
            ["Cheese, Chips And Garlic", "Loaded Chips", "Chips"]
            if str(cat).strip().lower() == "side dishes"
            else ["Garlic Bread", "Cheese Garlic Bread"]
        )
        md = {
            "pending_category_choice": {
                "categories": ["Garlic Bread"],
                "prompt": "category_disambiguation",
            }
        }
        out = t._deterministic_category_listing_reply("not these the sides", md)
        assert out is not None
        assert "Cheese, Chips And Garlic" in out
        assert md["pending_category_choice"]["categories"] == ["Side Dishes"]
    finally:
        t._sku_list_for_category_disambiguation = orig_sku
        t.pos_service.available_lookup_index = orig_idx


def test_message_has_specific_product_reference_recognizes_parmo_wrap_sku():
    orig_get_names = t.pos_service.get_all_product_names
    try:
        t.pos_service.get_all_product_names = lambda: [
            "Parmo Wrap",
            "Chicken Wrap",
            "Wrapped Donner Parmo",
        ]
        assert t._message_has_specific_product_reference("parmo wrap")
    finally:
        t.pos_service.get_all_product_names = orig_get_names


def test_merge_cart_correction_turn_keeps_existing_feed_the_fam_line():
    prev = json.dumps(
        [
            {
                "name": "Feed The Fam",
                "qty": 1,
                "mods": [
                    '12" Veggie Delight',
                    "Bbq Base",
                    "Standard Crust",
                    '12" Pepperoni',
                    "Standard Base",
                    "Stuffed Crust",
                    '12" Philly Cheesesteak',
                    "Standard Base",
                    "Standard Crust",
                    "Garlic Dip",
                    "BBQ Dip",
                    "Ketchup",
                    "Chilli Dip",
                ],
            }
        ]
    )
    new = json.dumps(
        [
            {"name": "Chips", "qty": 1, "mods": []},
            {"name": "Garlic Bread", "qty": 1, "mods": []},
            {"name": "Donner Meat Chips, Cheese And Garlic", "qty": 1, "mods": []},
        ]
    )
    md = {
        "_last_inbound_sms": "not these the sides",
        "pending_category_choice": {
            "categories": ["Garlic Bread"],
            "prompt": "category_disambiguation",
        },
    }
    out = t._merge_cart_with_previous(prev, new, md)
    parsed = json.loads(out)
    names = [str(x.get("name", "")) for x in parsed if isinstance(x, dict)]
    assert "Feed The Fam" in names
    assert "Donner Meat Chips, Cheese And Garlic" in names


def test_bill_line_for_deal_without_mod_detail_has_no_empty_parentheses():
    orig_idx = t.pos_service.available_lookup_index
    try:
        t.pos_service.available_lookup_index = {
            "pid_feed": {
                "name": "Feed The Fam",
                "categoryName": "Meal Deals",
                "printable_groups": [],
            }
        }
        mapped_items = [
            {
                "name": "Feed The Fam",
                "partnerId": "pid_feed",
                "quantity": 1,
                "price": 2999,
                "options": [],
            }
        ]
        lines = build_bill_lines_from_mapped_items(mapped_items)
        assert len(lines) == 1
        assert "()" not in lines[0]
        assert lines[0].startswith("1x Feed The Fam (")
    finally:
        t.pos_service.available_lookup_index = orig_idx


def test_merge_cart_add_meal_deal_preserves_existing_lines():
    prev = json.dumps(
        [
            {"name": "Parmo Wrap", "qty": 1, "mods": ["Make It Explosive"]},
            {"name": "Parmo Wrap", "qty": 1, "mods": ["Make It Brisket"]},
            {"name": "Chicken Wrap", "qty": 1, "mods": ["BBQ Sauce"]},
            {"name": "500ml Bottles", "qty": 1, "mods": ["DR Pepper"]},
            {
                "name": "Double Patty Smash Burger With Homemade Chips",
                "qty": 1,
                "mods": [
                    "Swiss Cheese",
                    "No Bacon",
                    "Fried Onion",
                    "Heinz Ketchup",
                    "Gherkins",
                ],
            },
            {"name": "Wrapped Explosive Parmo", "qty": 1, "mods": ["No Salad"]},
        ]
    )
    new = json.dumps(
        [
            {"name": "Meal Deal 3", "qty": 1, "mods": []},
        ]
    )
    md = {"_last_inbound_sms": "add a meal deal 3", "_user_signaled_add_intent": True}
    out = t._merge_cart_with_previous(prev, new, md)
    parsed = json.loads(out)
    names = [str(x.get("name", "")) for x in parsed]
    assert "Meal Deal 3" in names
    assert "Parmo Wrap" in names
    assert "Chicken Wrap" in names
    assert "500ml Bottles" in names
    assert "Wrapped Explosive Parmo" in names
    assert len(parsed) == 7


def test_merge_cart_pending_meal_deal_step_keeps_existing_non_deal_lines():
    prev = json.dumps(
        [
            {"name": "Parmo Wrap", "qty": 1, "mods": ["Make It Explosive"]},
            {"name": "Chicken Wrap", "qty": 1, "mods": ["BBQ Sauce"]},
            {"name": "500ml Bottles", "qty": 1, "mods": ["DR Pepper"]},
            {"name": "Wrapped Explosive Parmo", "qty": 1, "mods": ["No Salad"]},
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
                    "2x Bottles Of Coke",
                ],
            },
        ]
    )
    new = json.dumps(
        [
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
    )
    md = {
        "_last_inbound_sms": "garlic and bbq dip",
        "pending_required_choice": {
            "item": "Meal Deal 3",
            "options": ["Chilli Dip", "Garlic Dip", "BBQ Dip", "Ketchup", "No Dip"],
        },
    }
    out = t._merge_cart_with_previous(prev, new, md)
    parsed = json.loads(out)
    names = [str(x.get("name", "")) for x in parsed]
    assert "Parmo Wrap" in names
    assert "Chicken Wrap" in names
    assert "500ml Bottles" in names
    assert "Wrapped Explosive Parmo" in names
    md3 = next(x for x in parsed if str(x.get("name", "")) == "Meal Deal 3")
    mods = [str(m) for m in (md3.get("mods") or [])]
    assert mods.count("Garlic Dip") == 3
    assert mods.count("BBQ Dip") == 3


def test_sms_footer_not_prepended_when_order_so_far_already_present():
    metadata = {
        "last_quoted_items": json.dumps(
            [{"name": "Meal Deal 3", "qty": 1, "mods": []}]
        ),
        "last_quoted_bill_lines": ["1x Meal Deal 3 (GBP14.99)"],
        "last_quoted_food_total_pence": 1499,
    }
    body = "Your order so far:\n  - 1x Meal Deal 3\nWhat would you like next?"
    out = _append_sms_cart_footer_if_needed(body, metadata, session_active=True)
    assert out == body


def test_sms_footer_not_prepended_when_current_order_wording_already_present():
    metadata = {
        "last_quoted_items": json.dumps(
            [{"name": "Meal Deal 3", "qty": 1, "mods": []}]
        ),
        "last_quoted_bill_lines": ["1x Meal Deal 3 (GBP14.99)"],
        "last_quoted_food_total_pence": 1499,
    }
    body = "Here is your current order:\n  - 1x Meal Deal 3\nAnything else?"
    out = _append_sms_cart_footer_if_needed(body, metadata, session_active=True)
    assert out == body


def test_sms_footer_prepended_when_recap_missing():
    metadata = {
        "last_quoted_items": json.dumps(
            [{"name": "Meal Deal 3", "qty": 1, "mods": []}]
        ),
        "last_quoted_bill_lines": ["1x Meal Deal 3 (GBP14.99)"],
        "last_quoted_food_total_pence": 1499,
    }
    body = "What would you like next?"
    out = _append_sms_cart_footer_if_needed(body, metadata, session_active=True)
    assert out.startswith("---\nOrder so far:\n")
    assert "1x Meal Deal 3 (GBP14.99)" in out
    assert out.endswith(body)


def test_extract_explicit_item_quantity_detects_multi_add_count():
    assert _extract_explicit_item_quantity("add 4 garlic dips") == 4


def test_extract_explicit_item_quantity_ignores_pizza_size_number():
    assert _extract_explicit_item_quantity('12" pepperoni pizza') is None


def test_extract_explicit_item_quantity_ignores_embedded_bundle_count():
    assert (
        _extract_explicit_item_quantity(
            "add couples night with 2",
            matched_product_name="Couples Night With 2x 500ml Soft Drinks",
        )
        is None
    )


def test_extract_explicit_item_quantity_keeps_leading_qty_for_bundle_item():
    assert (
        _extract_explicit_item_quantity(
            "add 2 couples night with 2x 500ml soft drinks",
            matched_product_name="Couples Night With 2x 500ml Soft Drinks",
        )
        == 2
    )


def test_pending_category_numeric_choice_uses_stored_option_order():
    md = {
        "pending_category_choice": {
            "categories": ["Side Dishes"],
            "prompt": "category_disambiguation",
            "options": ["Alpha Side", "Bravo Side", "Charlie Side"],
        },
        "_last_inbound_sms": "2",
        "canonical_cart_json": "[]",
        "last_quoted_items": "[]",
    }
    out = t._inject_inbound_pending_category_numeric_choice(
        '[{"name":"Side Dishes","qty":1,"mods":[]}]',
        md,
    )
    parsed = json.loads(out)
    assert parsed[0]["name"] == "Bravo Side"


def test_merge_cart_direct_add_target_does_not_increment_unrelated_chip_lines():
    old_list = [
        {"name": "Loaded Chips", "qty": 1, "mods": []},
        {"name": "Cheese, Chips And Garlic", "qty": 1, "mods": []},
        {"name": "Cheese And Chips", "qty": 2, "mods": []},
        {"name": "Garlic Dip", "qty": 3, "mods": []},
        {"name": "Donner Meat Chips, Cheese And Garlic", "qty": 1, "mods": []},
    ]
    new_list = list(old_list) + [
        {"name": "Chips Bechemal Sauce And Cheese", "qty": 1, "mods": []}
    ]
    md = {
        "_last_inbound_sms": "add chips bechemal sauce and cheese",
        "_user_signaled_add_intent": True,
        "_direct_add_target_name": "Chips Bechemal Sauce And Cheese",
    }
    out = t._merge_cart_with_previous(json.dumps(old_list), json.dumps(new_list), md)
    lines = t._parse_simple_cart(out)

    def _qty(name: str) -> int:
        for row in lines:
            if str(row.get("name", "")).strip().lower() == name.lower():
                return int(row.get("qty", 1) or 1)
        return 0

    assert _qty("Loaded Chips") == 1
    assert _qty("Cheese, Chips And Garlic") == 1
    assert _qty("Cheese And Chips") == 2
    assert _qty("Donner Meat Chips, Cheese And Garlic") == 1
    assert _qty("Chips Bechemal Sauce And Cheese") == 1


def test_merge_cart_direct_add_target_applies_explicit_multi_quantity_delta():
    old_list = [
        {"name": "Loaded Chips", "qty": 1, "mods": []},
        {"name": "Garlic Dip", "qty": 1, "mods": []},
    ]
    new_list = [
        {"name": "Loaded Chips", "qty": 1, "mods": []},
        {"name": "Garlic Dip", "qty": 4, "mods": []},
    ]
    md = {
        "_last_inbound_sms": "add 4 garlic dips",
        "_user_signaled_add_intent": True,
        "_direct_add_target_name": "Garlic Dip",
    }
    out = t._merge_cart_with_previous(json.dumps(old_list), json.dumps(new_list), md)
    lines = t._parse_simple_cart(out)
    assert len(lines) == 2
    garlic = next(x for x in lines if str(x.get("name", "")).strip().lower() == "garlic dip")
    loaded = next(x for x in lines if str(x.get("name", "")).strip().lower() == "loaded chips")
    assert int(garlic.get("qty", 1) or 1) == 5
    assert int(loaded.get("qty", 1) or 1) == 1


def test_deal_chips_remap_does_not_switch_to_non_qty_side_option():
    mod_data = {"name": "Chips", "price": 199, "menuModifierId": "chips-id"}
    allowed_mods = {
        "Chips": {"name": "Chips", "price": 199, "menuModifierId": "chips-id"},
        "Cheese And Chips": {
            "name": "Cheese And Chips",
            "price": 0,
            "menuModifierId": "cheese-chips-id",
        },
    }
    product_data = {
        "name": "Couples Night With Bottle Wine",
        "categoryName": "Meal Deals",
        "printable_groups": [
            {
                "name": "CN - Side1",
                "options": [{"name": "Cheese And Chips"}, {"name": "Mozzarella Sticks"}],
            }
        ],
    }
    out = _deal_remap_bare_chips_to_included_qty_line(
        mod_data,
        "chips",
        product_data,
        allowed_mods,
    )
    assert str(out.get("name", "")).strip().lower() == "chips"


def test_deal_chips_remap_prefers_included_same_name_variant_from_lookup_lists():
    paid = {"name": "Chips", "price": 299, "menuModifierId": "chips-paid"}
    included = {"name": "Chips", "price": 0, "menuModifierId": "chips-included"}
    allowed_mods = {
        "Chips": paid,
        "Cheese And Chips": {
            "name": "Cheese And Chips",
            "price": 0,
            "menuModifierId": "cheese-chips-id",
        },
    }
    product_data = {
        "name": "Couples Night With Bottle Wine",
        "categoryName": "Meal Deals",
        "printable_groups": [
            {
                "name": "CN - Side1",
                "options": [{"name": "Chips"}, {"name": "Cheese And Chips"}],
            }
        ],
        "modifier_lookup_lists": {
            "chips": [paid, included],
        },
    }
    out = _deal_remap_bare_chips_to_included_qty_line(
        paid,
        "chips",
        product_data,
        allowed_mods,
    )
    assert str(out.get("menuModifierId", "")) == "chips-included"
    assert int(out.get("price", 0) or 0) == 0


def test_deal_chips_remap_keeps_scoped_side_slot_modifier():
    side1 = {"name": "Chips", "price": 0, "menuModifierId": "chips-side1"}
    side2 = {"name": "Chips", "price": 0, "menuModifierId": "chips-side2"}
    paid = {"name": "Chips", "price": 299, "menuModifierId": "chips-paid"}
    allowed_mods = {
        "Chips": paid,
    }
    product_data = {
        "name": "Couples Night With Bottle Wine",
        "categoryName": "Meal Deals",
        "printable_groups": [
            {
                "name": "CN - Side1",
                "options": [{"name": "Chips", "menuModifierId": "chips-side1"}],
            },
            {
                "name": "CN - Side2",
                "options": [{"name": "Chips", "menuModifierId": "chips-side2"}],
            },
        ],
        "modifier_lookup_lists": {
            "chips": [side1, side2, paid],
        },
    }
    out = _deal_remap_bare_chips_to_included_qty_line(
        side2,
        "chips",
        product_data,
        allowed_mods,
        scoped_slot=1,
    )
    assert str(out.get("menuModifierId", "")) == "chips-side2"


if __name__ == "__main__":
    test_broken_inch_in_mod_string()
    test_parse_simple_cart_merge_path()
    test_sanitize_idempotent()
    test_double_quote_after_inch_digit_in_mod()
    test_multi_item_cart_inch_dup_quote_does_not_drop_other_lines()
    test_multi_item_cart_missing_mods_close_bracket()
    test_deal_collapse_replaces_standard_base_crust()
    test_classify_bbq_sauce_as_deal_base()
    test_classify_parmo_distinct_from_pizza_slot()
    test_deal_guard_garlic_bread_not_mapped_to_garlic_dip()
    test_map_inbound_pending_size_synonyms()
    test_map_inbound_number_with_extras_meal_deal_pizza_list()
    test_reorder_p1_base_crust_then_p2_base_keeps_first_crust_on_p1()
    test_merge_multi_line_meal_deal_appends_second_pizza_slot()
    test_printable_row_max_for_numbered_deal_slots_is_single_pick()
    test_group_scoped_match_avoids_reusing_completed_meal_deal_pizza_slots()
    test_pending_opts_are_salad_binary()
    test_merge_salad_binary_append_same_preserves_first_slot()
    test_merge_salad_binary_fallback_when_two_half_parmos_one_salad_line()
    test_meal_deal_max_pizza_slots_default_and_trim()
    test_remove_meal_deal_n_is_not_full_cart_clear()
    test_remove_lines_matches_name_plus_mods_bottles_of_coke()
    test_expand_dip_picks_for_remaining_six_two_types()
    test_pending_opts_look_like_deal_dips()
    test_merge_mods_repeat_dip_appends()
    test_collapse_middle_pizza_flavour_md3()
    test_upgrade_bare_chips_to_4x_when_only_qty_option()
    test_inbound_signals_show_cart_only()
    test_inject_pending_category_numeric_choice_with_extras_uses_pending_index()
    test_merge_cart_add_identical_item_increments_qty()
    test_merge_cart_add_same_sku_different_size_keeps_both_lines()
    test_merge_cart_modifier_change_still_merges_structural_slots()
    test_merge_cart_multiline_add_same_pizza_keeps_new_placeholder_for_customization()
    test_merge_cart_multiline_add_same_pizza_same_as_before_increments_qty()
    test_merge_cart_add_same_pizza_qty_bump_from_model_becomes_placeholder()
    test_merge_cart_add_same_configured_non_pizza_keeps_placeholder()
    test_merge_cart_add_same_configured_non_pizza_same_as_before_increments_qty()
    test_merge_cart_add_meal_deal_qty_bump_stays_compacted_line()
    test_merge_cart_multiline_add_same_name_with_different_mods_keeps_separate_lines()
    test_merge_cart_add_intent_merges_complementary_partial_pizza_rows()
    test_deterministic_category_listing_reply_uses_pending_categories_for_list_request()
    test_deterministic_category_listing_reply_sets_pending_for_generic_category_request()
    test_detect_generic_category_request_supports_terse_kebab_turn()
    test_detect_generic_category_request_prefers_wrap_it_up_for_plain_wraps()
    test_detect_generic_category_request_ignores_only_one_of_it_phrase()
    test_detect_generic_category_request_handles_not_these_the_sides()
    test_wrap_group_requires_sauce_selection_for_wrap_sauce_group()
    test_wrap_group_requires_sauce_selection_ignores_non_wrap_items()
    test_resolve_specific_product_name_feed_the_fam_without_add_verb()
    test_resolve_specific_product_name_cheese_chips_and_garlics_side_not_bread()
    test_resolve_specific_product_name_standalone_garlic_prefers_dip()
    test_deterministic_category_listing_correction_turn_switches_to_sides()
    test_message_has_specific_product_reference_recognizes_parmo_wrap_sku()
    test_merge_cart_correction_turn_keeps_existing_feed_the_fam_line()
    test_bill_line_for_deal_without_mod_detail_has_no_empty_parentheses()
    test_merge_cart_add_meal_deal_preserves_existing_lines()
    test_merge_cart_pending_meal_deal_step_keeps_existing_non_deal_lines()
    test_sms_footer_not_prepended_when_order_so_far_already_present()
    test_sms_footer_not_prepended_when_current_order_wording_already_present()
    test_sms_footer_prepended_when_recap_missing()
    test_extract_explicit_item_quantity_detects_multi_add_count()
    test_extract_explicit_item_quantity_ignores_pizza_size_number()
    test_extract_explicit_item_quantity_ignores_embedded_bundle_count()
    test_extract_explicit_item_quantity_keeps_leading_qty_for_bundle_item()
    test_pending_category_numeric_choice_uses_stored_option_order()
    test_merge_cart_direct_add_target_does_not_increment_unrelated_chip_lines()
    test_merge_cart_direct_add_target_applies_explicit_multi_quantity_delta()
    test_deal_chips_remap_does_not_switch_to_non_qty_side_option()
    print("tests/test_cart_json_robust.py: ok")


# ── Multi-select numeric reply tests ─────────────────────────────────
def test_parse_multi_index_reply_space_separated():
    """'2 4 7' should parse as three indices."""
    from src.text_agent.tools import _parse_multi_index_reply
    result = _parse_multi_index_reply("2 4 7", 10)
    assert result == [1, 3, 6]  # zero-based


def test_parse_multi_index_reply_comma_separated():
    """'1, 3, 5' should parse as three indices."""
    from src.text_agent.tools import _parse_multi_index_reply
    result = _parse_multi_index_reply("1, 3, 5", 10)
    assert result == [0, 2, 4]


def test_parse_multi_index_reply_and_separated():
    """'2 and 4 and 7' should parse as three indices."""
    from src.text_agent.tools import _parse_multi_index_reply
    result = _parse_multi_index_reply("2 and 4 and 7", 10)
    assert result == [1, 3, 6]


def test_parse_multi_index_reply_single_returns_none():
    """Single number should return None (let existing logic handle)."""
    from src.text_agent.tools import _parse_multi_index_reply
    assert _parse_multi_index_reply("3", 10) is None


def test_parse_multi_index_reply_out_of_range_returns_none():
    """Out-of-range indices should reject the whole input."""
    from src.text_agent.tools import _parse_multi_index_reply
    assert _parse_multi_index_reply("2 99", 10) is None


def test_parse_multi_index_reply_mixed_separators():
    """'1, 3 and 5' should parse as three indices."""
    from src.text_agent.tools import _parse_multi_index_reply
    result = _parse_multi_index_reply("1, 3 and 5", 10)
    assert result == [0, 2, 4]


# ── Configurable-item modifier merge test ────────────────────────────
def test_configurable_item_merge_appends_new_mods():
    """Adding sauce to existing parmo wrap should merge, not create new line."""
    old = json.dumps([{"name": "Parmo Wrap", "qty": 1, "mods": ["Full"]}])
    new = json.dumps([{"name": "Parmo Wrap", "qty": 1, "mods": ["Onion", "Garlic Sauce"]}])
    metadata = {"_last_inbound_sms": "i want onion and garlic sauce on the parmo"}
    result = t._merge_cart_with_previous(old, new, metadata)
    cart = json.loads(result)
    parmo_lines = [c for c in cart if "parmo" in c.get("name", "").lower()]
    assert len(parmo_lines) == 1, f"Expected 1 Parmo Wrap line, got {len(parmo_lines)}: {parmo_lines}"
    mods = [str(m).lower() for m in parmo_lines[0].get("mods", [])]
    assert "full" in mods, f"'Full' mod missing from merged mods: {mods}"
    assert any("onion" in m for m in mods), f"'Onion' mod missing: {mods}"
    assert any("garlic" in m for m in mods), f"'Garlic Sauce' mod missing: {mods}"


# ---------------------------------------------------------------------------
# ADD-INTENT ECHO FILTER – LLM echoes existing items with wrong mods
# ---------------------------------------------------------------------------

def test_add_intent_echo_filter_drops_hallucinated_parmo():
    """'add a can of coke' — LLM echoes Parmo Wrap with hallucinated mods.
    Only the Coke should be added; Parmo Wrap should keep original mods."""
    old = json.dumps([
        {"name": "Parmo Wrap", "qty": 1, "mods": ["Cheese", "Make It Hot Honey"]},
    ])
    new = json.dumps([
        {"name": "Coke Can", "qty": 1, "mods": []},
        {"name": "Parmo Wrap", "qty": 1, "mods": ["Cheese", "Lettuce", "Onion", "Make It Hot Honey"]},
    ])
    metadata = {"_last_inbound_sms": "add a can of coke"}
    result = t._merge_cart_with_previous(old, new, metadata)
    cart = json.loads(result)
    parmo_lines = [c for c in cart if "parmo" in c.get("name", "").lower()]
    assert len(parmo_lines) == 1, f"Expected 1 Parmo line, got {len(parmo_lines)}: {parmo_lines}"
    mods_l = [str(m).lower() for m in parmo_lines[0].get("mods", [])]
    assert "lettuce" not in mods_l, f"Hallucinated 'Lettuce' should NOT be in mods: {mods_l}"
    assert "onion" not in mods_l, f"Hallucinated 'Onion' should NOT be in mods: {mods_l}"
    # Coke should be present
    coke_lines = [c for c in cart if "coke" in c.get("name", "").lower() or
                  any("coke" in str(m).lower() for m in c.get("mods", []))]
    assert len(coke_lines) >= 1, f"Coke missing from cart: {cart}"


def test_add_intent_echo_filter_drops_echoed_drink():
    """'add 3 garlics' — LLM echoes Parmo Wrap AND Coke Can alongside the new
    Garlic Dip.  Only the Garlic Dip should be added."""
    old = json.dumps([
        {"name": "Parmo Wrap", "qty": 1, "mods": ["Cheese", "Make It Hot Honey"]},
        {"name": "330ml Cans", "qty": 1, "mods": ["Coke Can"]},
    ])
    new = json.dumps([
        {"name": "Garlic Dip", "qty": 3, "mods": []},
        {"name": "Parmo Wrap", "qty": 1, "mods": ["Cheese", "Lettuce", "Onion", "Make It Hot Honey"]},
        {"name": "Coke Can", "qty": 1, "mods": []},
    ])
    metadata = {"_last_inbound_sms": "add 3 garlics"}
    result = t._merge_cart_with_previous(old, new, metadata)
    cart = json.loads(result)
    # Only 3 lines: original Parmo Wrap, original 330ml Cans, new Garlic Dip
    parmo_lines = [c for c in cart if "parmo" in c.get("name", "").lower()]
    assert len(parmo_lines) == 1, f"Expected 1 Parmo, got {len(parmo_lines)}: {parmo_lines}"
    mods_l = [str(m).lower() for m in parmo_lines[0].get("mods", [])]
    assert "lettuce" not in mods_l, f"Hallucinated mods leaked: {mods_l}"
    # Garlic Dip should be qty 3
    garlic_lines = [c for c in cart if "garlic" in c.get("name", "").lower() and "dip" in c.get("name", "").lower()]
    assert len(garlic_lines) == 1, f"Expected 1 Garlic Dip line: {cart}"
    assert garlic_lines[0].get("qty", 0) == 3, f"Garlic Dip qty should be 3: {garlic_lines[0]}"
    # Coke should stay as original 330ml Cans, qty 1 — no phantom second can
    can_lines = [c for c in cart if "330ml" in c.get("name", "").lower() or "cans" in c.get("name", "").lower()]
    assert len(can_lines) == 1, f"Expected 1 can line, got: {can_lines}"
    assert can_lines[0].get("qty", 0) == 1, f"Coke qty should remain 1: {can_lines[0]}"


def test_add_intent_echo_filter_allows_explicit_add_another():
    """'add another parmo wrap' — LLM sends both old parmo and a new empty one.
    The echo filter should keep both since user explicitly named 'parmo wrap'."""
    old = json.dumps([
        {"name": "Parmo Wrap", "qty": 1, "mods": ["Cheese", "Make It Hot Honey"]},
        {"name": "330ml Cans", "qty": 1, "mods": ["Coke Can"]},
    ])
    new = json.dumps([
        {"name": "Parmo Wrap", "qty": 1, "mods": ["Cheese", "Make It Hot Honey"]},
        {"name": "Parmo Wrap", "qty": 1, "mods": []},
        {"name": "330ml Cans", "qty": 1, "mods": ["Coke Can"]},
    ])
    metadata = {"_last_inbound_sms": "add another parmo wrap"}
    result = t._merge_cart_with_previous(old, new, metadata)
    cart = json.loads(result)
    parmo_lines = [c for c in cart if "parmo" in c.get("name", "").lower()]
    total_qty = sum(c.get("qty", 1) for c in parmo_lines)
    assert total_qty >= 2, f"Expected 2 parmo wraps total, got {total_qty}: {parmo_lines}"


# ---------------------------------------------------------------------------
# MULTI-NAME PENDING CHOICE – selecting multiple options by name
# ---------------------------------------------------------------------------

_WRAP_SALAD_SAUCE_OPTS = [
    "All Salad", "Lettuce", "Tomato", "Onion", "No Salad",
    "Chilli Sauce", "Garlic Sauce", "BBQ Sauce", "Garlic Mayonnaise",
    "Ketchup", "No Sauce", "Purple Slaw", "No Chips", "Cheese",
]


def test_parse_multi_name_comma_and():
    """'tomato, chili sauce, lettuce and garlic sauce' → 4 matched options."""
    from src.text_agent.tools import _parse_multi_name_reply
    result = _parse_multi_name_reply(
        "tomato, chili sauce, lettuce and garlic sauce",
        _WRAP_SALAD_SAUCE_OPTS,
    )
    assert result is not None, "Should parse multi-name reply"
    names_l = [r.lower() for r in result]
    assert "tomato" in names_l, f"Tomato missing: {result}"
    assert "chilli sauce" in names_l, f"Chilli Sauce missing: {result}"
    assert "lettuce" in names_l, f"Lettuce missing: {result}"
    assert "garlic sauce" in names_l, f"Garlic Sauce missing: {result}"


def test_parse_multi_name_two_items():
    """'cheese and onion' → 2 matched options."""
    from src.text_agent.tools import _parse_multi_name_reply
    result = _parse_multi_name_reply(
        "cheese and onion",
        _WRAP_SALAD_SAUCE_OPTS,
    )
    assert result is not None
    names_l = [r.lower() for r in result]
    assert "cheese" in names_l
    assert "onion" in names_l


def test_parse_multi_name_typos():
    """'tomatio, chili sauce, letuce and garlik sauce' — typos should still match."""
    from src.text_agent.tools import _parse_multi_name_reply
    result = _parse_multi_name_reply(
        "tomatio, chili sauce, letuce and garlik sauce",
        _WRAP_SALAD_SAUCE_OPTS,
    )
    assert result is not None, "Should fuzzy-match despite typos"
    names_l = [r.lower() for r in result]
    assert "tomato" in names_l, f"Tomato missing: {result}"
    assert "chilli sauce" in names_l, f"Chilli Sauce missing: {result}"
    assert "lettuce" in names_l, f"Lettuce missing: {result}"
    assert "garlic sauce" in names_l, f"Garlic Sauce missing: {result}"


def test_parse_multi_name_single_returns_none():
    """Single option name without separators should return None."""
    from src.text_agent.tools import _parse_multi_name_reply
    result = _parse_multi_name_reply("lettuce", _WRAP_SALAD_SAUCE_OPTS)
    assert result is None


def test_parse_multi_name_all_commas():
    """'lettuce, tomato, onion' — pure comma separation."""
    from src.text_agent.tools import _parse_multi_name_reply
    result = _parse_multi_name_reply(
        "lettuce, tomato, onion",
        _WRAP_SALAD_SAUCE_OPTS,
    )
    assert result is not None
    names_l = [r.lower() for r in result]
    assert "lettuce" in names_l
    assert "tomato" in names_l
    assert "onion" in names_l


def test_multi_name_inject_pending_choice():
    """End-to-end: multi-name reply should inject all matched mods into the cart line."""
    old_cart = json.dumps([{"name": "Mixed Wrap", "qty": 1, "mods": []}])
    new_cart = json.dumps([{"name": "Mixed Wrap", "qty": 1, "mods": ["Lettuce"]}])
    metadata = {
        "_last_inbound_sms": "tomato, chili sauce, lettuce and garlic sauce",
        "pending_required_choice": {
            "item": "Mixed Wrap",
            "options": _WRAP_SALAD_SAUCE_OPTS,
            "append_same_option_group": True,
        },
    }
    result = t._inject_inbound_pending_required_choice(new_cart, metadata)
    cart = json.loads(result)
    wrap_lines = [c for c in cart if "mixed" in c.get("name", "").lower()]
    assert len(wrap_lines) == 1, f"Expected 1 Mixed Wrap, got {len(wrap_lines)}: {wrap_lines}"
    mods_l = [str(m).lower() for m in wrap_lines[0].get("mods", [])]
    assert "tomato" in mods_l, f"Tomato missing from mods: {mods_l}"
    assert "chilli sauce" in mods_l, f"Chilli Sauce missing from mods: {mods_l}"
    assert "lettuce" in mods_l, f"Lettuce missing from mods: {mods_l}"
    assert "garlic sauce" in mods_l, f"Garlic Sauce missing from mods: {mods_l}"


def test_multi_name_inject_parmo_wrap_salad_sauce():
    """Parmo Wrap: 'cheese, lettuce and bbq sauce' should inject all three."""
    old_cart = json.dumps([{"name": "Parmo Wrap", "qty": 1, "mods": []}])
    new_cart = json.dumps([{"name": "Parmo Wrap", "qty": 1, "mods": ["Cheese"]}])
    metadata = {
        "_last_inbound_sms": "cheese, lettuce and bbq sauce",
        "pending_required_choice": {
            "item": "Parmo Wrap",
            "options": _WRAP_SALAD_SAUCE_OPTS,
            "append_same_option_group": True,
        },
    }
    result = t._inject_inbound_pending_required_choice(new_cart, metadata)
    cart = json.loads(result)
    wrap = [c for c in cart if "parmo" in c.get("name", "").lower()]
    assert len(wrap) == 1
    mods_l = [str(m).lower() for m in wrap[0].get("mods", [])]
    assert "cheese" in mods_l, f"Cheese missing: {mods_l}"
    assert "lettuce" in mods_l, f"Lettuce missing: {mods_l}"
    assert "bbq sauce" in mods_l, f"BBQ Sauce missing: {mods_l}"


# ---------------------------------------------------------------------------
# GROUP_MAX ENFORCEMENT – multi-select only when group allows it
# ---------------------------------------------------------------------------

_SIZE_OPTS = ["Small 10\"", "Medium 12\"", "Large 16\""]


def test_group_max_1_blocks_multi_index():
    """With group_max=1, '1 3' should NOT multi-select — fall through to single."""
    old_cart = json.dumps([{"name": "BBQ Chicken Pizza", "qty": 1, "mods": []}])
    new_cart = json.dumps([{"name": "BBQ Chicken Pizza", "qty": 1, "mods": []}])
    metadata = {
        "_last_inbound_sms": "1 3",
        "pending_required_choice": {
            "item": "BBQ Chicken Pizza",
            "options": _SIZE_OPTS,
            "group_max": 1,
        },
    }
    result = t._inject_inbound_pending_required_choice(new_cart, metadata)
    cart = json.loads(result)
    pizza = [c for c in cart if "bbq" in c.get("name", "").lower()]
    assert len(pizza) == 1
    mods = pizza[0].get("mods", [])
    # Should have at most 1 mod (single-select fallback), not 2
    assert len(mods) <= 1, f"group_max=1 should block multi-select: {mods}"


def test_group_max_1_blocks_multi_name():
    """With group_max=1, 'cheese and onion' should NOT multi-select."""
    old_cart = json.dumps([{"name": "Parmo Wrap", "qty": 1, "mods": []}])
    new_cart = json.dumps([{"name": "Parmo Wrap", "qty": 1, "mods": []}])
    metadata = {
        "_last_inbound_sms": "cheese and onion",
        "pending_required_choice": {
            "item": "Parmo Wrap",
            "options": _WRAP_SALAD_SAUCE_OPTS,
            "group_max": 1,
        },
    }
    result = t._inject_inbound_pending_required_choice(new_cart, metadata)
    cart = json.loads(result)
    wrap = [c for c in cart if "parmo" in c.get("name", "").lower()]
    assert len(wrap) == 1
    mods = wrap[0].get("mods", [])
    # Should pick at most 1 option (the best single fuzzy match), not 2
    assert len(mods) <= 1, f"group_max=1 should block multi-name select: {mods}"


def test_group_max_14_allows_multi_name():
    """With group_max=14, multi-name select should work normally."""
    old_cart = json.dumps([{"name": "Mixed Wrap", "qty": 1, "mods": []}])
    new_cart = json.dumps([{"name": "Mixed Wrap", "qty": 1, "mods": []}])
    metadata = {
        "_last_inbound_sms": "tomato, lettuce and garlic sauce",
        "pending_required_choice": {
            "item": "Mixed Wrap",
            "options": _WRAP_SALAD_SAUCE_OPTS,
            "group_max": 14,
        },
    }
    result = t._inject_inbound_pending_required_choice(new_cart, metadata)
    cart = json.loads(result)
    wrap = [c for c in cart if "mixed" in c.get("name", "").lower()]
    assert len(wrap) == 1
    mods_l = [str(m).lower() for m in wrap[0].get("mods", [])]
    assert "tomato" in mods_l, f"Tomato missing: {mods_l}"
    assert "lettuce" in mods_l, f"Lettuce missing: {mods_l}"
    assert "garlic sauce" in mods_l, f"Garlic Sauce missing: {mods_l}"


def test_group_max_truncates_excess_selections():
    """With group_max=2, 'lettuce, tomato, onion' should only select first 2."""
    old_cart = json.dumps([{"name": "Mixed Wrap", "qty": 1, "mods": []}])
    new_cart = json.dumps([{"name": "Mixed Wrap", "qty": 1, "mods": []}])
    metadata = {
        "_last_inbound_sms": "lettuce, tomato, onion",
        "pending_required_choice": {
            "item": "Mixed Wrap",
            "options": _WRAP_SALAD_SAUCE_OPTS,
            "group_max": 2,
        },
    }
    result = t._inject_inbound_pending_required_choice(new_cart, metadata)
    cart = json.loads(result)
    wrap = [c for c in cart if "mixed" in c.get("name", "").lower()]
    assert len(wrap) == 1
    mods = wrap[0].get("mods", [])
    # Should have exactly 2 options, not 3
    assert len(mods) == 2, f"group_max=2 should truncate to 2 options, got {len(mods)}: {mods}"


def test_group_max_truncates_numeric_selections():
    """With group_max=2, '1 3 5' should only select first 2 indices."""
    old_cart = json.dumps([{"name": "Mixed Wrap", "qty": 1, "mods": []}])
    new_cart = json.dumps([{"name": "Mixed Wrap", "qty": 1, "mods": []}])
    metadata = {
        "_last_inbound_sms": "1 3 5",
        "pending_required_choice": {
            "item": "Mixed Wrap",
            "options": _WRAP_SALAD_SAUCE_OPTS,
            "group_max": 2,
        },
    }
    result = t._inject_inbound_pending_required_choice(new_cart, metadata)
    cart = json.loads(result)
    wrap = [c for c in cart if "mixed" in c.get("name", "").lower()]
    assert len(wrap) == 1
    mods = wrap[0].get("mods", [])
    # Should have exactly 2 options, not 3
    assert len(mods) == 2, f"group_max=2 should truncate to 2 indices, got {len(mods)}: {mods}"


# ---------------------------------------------------------------------------
# DEAL PIZZA EXTRAS – base/crust dedup across pizza slots
# ---------------------------------------------------------------------------

_MD6_PIZZA_OPTS = [
    '16" Margherita', '16" Al Funghi', '16" London', '16" Veggie Delight',
    '16" Prosciutto Funghi', '16" Hawaiian', '16" Captain Inferno',
    '16" Pepperoni', '16" Pollo', '16" Philly Cheesesteak',
    '16" Bbq Chicken', '16" Parmo', '16" Naples Special',
    '16" Donner Baked In', '16" Donner On Top', '16" Meat Lovers',
    '16" Tandoori Chicken', '16" The New Yorker', '16" Farmyard Special',
]


def test_deal_pizza_extras_not_deduped_across_slots():
    """5th pizza '13 with bbq base and stuffed crust' — extras must NOT be skipped
    even though earlier pizza slots already have 'BBQ Base' and 'Stuffed Crust'."""
    old_mods = [
        '16" Prosciutto Funghi', 'Standard Base', 'Standard Crust',
        '16" Captain Inferno', 'Standard Base', 'Stuffed Crust',
        '16" Pollo', 'BBQ Base', 'Standard Crust',
        '16" Bbq Chicken', 'Standard Base', 'Standard Crust',
    ]
    old_cart = json.dumps([{"name": "Meal Deal 6", "qty": 1, "mods": old_mods}])
    # LLM only sends the new pizza name; merge appends it
    new_cart = json.dumps([{"name": "Meal Deal 6", "qty": 1, "mods": old_mods + ['16" Naples Special']}])
    metadata = {
        "_last_inbound_sms": "13 with bbq base and stuffed crust",
        "pending_required_choice": {
            "item": "Meal Deal 6",
            "options": _MD6_PIZZA_OPTS,
            "group_max": 1,
            "append_same_option_group": True,
        },
    }
    result = t._inject_inbound_pending_required_choice(new_cart, metadata)
    cart = json.loads(result)
    md = [c for c in cart if "meal deal" in c.get("name", "").lower()]
    assert len(md) == 1
    mods_l = [str(m).lower() for m in md[0].get("mods", [])]
    # The 5th pizza should have its own BBQ Base and Stuffed Crust
    naples_idx = None
    for i, m in enumerate(mods_l):
        if "naples special" in m:
            naples_idx = i
    assert naples_idx is not None, f"Naples Special missing: {mods_l}"
    # BBQ Base and Stuffed Crust should appear AFTER Naples Special
    after_naples = mods_l[naples_idx + 1:]
    assert any("bbq base" in m for m in after_naples), \
        f"BBQ Base missing after 5th pizza: {mods_l}"
    assert any("stuffed crust" in m for m in after_naples), \
        f"Stuffed Crust missing after 5th pizza: {mods_l}"


# ---------------------------------------------------------------------------
# DIP BATCH 3 types – expand 3 dip types to fill 6 slots
# ---------------------------------------------------------------------------

_DIP_OPTS = ["Chilli Dip", "Garlic Dip", "BBQ Dip", "Ketchup", "No Dip"]


def test_dip_batch_three_types_expanded_to_six():
    """'garlic, chili dip and ketchup' with rem=6 should expand to 6 dips (2 each)."""
    old_cart = json.dumps([{"name": "Meal Deal 6", "qty": 1, "mods": ["some mod"]}])
    new_cart = old_cart
    metadata = {
        "_last_inbound_sms": "garlic, chili dip and ketchup",
        "canonical_cart_json": old_cart,
        "pending_required_choice": {
            "item": "Meal Deal 6",
            "options": _DIP_OPTS,
            "append_same_option_group": True,
            "deal_dip_repeat_picks": True,
            "deal_group_pick_remaining": 6,
            "group_max": 999,
        },
    }
    result = t._inject_inbound_pending_required_choice(new_cart, metadata)
    cart = json.loads(result)
    md = [c for c in cart if "meal deal" in c.get("name", "").lower()]
    assert len(md) == 1
    mods_l = [str(m).lower() for m in md[0].get("mods", [])]
    # Should have 6 dip mods (2 of each type) + "some mod"
    garlic_count = sum(1 for m in mods_l if "garlic dip" in m)
    chilli_count = sum(1 for m in mods_l if "chilli dip" in m)
    ketchup_count = sum(1 for m in mods_l if "ketchup" in m)
    total_dips = garlic_count + chilli_count + ketchup_count
    assert total_dips == 6, f"Expected 6 dips total, got {total_dips}: {mods_l}"
    assert garlic_count == 2, f"Expected 2 Garlic Dip, got {garlic_count}: {mods_l}"
    assert chilli_count == 2, f"Expected 2 Chilli Dip, got {chilli_count}: {mods_l}"
    assert ketchup_count == 2, f"Expected 2 Ketchup, got {ketchup_count}: {mods_l}"


def test_multi_name_no_crash_when_chosen_unbound():
    """Multi-name select should not crash with UnboundLocalError on 'chosen'."""
    old_cart = json.dumps([{"name": "Mixed Wrap", "qty": 1, "mods": []}])
    # LLM sends invalid/empty JSON — triggers the fallback path that references 'chosen'
    metadata = {
        "_last_inbound_sms": "tomato, lettuce and garlic sauce",
        "canonical_cart_json": old_cart,
        "pending_required_choice": {
            "item": "Mixed Wrap",
            "options": _WRAP_SALAD_SAUCE_OPTS,
            "group_max": 14,
        },
    }
    # Pass broken JSON as items_str to force the except/fallback path.
    # Should not raise UnboundLocalError — must return valid JSON.
    result = t._inject_inbound_pending_required_choice("NOT VALID JSON", metadata)
    # Should succeed without crashing and return a valid cart
    cart = json.loads(result)
    wrap = [c for c in cart if "mixed" in c.get("name", "").lower()]
    assert len(wrap) >= 1, f"Mixed Wrap missing: {cart}"
