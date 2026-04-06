"""Tests for meal-deal slot normalization (shared POS group ids, dip caps)."""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.int.poshub_service import (
    _deal_autofill_single_option_required_groups,
    _deal_backstop_unfilled_half_parmo_missing_row,
    _deal_backstop_unfilled_numbered_pizza_missing_row,
    _deal_half_parmo_flavour_slot_rows_per_group_id,
    _deal_normalize_excess_slot_selections,
    _deal_numbered_pizza_slot_fill_state,
    _deal_parmo_flavour_pick_count,
    _deal_pizza_flavour_pick_count_for_upsell,
    deal_structured_line_parmo_slots_incomplete_message,
    deal_structured_line_pizza_slots_incomplete_message,
    _is_inch_based_size_option,
    _size_display_names_for_opts,
)


def test_shared_gid_two_half_parmo_slots_keeps_both_picks():
    """POS reuses one menuModifierGroupId for first+second half parmo — cap is per slot row."""
    op = {
        "printable_groups": [
            {
                "name": "Please select your first half parmo",
                "options": [{"name": "Half Alpha", "menuModifierGroupId": "G1"}],
            },
            {
                "name": "Please select your second half parmo",
                "options": [{"name": "Half Beta", "menuModifierGroupId": "G1"}],
            },
        ],
        "group_constraints": {"G1": {"max": 1, "min": 0}},
    }
    assert _deal_half_parmo_flavour_slot_rows_per_group_id(op)["G1"] == 2
    item = {
        "options": [
            {"name": "Half Alpha", "menuModifierGroupId": "G1"},
            {"name": "Half Beta", "menuModifierGroupId": "G1"},
        ]
    }
    _deal_normalize_excess_slot_selections(item, op)
    assert len(item["options"]) == 2
    names = [o["name"] for o in item["options"]]
    assert "Half Alpha" in names and "Half Beta" in names


def test_single_option_autofill_deferred_until_pizza_slots_filled():
    """Do not inject a lone required option (e.g. drinks) before all pizza picks exist."""
    gid_bottle = "bottle-gid"
    gid_pizza = "pizza-gid"
    op = {
        "name": "Meal Deal 3",
        "printable_groups": [
            {
                "name": "Please select your first pizza",
                "description": "MD3 - 1st 16\" Pizza Type",
                "options": [
                    {"name": '16" Margherita', "menuModifierGroupId": gid_pizza},
                ],
            },
            {
                "name": "Please select your second pizza",
                "description": "MD3 - 2nd 16\" Pizza Type",
                "options": [
                    {"name": '16" London', "menuModifierGroupId": gid_pizza},
                ],
            },
            {
                "name": "Drinks",
                "options": [
                    {"name": "2x Bottles Of Coke", "menuModifierGroupId": gid_bottle},
                ],
            },
        ],
        "group_constraints": {
            gid_pizza: {"min": 0, "max": 2},
            gid_bottle: {"min": 1, "max": 1},
        },
        "modifier_lookup": {
            "2x Bottles Of Coke": {
                "name": "2x Bottles Of Coke",
                "menuModifierId": "m-bottle",
                "menuModifierGroupId": gid_bottle,
                "modifierGroupName": "Drinks",
                "price": 0,
            },
        },
    }
    item = {
        "name": "Meal Deal 3",
        "options": [
            {"name": '16" Margherita', "menuModifierGroupId": gid_pizza},
        ],
    }
    _deal_autofill_single_option_required_groups(item, op)
    assert not any(
        "Bottle" in (o.get("name") or "") for o in (item.get("options") or [])
    )
    item["options"].append(
        {"name": '16" London', "menuModifierGroupId": gid_pizza},
    )
    _deal_autofill_single_option_required_groups(item, op)
    assert any(
        "Coke" in (o.get("name") or "") for o in (item.get("options") or [])
    )


def test_pizza_backstop_inserts_missing_row_when_second_slot_unfilled():
    """Greedy can skip a nested 2nd pizza row; backstop must force ACTION REQUIRED."""
    gid = "pizza-gid"
    shared = [
        {"name": '16" Margherita', "menuModifierId": "m1", "menuModifierGroupId": gid},
        {"name": '16" London', "menuModifierId": "m2", "menuModifierGroupId": gid},
    ]
    groups = [
        {
            "name": "Please select your first pizza",
            "description": 'MD3 - 1st 16" Pizza Type',
            "options": shared,
        },
        {
            "name": "Please select your second pizza",
            "description": 'MD3 - 2nd 16" Pizza Type',
            "options": shared,
        },
    ]
    op = {
        "name": "Meal Deal 3",
        "categoryName": "Meal Deals",
        "printable_groups": groups,
    }
    item = {
        "name": "Meal Deal 3",
        "options": [
            {"name": '16" Margherita', "menuModifierId": "m1", "menuModifierGroupId": gid}
        ],
    }
    assert deal_structured_line_pizza_slots_incomplete_message(item, op) is not None
    missing_required: list = []
    _deal_backstop_unfilled_numbered_pizza_missing_row(
        item, groups, op, {}, missing_required
    )
    assert len(missing_required) == 1
    assert "second" in (missing_required[0][0] or "").lower()
    assert missing_required[0][5] == 1


