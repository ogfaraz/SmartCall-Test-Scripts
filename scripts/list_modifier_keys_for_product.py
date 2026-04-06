"""
Print modifier_lookup keys for a product name (fuzzy match). Useful for chips / deal SKUs.

  .venv\\Scripts\\python.exe scripts/list_modifier_keys_for_product.py "Meal Deal 6"
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


async def _run(name: str) -> None:
    from rapidfuzz import fuzz, process
    from src.int.poshub_service import pos_service

    await pos_service.warmup()
    idx = pos_service.available_lookup_index or {}
    keys = [str(v.get("name") or "") for v in idx.values() if v.get("name")]
    match = process.extractOne(name, keys, scorer=fuzz.WRatio)
    if not match:
        print("No match")
        return
    picked, score, _ = match
    print(f"Matched: {picked!r} (score={score})")
    obj = next(v for v in idx.values() if (v.get("name") or "") == picked)
    ml = obj.get("modifier_lookup") or {}
    for k in sorted(ml.keys(), key=str):
        kl = str(k).lower()
        if "chip" in kl or "chips" in kl:
            print(f"  [chips-like] {k!r}")
    print(f"Total modifier keys: {len(ml)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("name", nargs="?", default="Meal Deal 3")
    args = ap.parse_args()
    asyncio.run(_run(args.name))


if __name__ == "__main__":
    main()
