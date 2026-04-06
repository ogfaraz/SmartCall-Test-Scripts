import asyncio
import os
import sys

# Add the current directory to sys.path to allow imports from src
sys.path.insert(0, os.getcwd())

from src.int.poshub_service import pos_service
from src.int.meal_deal_intent import _is_pizza_product

async def main():
    await pos_service.warmup()
    all_items = pos_service.available_lookup_index.values()
    artizan_pizzas = [p for p in all_items if "Artizan" in (p.get("categoryName") or "")]
    
    print(f"Checking {len(artizan_pizzas)} Artizan items...")
    for p in artizan_pizzas[:10]:
        pgs = p.get("printable_groups") or []
        group_names = [g.get("name") or "" for g in pgs]
        is_pizza = _is_pizza_product(p)
        print(f"Item: {p.get('name')}")
        print(f"  Category: {p.get('categoryName')}")
        print(f"  Groups: {group_names}")
        print(f"  _is_pizza_product: {is_pizza}")
        
        # Breakdown of the check
        names = {str(n).lower() for n in group_names}
        has_size = any("size" in n or '"' in n or "inch" in n for n in names)
        has_base = any("base" in n or ("sauce" in n and "dip" not in n) for n in names)
        has_crust = any("crust" in n for n in names)
        print(f"  Check: size={has_size}, base={has_base}, crust={has_crust}")
        print("-" * 20)

if __name__ == "__main__":
    asyncio.run(main())
