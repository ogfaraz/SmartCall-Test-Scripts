"""One-off: print Meal Deal 6 printable_groups from live POS menu."""
import asyncio
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.int.poshub_service import pos_service


async def main():
    await pos_service.warmup()
    idx = pos_service.cached_lookup_index or {}
    v = idx.get("meal deal 6")
    if not v:
        for vv in idx.values():
            if isinstance(vv, dict) and str(vv.get("name", "")).strip().lower() == "meal deal 6":
                v = vv
                break
    if not v:
        print("NOT FOUND")
        return
    print("name:", v.get("name"))
    print("price_pence:", v.get("price"))
    pg = v.get("printable_groups") or []
    print("printable_groups:", len(pg))
    for i, g in enumerate(pg):
        opts = g.get("options") or []
        desc = (g.get("description") or "")[:80]
        print(f"  [{i}] group={g.get('name')!r} desc={desc!r} n_opts={len(opts)}")
        if opts and len(opts) <= 6:
            for o in opts:
                print("      ", o.get("name"))
        elif opts:
            for o in opts[:4]:
                print("      ", o.get("name"))
            print(f"       ... +{len(opts) - 4} more")


if __name__ == "__main__":
    asyncio.run(main())