def test_pizza_slot_simulation_orders_slots_one_flavour_one_slot():
    """Union of opt_names must not make two cart rows count as two slots without simulation."""
    gid = "pizza-gid"
    shared = [
        {"name": '16" Margherita', "menuModifierId": "m1", "menuModifierGroupId": gid},
        {"name": '16" London', "menuModifierId": "m2", "menuModifierGroupId": gid},
    ]
    groups = [
        {
            "name": "Please select your first pizza",
            "description": 'MD3 - 1st 16" Pizza Type',
            "options": shared,
        },
        {
            "name": "Please select your second pizza",
            "description": 'MD3 - 2nd 16" Pizza Type',
            "options": shared,
        },
    ]
    item = {
        "name": "Meal Deal 3",
        "options": [
            {"name": '16" Margherita', "menuModifierId": "m1", "menuModifierGroupId": gid}
        ],
    }
    filled, unfilled = _deal_numbered_pizza_slot_fill_state(item, groups)
    assert filled == 1
    assert len(unfilled) == 1
    assert _deal_pizza_flavour_pick_count_for_upsell(item, groups) == 1


def test_parmo_flavour_pick_count_same_modifier_twice_fills_two_slots():
    """Two cart rows for the same POS modifier can satisfy two printable rows (same flavour twice)."""
    op = {
        "printable_groups": [
            {
                "name": "Please select your first half parmo",
                "options": [
                    {"name": "Half Original", "menuModifierId": "m1", "id": "m1"}
                ],
            },
            {
                "name": "Please select your second half parmo",
                "options": [
                    {"name": "Half Original", "menuModifierId": "m1", "id": "m1"}
                ],
            },
        ],
    }
    item = {
        "options": [
            {"name": "Half Original", "menuModifierId": "m1"},
            {"name": "Half Original", "menuModifierId": "m1"},
        ]
    }
    assert _deal_parmo_flavour_pick_count(item, op) == 2


def test_parmo_backstop_inserts_missing_row_when_second_slot_unfilled():
    """Greedy can skip the 2nd half-parmo row; backstop must force ACTION REQUIRED."""
    gid = "parmo-gid"
    shared = [
        {"name": "Half Alpha", "menuModifierId": "m1", "menuModifierGroupId": gid},
        {"name": "Half Beta", "menuModifierId": "m2", "menuModifierGroupId": gid},
    ]
    groups = [
        {
            "name": "Please select your first half parmo",
            "description": "MD3 - First Parmo",
            "options": shared,
        },
        {
            "name": "Please select your second half parmo",
            "description": "MD3 - Second Parmo",
            "options": shared,
        },
    ]
    op = {
        "name": "Meal Deal 3",
        "categoryName": "Meal Deals",
        "printable_groups": groups,
    }
    item = {
        "name": "Meal Deal 3",
        "options": [
            {"name": "Half Alpha", "menuModifierId": "m1", "menuModifierGroupId": gid},
        ],
    }
    assert deal_structured_line_parmo_slots_incomplete_message(item, op) is not None
    missing_required: list = []
    _deal_backstop_unfilled_half_parmo_missing_row(
        item, groups, op, {}, missing_required
    )
    assert len(missing_required) == 1
    assert "second" in (missing_required[0][0] or "").lower()
    assert missing_required[0][5] == 1


def test_parmo_flavour_pick_count_two_distinct_modifiers_fills_two_slots():
    op = {
        "printable_groups": [
            {
                "name": "Please select your first half parmo",
                "options": [{"name": "Half Alpha", "menuModifierId": "a"}],
            },
            {
                "name": "Please select your second half parmo",
                "options": [{"name": "Half Beta", "menuModifierId": "b"}],
            },
        ],
    }
    item = {
        "options": [
            {"name": "Half Alpha", "menuModifierId": "a"},
            {"name": "Half Beta", "menuModifierId": "b"},
        ]
    }
    assert _deal_parmo_flavour_pick_count(item, op) == 2


def test_inch_size_option_rejects_volume_prefix_numbers():
    assert not _is_inch_based_size_option("330ml Pepsi Max")
    assert not _is_inch_based_size_option("500ml Coke")
    assert not _is_inch_based_size_option("3 Piece Chicken")


def test_inch_size_option_accepts_pizza_tiers():
    assert _is_inch_based_size_option('12" Margherita')
    assert _is_inch_based_size_option("Small")
    assert _is_inch_based_size_option("10 inch")


def test_size_display_names_only_when_all_tiers_normalize():
    """Do not append Small/Medium/Large to arbitrary meal-deal lines by position."""
    opts = [
        {"name": "Marinated Chicken With Chips"},
        {"name": "Donner Meal"},
        {"name": "Something Else"},
    ]
    assert _size_display_names_for_opts(opts) is None

