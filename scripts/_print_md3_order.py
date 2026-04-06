"""One-off: print Meal Deal 3 option order after _parse_order_text."""
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from src.agent import _parse_order_text
from src.int.poshub_service import pos_service

CART = [
    {
        "name": "Meal Deal 3",
        "qty": 1,
        "mods": [
            '16" Prosciutto Funghi',
            '16" Captain Inferno',
            "Standard Base",
            "BBQ Base",
            "Standard Crust",
            "Stuffed Crust",
            "Half Explosive Parmo & Chips",
            "Half Donner Baked In Parmo & Chips",
            "Salad",
            "Salad",
            "Chilli Dip",
            "Chilli Dip",
            "Chilli Dip",
            "Garlic Dip",
            "Garlic Dip",
            "Garlic Dip",
            "2x Bottles Of Coke",
        ],
    }
]


async def main() -> None:
    await pos_service.warmup()
    mapped, _, _, missing, _ = _parse_order_text(json.dumps(CART))
    if missing:
        print("MISSING", missing)
        return
    for mi in mapped:
        if mi.get("name") == "Meal Deal 3":
            for i, o in enumerate(mi.get("options") or []):
                print(f"{i+1:2d} {o.get('name')}")


if __name__ == "__main__":
    asyncio.run(main())
