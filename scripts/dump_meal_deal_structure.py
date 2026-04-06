"""
Dump printable_groups + group_constraints for Meal Deal SKUs from the live POS menu.

Requires POSHUB_* env vars (same as the app). Run from repo root:

    .venv\\Scripts\\python.exe scripts\\dump_meal_deal_structure.py
    .venv\\Scripts\\python.exe scripts\\dump_meal_deal_structure.py "Meal Deal 6"
"""
import asyncio
import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv(_ROOT / ".env")

from src.int.poshub_service import pos_service


async def main():
    name_filter = (sys.argv[1] if len(sys.argv) > 1 else "").strip().lower() or "meal deal"
    await pos_service.warmup()
    if not pos_service.available_lookup_index:
        print("No menu loaded — check POSHUB_* credentials.")
        return
    for p in pos_service.available_lookup_index.values():
        nm = str(p.get("name") or "")
        if name_filter not in nm.lower():
            continue
        print("=" * 72)
        print(nm)
        print("category:", p.get("categoryName"))
        gc = p.get("group_constraints") or {}
        for i, g in enumerate(p.get("printable_groups") or []):
            gid = str(g.get("menuModifierGroupId") or g.get("id") or "")
            cmin = cmax = None
            if gid and isinstance(gc.get(gid), dict):
                cmin = gc[gid].get("min")
                cmax = gc[gid].get("max")
            print(
                f"  [{i}] {g.get('name')!r}  min={g.get('min')} max={g.get('max')} "
                f"constraints=({cmin},{cmax}) desc={str(g.get('description') or '')[:80]!r}"
            )
            for o in (g.get("options") or [])[:6]:
                print(f"       - {o.get('name')!r}")
            nrest = len(g.get("options") or []) - 6
            if nrest > 0:
                print(f"       ... +{nrest} more options")
        print()


if __name__ == "__main__":
    asyncio.run(main())
