"""Printable-group–scoped modifier matching (IDs + prices from menu rows)."""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.agent import _try_match_modifier_printable_group_scoped


def _sample_product_two_rows():
    return {
        "printable_groups": [
            {
                "name": "Pizza",
                "min": 1,
                "max": 1,
                "options": [
                    {
                        "name": '12" Margherita',
                        "price": 0,
                        "menuModifierId": "mod-pizza-1",
                        "menuModifierGroupId": "grp-pizza",
                        "modifierGroupName": "Pizza",
                    },
                ],
                "required_parent": None,
            },
            {
                "name": "Base",
                "min": 1,
                "max": 1,
                "options": [
                    {
                        "name": "BBQ Base",
                        "price": 99,
                        "menuModifierId": "mod-base-1",
                        "menuModifierGroupId": "grp-base",
                        "modifierGroupName": "Base",
                    },
                ],
                "required_parent": None,
            },
        ],
    }


def test_scoped_prefers_earliest_row_with_capacity():
    pd = _sample_product_two_rows()
    picks = [0, 0]
    sel = set()
    hit, slot = _try_match_modifier_printable_group_scoped(
        "margherita", pd, picks, sel, min_score=65
    )
    assert hit is not None
    assert hit["menuModifierId"] == "mod-pizza-1"
    assert hit["menuModifierGroupId"] == "grp-pizza"
    assert slot == 0
    picks[0] += 1
    hit2, slot2 = _try_match_modifier_printable_group_scoped(
        "bbq base", pd, picks, sel, min_score=65
    )
    assert hit2 is not None
    assert hit2["menuModifierId"] == "mod-base-1"
    assert hit2["price"] == 99
    assert slot2 == 1


def test_scoped_respects_parent_gate():
    pd = {
        "printable_groups": [
            {
                "name": "Child",
                "min": 1,
                "max": 1,
                "options": [
                    {
                        "name": "Extra Cheese",
                        "price": 50,
                        "menuModifierId": "mod-ch",
                        "menuModifierGroupId": "grp-ch",
                        "modifierGroupName": "Topping",
                    },
                ],
                "required_parent": "parent-mod-id",
            },
        ],
    }
    picks = [0]
    sel = set()
    hit, _ = _try_match_modifier_printable_group_scoped(
        "cheese", pd, picks, sel, min_score=65
    )
    assert hit is None
    sel.add("parent-mod-id")
    hit2, slot = _try_match_modifier_printable_group_scoped(
        "cheese", pd, picks, sel, min_score=65
    )
    assert hit2 is not None
    assert hit2["menuModifierId"] == "mod-ch"
    assert slot == 0
