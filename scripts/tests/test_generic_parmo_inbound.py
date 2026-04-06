"""Inbound SMS classifier: bare 'parmo' vs explicit variant (agent._inbound_is_generic_parmo_only)."""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.agent import (
    _default_wrap_it_up_category,
    _default_wrap_parmo_category,
    _inbound_is_generic_parmo_only,
    _inbound_requests_generic_parmo_wrap,
    _inbound_requests_wrapped_parmo_variant,
    _llm_line_is_flavoured_parmo_wrap_hallucination,
    _resolve_parmo_wrap_product_wrap_it_up,
    _wrapped_parmo_query_from_inbound,
)


def test_bare_parmo_phrases_match():
    assert _inbound_is_generic_parmo_only("parmo")
    assert _inbound_is_generic_parmo_only("add parmo")
    assert _inbound_is_generic_parmo_only("add a parmo")
    assert _inbound_is_generic_parmo_only("  Add a parmo  ")
    assert _inbound_is_generic_parmo_only("please add a parmo")
    assert _inbound_is_generic_parmo_only("just parmo")


def test_explicit_variant_or_context_rejects():
    assert not _inbound_is_generic_parmo_only("explosive parmo")
    assert not _inbound_is_generic_parmo_only("add an explosive parmo")
    assert not _inbound_is_generic_parmo_only("add a x large parmo with salad")
    assert not _inbound_is_generic_parmo_only("original parmo")
    assert not _inbound_is_generic_parmo_only("wrapped parmo")
    assert not _inbound_is_generic_parmo_only("parmo pizza")


def test_empty_or_none():
    assert not _inbound_is_generic_parmo_only(None)
    assert not _inbound_is_generic_parmo_only("")


def test_parmo_wrap_is_not_generic_bare_parmo():
    """Explicit wrap intent must not trigger Original-Parmo SMS override."""
    assert not _inbound_is_generic_parmo_only("parmo wrap")
    assert not _inbound_is_generic_parmo_only("add a parmo wrap")
    assert not _inbound_is_generic_parmo_only("wrapped explosive parmo")


def test_short_query_falls_back_to_wrap_it_up_when_no_combined_parmo_wraps_category():
    """API may only expose Wrap It Up + Parmo Time — no 'Parmo Time Wraps' category name."""
    cats = ["Pizzas", "Parmo Time", "Wrap It Up"]
    assert _default_wrap_parmo_category(cats) is None
    assert _default_wrap_it_up_category(cats) == "Wrap It Up"


def test_inbound_generic_parmo_wrap_detects_plain_request():
    assert _inbound_requests_generic_parmo_wrap("add parmo wrap")
    assert _inbound_requests_generic_parmo_wrap("add a parmo wrap")
    assert _inbound_requests_generic_parmo_wrap("parmo wrap")
    assert not _inbound_requests_generic_parmo_wrap("wrapped parmo")
    assert not _inbound_requests_generic_parmo_wrap("add 2 wrapped explosive parmo")
    assert not _inbound_requests_generic_parmo_wrap("add chorizo parmo wrap")
    assert not _inbound_requests_generic_parmo_wrap("add parmo")


def test_wrapped_parmo_variant_detection_and_query_builder():
    assert _inbound_requests_wrapped_parmo_variant("wrapped parmo")
    assert _inbound_requests_wrapped_parmo_variant("add 2 wrapped explosive parmo")
    assert not _inbound_requests_wrapped_parmo_variant("add a parmo wrap")
    assert not _inbound_requests_wrapped_parmo_variant("add explosive parmo wrap")

    assert (
        _wrapped_parmo_query_from_inbound("add 2 wrapped explosive parmo", [])
        == "wrapped explosive parmo"
    )
    assert (
        _wrapped_parmo_query_from_inbound("wrapped parmo", ["Make It Doner"])
        == "wrapped donner parmo"
    )
    assert _wrapped_parmo_query_from_inbound("add a parmo wrap", ["Make It Explosive"]) is None


def test_flavoured_parmo_wrap_hallucination_pattern():
    assert _llm_line_is_flavoured_parmo_wrap_hallucination("Chorizo Parmo Wrap")
    assert _llm_line_is_flavoured_parmo_wrap_hallucination("Mushroom Parmo Wrap")
    assert not _llm_line_is_flavoured_parmo_wrap_hallucination("Parmo Wrap")
    assert not _llm_line_is_flavoured_parmo_wrap_hallucination("Wrapped Chorizo Parmo")


def test_resolve_parmo_wrap_under_wrap_it_up():
    cats = ["Wrap It Up", "Parmo Time"]
    lookup = {
        "k1": {"name": "Parmo Wrap", "categoryName": "Wrap It Up"},
        "k2": {"name": "Chicken Wrap", "categoryName": "Wrap It Up"},
        "k3": {"name": "Explosive Parmo Wrap", "categoryName": "Wrap It Up"},
    }
    picked = _resolve_parmo_wrap_product_wrap_it_up(
        cats, "parmo wrap", [], lookup
    )
    assert picked and picked.get("name") == "Parmo Wrap"
    exp = _resolve_parmo_wrap_product_wrap_it_up(
        cats, "explosive parmo wrap", ["explosive"], lookup
    )
    assert exp and exp.get("name") == "Explosive Parmo Wrap"

