#!/usr/bin/env python3
"""
Inspect Meal Deal SKUs from POSHub (cached menu after warmup).

Usage (from repo root, with .env / credentials configured as for the main app):

  python scripts/dump_meal_deal_structures.py
  python scripts/dump_meal_deal_structures.py --name "Meal Deal 3"

Requires a successful menu sync (same as the running server). Offline: ensure
MENU_INDEX or disk cache was populated by a prior API sync.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


async def _main() -> None:
    from src.int.poshub_service import pos_service

    p = argparse.ArgumentParser(description="Dump meal deal printable_groups / constraints")
    p.add_argument(
        "--name",
        help="Filter: product name contains this (case-insensitive)",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit full product dict as JSON (large)",
    )
    args = p.parse_args()

    await pos_service.warmup()
    if not pos_service.is_ready:
        print("POS service not ready — check API credentials and network.", file=sys.stderr)
        sys.exit(1)

    needle = (args.name or "").strip().lower()
    shown = 0
    for _k, prod in pos_service.available_lookup_index.items():
        name = (prod.get("name") or "").strip()
        if "meal deal" not in name.lower():
            continue
        if needle and needle not in name.lower():
            continue
        shown += 1
        print("=" * 72)
        print(name)
        print(f"  partnerId={prod.get('partnerId')}  category={prod.get('categoryName')}")
        groups = prod.get("printable_groups") or []
        print(f"  printable_groups: {len(groups)} rows")
        for i, g in enumerate(groups):
            gn = (g.get("name") or "")[:80]
            gid = g.get("menuModifierGroupId") or g.get("id") or ""
            nopt = len(g.get("options") or [])
            print(f"    [{i}] {gn!r}  gid={gid}  options={nopt}")
        gc = prod.get("group_constraints") or {}
        if gc:
            print(f"  group_constraints keys: {len(gc)}")
            for gk, gv in list(gc.items())[:12]:
                print(f"    {gk}: min={gv.get('min')} max={gv.get('max')}")
            if len(gc) > 12:
                print("    ...")
        if args.json:
            slim = {k: prod.get(k) for k in ("name", "partnerId", "categoryName", "printable_groups", "group_constraints", "modifier_lookup")}
            print(json.dumps(slim, indent=2, default=str)[:24000])

    print("=" * 72)
    print(f"Total meal-deal SKUs listed: {shown}")


if __name__ == "__main__":
    asyncio.run(_main())
