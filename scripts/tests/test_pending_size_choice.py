"""Pending required-choice: garlic-bread style Small/Medium/Large + pending item names."""
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.agent import (
    _cart_line_matches_pending_item,
    _opts_look_like_small_medium_large_labels,
)
from src.text_agent.tools import (
    _cart_line_matches_pending_item as _cart_match_tools,
    _inject_inbound_pending_required_choice,
    _opts_look_like_small_medium_large_labels as _sml_tools,
    _rebuild_cart_with_pending_choice_mods,
)


def test_small_medium_large_labels_detects_garlic_style_opts():
    opts = ['Small (10")', 'Medium (12")', 'Large (16")']
    assert _opts_look_like_small_medium_large_labels(opts)
    assert _sml_tools(opts)


def test_pending_item_fuzzy_matches_speak_line():
    assert _cart_line_matches_pending_item("Garlic Bread", "2 garlic breads")
    assert _cart_match_tools("Garlic Bread", "2 garlic breads")
    assert not _cart_line_matches_pending_item("Pizza", "2 garlic breads")


def test_rebuild_only_last_duplicate_line_gets_mods():
    prev = [
        {"name": "Garlic Bread", "qty": 2, "mods": []},
        {"name": "Garlic Bread", "qty": 2, "mods": ["old"]},
    ]
    merged = ['Large (16")']
    out = _rebuild_cart_with_pending_choice_mods(
        prev,
        merged,
        "2 garlic breads",
        "Garlic Bread",
    )
    assert out[0]["mods"] == []
    assert out[1]["mods"] == merged


def test_inject_pending_choice_targets_unresolved_duplicate_line():
    prev = [
        {"name": "Donner Pizza", "qty": 1, "mods": ["BBQ Base"]},
        {"name": "Donner Pizza", "qty": 1, "mods": ['16"']},
    ]
    md = {
        "pending_required_choice": {
            "item": "donner pizza",
            "options": ['10"', '12"', '16"'],
        },
        "_last_inbound_sms": "3",
        "canonical_cart_json": json.dumps(prev),
        "last_quoted_items": json.dumps(prev),
    }
    out = _inject_inbound_pending_required_choice(json.dumps(prev), md)
    parsed = json.loads(out)
    bbq = next(
        x
        for x in parsed
        if any(str(m).strip().lower() == "bbq base" for m in (x.get("mods") or []))
    )
    assert any('16"' in str(m) for m in (bbq.get("mods") or []))
