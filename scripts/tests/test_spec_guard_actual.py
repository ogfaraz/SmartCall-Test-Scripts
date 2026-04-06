import asyncio
import os
import sys

# Add the current directory to sys.path to allow imports from src
sys.path.insert(0, os.getcwd())

from src.int.poshub_service import pos_service
from src.text_agent.tools import _message_has_specific_product_reference

async def main():
    await pos_service.warmup()
    
    test_cases = [
        "add a donner pizza",
        "add a meal deal 3",
        "add a medium hawaiian pizza",
        "add pizza",
        "meal deal",
        "donner pizza"
    ]
    
    for tc in test_cases:
        res = _message_has_specific_product_reference(tc)
        print(f"Result for '{tc}': {res}")

if __name__ == "__main__":
    asyncio.run(main())
