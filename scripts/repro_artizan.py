import asyncio
import os
import sys

# Add the current directory to sys.path to allow imports from src
sys.path.insert(0, r"c:\Users\zencloud\Downloads\PizzaGuys\Hybrid-Model")

from src.int.poshub_service import pos_service

def _is_pizza_product(p: dict) -> bool:
    """Duplicate logic from meal_deal_intent.py for debugging"""
    pgs = p.get("printable_groups") or []
    names = {str(g.get("name") or "").lower() for g in pgs}
    # Pizzas must have a size (inch/size), a base (base/sauce), and a crust group.
    has_size = any("size" in n or '"' in n or "inch" in n for n in names)
    has_base = any("base" in n or ("sauce" in n and "dip" not in n) for n in names)
    has_crust = any("crust" in n for n in names)
    
    # Check if category name suggests it's a pizza
    cat = (p.get("categoryName") or "").lower()
    is_pizza_cat = "pizza" in cat and "sides" not in cat and "deal" not in cat
    
    return (has_size and has_base and has_crust) or is_pizza_cat, {"size": has_size, "base": has_base, "crust": has_crust, "cat_pizza": is_pizza_cat}

async def debug_artizan():
    print("Warming up poshub_service...")
    await pos_service.warmup()
    
    artizan_cats = [c for c in {v.get("categoryName") for v in pos_service.available_lookup_index.values()} if c and "Artizan" in c]
    print(f"Artizan Categories Found: {artizan_cats}")
    
    for cat in artizan_cats:
        print(f"\n--- Category: {cat} ---")
        items = [v for v in pos_service.available_lookup_index.values() if v.get("categoryName") == cat]
        for p in items[:3]: # check first 3 items
            res, details = _is_pizza_product(p)
            pgs = p.get("printable_groups") or []
            group_names = [g.get("name") for g in pgs]
            print(f"Item: {p['name']}")
            print(f"  Groups: {group_names}")
            print(f"  _is_pizza_product: {res} (Details: {details})")

if __name__ == "__main__":
    asyncio.run(debug_artizan())
