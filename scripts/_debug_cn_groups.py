"""Debug script to inspect Couples Night deal structure after warmup."""
import asyncio, sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.int.poshub_service import pos_service
from src.agent import _parse_order_text

async def main():
    await pos_service.warmup()
    
    # Simulate the exact cart from the logs - with drink choice
    cart_with_drink = json.dumps([{
        "name": "Couples Night With 2x 500ml Soft Drinks",
        "qty": 1,
        "mods": [
            "12\" Prosciutto Funghi", "2x 500ml Bottle", "Bbq Base", 
            "Standard Crust", "12\" Philly Cheesesteak", "Standard Base", 
            "Stuffed Crust", "Chilli Dip", "Chips", "Potato Wedges", "BBQ Dip"
        ]
    }])
    
    print("=== PARSING CART WITH DRINK CHOICE ===")
    print(f"Input: {cart_with_drink[:200]}")
    mapped, total, bills, missing, dropped = await asyncio.to_thread(
        _parse_order_text, cart_with_drink, None
    )
    
    print(f"\nResult: mapped={len(mapped)} items, total={total}, missing={missing}, dropped={dropped}")
    if mapped:
        item = mapped[0]
        print(f"  Item: {item.get('name')}")
        print(f"  Options count: {len(item.get('options',[]))}")
        for i, opt in enumerate(item.get('options', [])):
            print(f"    Opt[{i}]: {opt.get('name')} id={str(opt.get('partnerId',''))[:20]}")
        
        # Check if drink option is in selected options
        drink_ids = {'a14db9b1-4a2c-42b3-8be8-b4a165d39302', 'f5d9061f-a3e2-444e-a889-a00993f4d251'}
        has_drink = any(
            str(opt.get('partnerId','')) in drink_ids or 
            str(opt.get('menuModifierId','')) in drink_ids 
            for opt in item.get('options', [])
        )
        print(f"\n  HAS DRINK OPTION: {has_drink}")
    
    print("\n=== SUGGESTION INSTRUCTION ===")
    for b in bills:
        print(f"  {b}")

asyncio.run(main())
