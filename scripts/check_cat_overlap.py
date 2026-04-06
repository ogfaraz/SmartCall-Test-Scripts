import asyncio
import os
import sys

# Add the current directory to sys.path to allow imports from src
sys.path.insert(0, os.getcwd())

from src.int.poshub_service import pos_service
from src.int.meal_deal_intent import _is_pizza_product, _is_meal_deal_product

async def check_overlap():
    await pos_service.warmup()
    all_items = list(pos_service.available_lookup_index.values())
    
    overlap_items = [p['name'] for p in all_items if _is_pizza_product(p) and _is_meal_deal_product(p)]
    print(f"Items that are BOTH pizza and meal deal: {overlap_items}")
    
    pizza_cats = {p.get('categoryName') for p in all_items if _is_pizza_product(p)}
    meal_cats = {p.get('categoryName') for p in all_items if _is_meal_deal_product(p)}
    
    print(f"Pizza Categories: {pizza_cats}")
    print(f"Meal Deal Categories: {meal_cats}")
    
    cat_overlap = pizza_cats.intersection(meal_cats)
    print(f"Categories that have BOTH: {cat_overlap}")
    
    if cat_overlap:
        for cat in cat_overlap:
            items_in_cat = [p['name'] for p in all_items if p.get('categoryName') == cat]
            pizzas = [p['name'] for p in all_items if p.get('categoryName') == cat and _is_pizza_product(p)]
            deals = [p['name'] for p in all_items if p.get('categoryName') == cat and _is_meal_deal_product(p)]
            print(f"\nCategory: {cat}")
            print(f"  Pizzas predicted: {pizzas}")
            print(f"  Deals predicted: {deals}")
            print(f"  Total items: {items_in_cat}")

if __name__ == "__main__":
    asyncio.run(check_overlap())
