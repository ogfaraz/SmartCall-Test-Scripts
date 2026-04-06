import asyncio
import os
import sys

# Add the current directory to sys.path to allow imports from src
sys.path.insert(0, os.getcwd())

from src.int.poshub_service import pos_service
from src.int.meal_deal_intent import get_all_pizza_category_names

async def verify_fix():
    print("Warming up poshub_service...")
    await pos_service.warmup()
    
    pizza_cats = get_all_pizza_category_names(pos_service)
    print(f"Unified Pizza Categories: {pizza_cats}")
    
    target = "New Artizan Pizzas"
    if target in pizza_cats:
        print(f"SUCCESS: '{target}' found in unified pizza categories!")
    else:
        print(f"FAILURE: '{target}' still missing from unified pizza categories.")
        
    # Check if there are any other pizza categories correctly included
    standard = "Pizzas"
    if standard in pizza_cats:
        print(f"INFO: '{standard}' correctly included.")

if __name__ == "__main__":
    asyncio.run(verify_fix())
