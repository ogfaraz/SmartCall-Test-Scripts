"""Wrap It Up + Parmo Time Wraps merged listing (order_flow + meal_deal_intent)."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.int.meal_deal_intent import (
    build_combined_wrap_option_list,
    should_merge_wrap_categories_for_listing,
)
from src.order_flow import process_missing_items


def test_should_merge_requires_all_wrap_named_categories():
    assert should_merge_wrap_categories_for_listing(
        ["Wrap It Up", "Parmo Time Wraps"]
    )
    assert not should_merge_wrap_categories_for_listing(["Wrap It Up", "Pizzas"])
    assert not should_merge_wrap_categories_for_listing(["Wrap It Up"])


def test_build_combined_wrap_union():
    pos = MagicMock()
    pos.available_lookup_index = {
        "a": {"name": "Zebra Wrap", "categoryName": "Wrap It Up"},
        "b": {"name": "Parmo Wrap", "categoryName": "Parmo Time Wraps"},
        "c": {"name": "Zebra Wrap", "categoryName": "Wrap It Up"},
    }
    out = build_combined_wrap_option_list(
        pos, ["Wrap It Up", "Parmo Time Wraps"]
    )
    assert set(out) == {"Zebra Wrap", "Parmo Wrap"}
    assert out == sorted(out, key=str.lower)


def test_process_missing_items_merges_wrap_siblings():
    pos = MagicMock()
    pos.cached_categories = ["Wrap It Up", "Parmo Time Wraps", "Pizzas"]
    pos.available_lookup_index = {
        "a": {"name": "Chicken Wrap", "categoryName": "Wrap It Up"},
        "b": {"name": "Parmo Wrap", "categoryName": "Parmo Time Wraps"},
    }
    pos.cached_lookup_index = pos.available_lookup_index

    missing = ["Chicken Wrap (category)"]
    msg, pending, stock, rules = process_missing_items(missing, pos)
    assert msg is not None
    assert "wraps menu" in msg.lower() or "chicken wrap" in msg.lower()
    assert pending is not None
    assert len(pending) == 2
    assert "Wrap It Up" in pending and "Parmo Time Wraps" in pending


def test_process_missing_items_exact_pizzas_merges_all_pizza_categories():
    pos = MagicMock()
    pos.cached_categories = [
        "Pizzas",
        "New Artizan Pizzas",
        "Meal Deals",
        "Brand New Meal Deals",
    ]
    pos.available_lookup_index = {
        "a": {"name": "Donner Pizza", "categoryName": "Pizzas"},
        "b": {"name": "12\" Hot Buzz Artizan Pizzas", "categoryName": "New Artizan Pizzas"},
        "c": {"name": "Margherita Pizza", "categoryName": "Pizzas"},
    }
    pos.cached_lookup_index = pos.available_lookup_index

    msg, pending, stock, rules = process_missing_items(["Pizzas"], pos)
    assert stock == [] and rules == []
    assert msg is not None
    assert "all pizza categories combined" in msg.lower()
    assert "Donner Pizza" in msg
    assert "12\" Hot Buzz Artizan Pizzas" in msg
    assert pending == ["Pizzas"]


def test_process_missing_items_exact_meal_deals_merges_brand_new_category():
    pos = MagicMock()
    pos.cached_categories = [
        "Pizzas",
        "Meal Deals",
        "Brand New Meal Deals",
    ]
    pos.available_lookup_index = {
        "a": {"name": "Meal Deal 1", "categoryName": "Meal Deals"},
        "b": {"name": "Meal Deal 2", "categoryName": "Meal Deals"},
        "c": {"name": "Couples Night With Bottle Wine", "categoryName": "Brand New Meal Deals"},
        "d": {"name": "Feed The Fam", "categoryName": "Brand New Meal Deals"},
    }
    pos.cached_lookup_index = pos.available_lookup_index

    msg, pending, stock, rules = process_missing_items(["Meal Deals"], pos)
    assert stock == [] and rules == []
    assert msg is not None
    assert "meal deal menu" in msg.lower()
    assert "Meal Deal 1" in msg
    assert "Couples Night With Bottle Wine" in msg
    assert pending == ["Meal Deals"]


def test_process_missing_items_generic_pizza_merges_sibling_categories():
    pos = MagicMock()
    pos.cached_categories = ["Pizzas", "New Artizan Pizzas", "Meal Deals"]
    pos.available_lookup_index = {
        "a": {"name": "Donner Pizza", "categoryName": "Pizzas"},
        "b": {"name": "12\" Hot Buzz Artizan Pizzas", "categoryName": "New Artizan Pizzas"},
    }
    pos.cached_lookup_index = pos.available_lookup_index

    msg, pending, stock, rules = process_missing_items(["Pizza"], pos)
    assert stock == [] and rules == []
    assert msg is not None
    assert "options (numbered)" in msg
    assert "Donner Pizza" in msg
    assert "12\" Hot Buzz Artizan Pizzas" in msg
    assert pending is not None and len(pending) == 1


def test_process_missing_items_generic_meal_deal_merges_sibling_categories():
    pos = MagicMock()
    pos.cached_categories = ["Meal Deals", "Brand New Meal Deals", "Pizzas"]
    pos.available_lookup_index = {
        "a": {"name": "Meal Deal 1", "categoryName": "Meal Deals"},
        "b": {"name": "Meal Deal 2", "categoryName": "Meal Deals"},
        "c": {"name": "Feed The Fam", "categoryName": "Brand New Meal Deals"},
    }
    pos.cached_lookup_index = pos.available_lookup_index

    msg, pending, stock, rules = process_missing_items(["meal deal"], pos)
    assert stock == [] and rules == []
    assert msg is not None
    assert "options (numbered)" in msg
    assert "Meal Deal 1" in msg
    assert "Feed The Fam" in msg
    assert pending is not None and len(pending) == 1
