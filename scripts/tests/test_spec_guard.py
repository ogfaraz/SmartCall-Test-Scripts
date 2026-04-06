import asyncio
import os
import sys

# Add the current directory to sys.path to allow imports from src
sys.path.insert(0, os.getcwd())

from src.int.poshub_service import pos_service
from rapidfuzz import fuzz, process
import re

def _intent_tokens(text: str) -> list[str]:
    _LISTING_FILLER_WORDS = {
        "a", "an", "the", "i", "me", "my", "to", "for", "of", "on", "in", "at",
        "and", "or", "please", "pls", "plz", "can", "could", "would", "want", "like",
        "add", "get", "give", "order", "show", "list", "menu", "options", "option",
        "items", "item", "choices", "choice", "them", "em", "again", "all",
    }
    toks = []
    for t in re.findall(r"[a-z0-9]+", (text or "").lower()):
        if len(t) <= 1:
            continue
        if t in _LISTING_FILLER_WORDS:
            continue
        toks.append(t[:-1] if t.endswith("s") and len(t) > 3 else t)
    return toks

def _message_has_specific_product_reference(msg: str, product_names: list[str]) -> bool:
    toks = _intent_tokens(msg)
    if len(toks) < 2:
        return False
    generic_tokens = {
        "pizza", "meal", "deal", "wrap", "burger", "drink", "dessert", "side", "parmo"
    }
    if set(toks).issubset(generic_tokens):
        return False
    query = " ".join(toks)
    print(f"DEBUG: product_names type={type(product_names)} len={len(product_names)}")
    hits = process.extract(query, product_names, scorer=fuzz.token_set_ratio, limit=5)
    print(f"DEBUG: Manually checking 'Donner Pizza' vs 'donner pizza'")
    r = fuzz.token_set_ratio("donner pizza", "Donner Pizza")
    print(f"DEBUG: Result = {r}")
    
    for name, score, _idx in hits:
        print(f"DEBUG: Query='{query}' Hit='{name}' Score={score}")
    
    # Return best hit
    if not hits:
        return False
    best_name, best_score, _idx = hits[0]
    return best_score >= 92

async def main():
    await pos_service.warmup()
    names = pos_service.get_all_product_names()
    print(f"Total product names: {len(names)}")
    donner_names = [n for n in names if "donner" in n.lower()]
    print(f"Names containing 'donner': {donner_names}")
    
    test_cases = [
        "add a donner pizza",
        "add a meal deal 3",
        "add a medium hawaiian pizza",
        "add pizza",
        "meal deal",
        "donner pizza"
    ]
    
    for tc in test_cases:
        res = _message_has_specific_product_reference(tc, names)
        print(f"Result for '{tc}': {res}")

if __name__ == "__main__":
    asyncio.run(main())
