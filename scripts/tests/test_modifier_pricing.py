"""Modifier link pricing and duplicate-name lists (POSHub menu harvest)."""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.int.poshub_service import POSHubService


def test_modifier_link_price_prefers_link_price():
    assert (
        POSHubService.modifier_link_price_pence(
            {"price": 150, "inStorePrice": 0},
            {"price": 0},
        )
        == 150
    )


def test_modifier_link_price_falls_back_to_in_store_when_price_missing():
    assert (
        POSHubService.modifier_link_price_pence(
            {"inStorePrice": 88},
            {"price": 0},
        )
        == 88
    )


def test_modifier_link_price_catalog_when_link_empty():
    assert (
        POSHubService.modifier_link_price_pence(
            None,
            {"price": 199},
        )
        == 199
    )


def test_modifier_link_price_zero_is_valid():
    assert (
        POSHubService.modifier_link_price_pence(
            {"price": 0, "inStorePrice": 50},
            {"price": 999},
        )
        == 0
    )
