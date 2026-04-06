"""Phase-2 resolution: Parmo Wrap (Wrap It Up) vs Parmo Time Wraps SKUs."""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.agent import (
    _phase2_exact_display_name_match,
    _phase2_parmo_wrap_cross_category,
    _phase2_union_lookup_for_parmo_wrap,
)


def test_exact_display_name_prefers_parmo_wrap_line():
    lookup = {
        "a": {
            "name": "Parmo Wrap",
            "categoryName": "Wrap It Up",
            "price": 7.99,
        },
        "b": {
            "name": "Wrapped Donner Parmo",
            "categoryName": "Parmo Time Wraps",
            "price": 11.38,
        },
    }
    hit = _phase2_exact_display_name_match("Parmo Wrap", lookup)
    assert hit is not None
    assert hit["name"] == "Parmo Wrap"
    assert hit["categoryName"] == "Wrap It Up"


def test_cross_category_uses_merged_lookup_when_live_omits_wrap_it_up():
    """Live may only expose Parmo Time Wraps; full menu still has Wrap It Up Parmo Wrap."""
    live = {
        "x": {
            "name": "Wrapped Donner Parmo",
            "categoryName": "Parmo Time Wraps",
            "price": 11.38,
        },
    }
    cached = {
        "y": {
            "name": "Parmo Wrap",
            "categoryName": "Wrap It Up",
            "price": 7.99,
        },
    }
    merged = _phase2_union_lookup_for_parmo_wrap(live, cached)
    cats = ["Wrap It Up", "Parmo Time Wraps"]
    missing = []
    picked, amb = _phase2_parmo_wrap_cross_category(
        "parmo wrap", merged, cats, missing
    )
    assert not amb
    assert picked is not None
    assert picked["name"] == "Parmo Wrap"
    assert picked["categoryName"] == "Wrap It Up"


def test_cross_category_parmo_wrap_beats_wrapped_donner_parmo():
    """Fuzzy cache must not prefer 'Wrapped Donner Parmo' when 'Parmo Wrap' exists."""
    lookup = {
        "a": {
            "name": "Parmo Wrap",
            "categoryName": "Wrap It Up",
            "price": 7.99,
        },
        "b": {
            "name": "Wrapped Donner Parmo",
            "categoryName": "Parmo Time Wraps",
            "price": 11.38,
        },
    }
    cats = ["Wrap It Up", "Parmo Time Wraps"]
    missing = []
    picked, amb = _phase2_parmo_wrap_cross_category(
        "parmo wrap", lookup, cats, missing
    )
    assert not amb
    assert picked is not None
    assert picked["name"] == "Parmo Wrap"
    assert missing == []


def test_cross_category_wrapped_flavour_clear_winner():
    """Explicit flavour beats sibling 'Wrapped … Parmo' lines."""
    lookup = {
        "a": {
            "name": "Wrapped Alpha Parmo",
            "categoryName": "Parmo Time Wraps",
            "price": 11.0,
        },
        "b": {
            "name": "Wrapped Beta Parmo",
            "categoryName": "Parmo Time Wraps",
            "price": 11.0,
        },
    }
    cats = ["Wrap It Up", "Parmo Time Wraps"]
    missing = []
    picked, amb = _phase2_parmo_wrap_cross_category(
        "wrapped alpha parmo", lookup, cats, missing
    )
    assert picked is not None
    assert picked["name"] == "Wrapped Alpha Parmo"
    assert not amb


def test_cross_category_vague_wrapped_parmo_prompts_two_options():
    """Vague phrase with two close fuzzy scores → choose line, no silent pick."""
    lookup = {
        "a": {
            "name": "Wrapped Donner Parmo",
            "categoryName": "Parmo Time Wraps",
        },
        "b": {
            "name": "Wrapped Mushroom Parmo",
            "categoryName": "Parmo Time Wraps",
        },
    }
    cats = ["Parmo Time Wraps", "Wrap It Up"]
    missing = []
    picked, amb = _phase2_parmo_wrap_cross_category(
        "wrapped parmo", lookup, cats, missing
    )
    assert picked is None
    assert amb
    assert len(missing) == 1
    assert "Wrapped Donner Parmo" in missing[0]
    assert "Wrapped Mushroom Parmo" in missing[0]
