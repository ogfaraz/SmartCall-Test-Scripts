import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from src.agent import (
    _classify_deal_mod_string,
    _deal_parmo_slot_option_names_lower,
    _deal_pizza_option_names_lower,
    _deal_printable_mod_sets,
    _reorder_deal_string_mods_for_matching,
)
from src.int.poshub_service import pos_service
from src.int.deal_structured_flow import is_deal_structured_product


async def main() -> None:
    await pos_service.warmup()
    md = None
    for v in pos_service.cached_lookup_index.values():
        if (v.get("name") or "").strip() == "Meal Deal 3":
            md = v
            break
    assert md and is_deal_structured_product(md)
    mods = [
        '16" Prosciutto Funghi',
        '16" Captain Inferno',
        "Standard Base",
        "BBQ Base",
        "Standard Crust",
        "Stuffed Crust",
    ]
    pn = _deal_pizza_option_names_lower(md)
    pr = _deal_parmo_slot_option_names_lower(md)
    _, b, c = _deal_printable_mod_sets(md)
    for m in mods:
        k = _classify_deal_mod_string(m, pn, pr, b, c)
        print(repr(m), "->", k)
    out = _reorder_deal_string_mods_for_matching(mods, md)
    print("OUT", out)


if __name__ == "__main__":
    asyncio.run(main())
