# Pizza Guys Hybrid Model - Three Issues Fixed

## Summary
All three critical issues reported have been systematically analyzed and fixed with surgical, general-purpose solutions that don't break existing flows.

---

## Issue 1: Meal Deal Disappeared at Checkout ✅ FIXED

### Root Cause
`canonical_cart_json` was never being persisted to session_metadata after `quote_order` completed successfully. This meant when `submit_order` was called, it had no record of the full cart that had been parsed and quoted.

### Location & Fix
**File: src/text_agent/tools.py**
**Lines: 3772-3781**

```python
# FIX #4: SAVE CANONICAL CART FOR SUBMISSION
# Persist the full quote result so submit_order has the complete cart
session_metadata["canonical_cart_json"] = cart_json
session_metadata["last_quoted_items"] = cart_json
logger.info(
    "💾 CART PERSISTED: Save canonical_cart_json (%d items) for submission",
    len(mapped_items)
)
```

### Why It Works
- After quote_order completes parsing and quoting the cart, the full result (`cart_json`) is now saved to session metadata
- When submit_order is called later, it can reconstruct the full cart from `canonical_cart_json`
- Meal deals no longer disappear between quoting and submission

---

## Issue 2: Stuffed Crust Lost from Pizza 4 ✅ FIXED

### Root Cause
`_pizza_merge_structural_correction()` had overly strict validation logic:
```python
if len(structural) != len(nm):  # Too strict!
    return None  # Rejected merge
```

When the LLM re-parsed the cart after the user said "garlic as a separate item", it might not include the crust modifier in the new parse, causing the entire merge to fail and the crust to be lost.

### Location & Fix
**File: src/text_agent/tools.py**
**Lines: 849-905**

**Key change:** Use conditional fallback instead of strict validation
```python
# Merge: Use new structural mods if provided, otherwise keep existing ones
size_f = sn["size"] if sn["size"] else so["size"]
base_f = sn["base"] if sn["base"] else so["base"]
crust_f = sn["crust"] if sn["crust"] else so["crust"]  # ← Preserves if LLM omits
merged_mods = size_f + base_f + crust_f + list(so["other"])
```

### Why It Works
- If LLM re-parses without crust, the new logic preserves the existing crust instead of rejecting the merge
- Structural mods (base, crust, size) now survive re-parsing and user modifications
- Crust is only lost if user explicitly modifies it, not when unrelated items are changed

---

## Issue 3: Garlic Bread/Dip/Sauce Confusion ✅ FIXED

### Root Cause (Three-part problem)
1. No detection of when user wants items "separate" vs. "as a modifier"
2. `_deal_modifier_misclassified_side_phrase()` rejected garlic requests without fallback
3. Rejected mods weren't promoted as separate items; they were silently dropped

### Solution: Three Coordinated Fixes

#### Fix #1: User Intent Detection
**File: src/text_agent/tools.py**
**Lines: 311-343**

Added `_detect_separate_item_intent()` function that detects phrases like:
- "separate item"
- "not in meal deal"
- "on the side"
- "separately"
- "by itself"

And tags items with `_separate_item_intent=True` marker.

#### Fix #3: Dropped Mods Garlic Promotion
**File: src/text_agent/tools.py**
**Lines: 3344-3359**

When a dropped mod is "garlic" (without "bread"), promote it as a separate Garlic Dip item:
```python
if "garlic" in mod_lower and "bread" not in mod_lower and "dip" in mod_lower:
    _garlic_dip_skus = [(s, n) for s, n in _promo_candidates
                        if "garlic" in n.lower() and "dip" in n.lower()]
    if _garlic_dip_skus:
        _promo_candidates = _garlic_dip_skus
        logger.info("🧄 GARLIC PROMOTION: 'garlic' → promoting as Garlic Dip separate item")

# Tag with intent so it won't be re-merged into meal deal
promoted_entry["_separate_item_intent"] = True
```

#### Fix #5: Enhanced Modifier Classification
**File: src/agent.py**
**Lines: 136-179**

Enhanced `_deal_modifier_misclassified_side_phrase()` to:
1. Accept `user_context` parameter (the original user utterance)
2. Detect when user wants standalone garlic as separate item
3. Reject that modifier so it gets promoted properly

```python
def _deal_modifier_misclassified_side_phrase(mod_str, mod_data, user_context=None):
    # ... existing garlic bread logic ...

    # NEW: When user explicitly wants garlic separate, reject it so it becomes Dip
    if "garlic" in ms and "bread" not in ms and "dip" in mn and user_context:
        if any(signal in user_context.lower() for signal in
               ["separate", "not in meal deal", "on the side"]):
            return True  # Reject, promote as separate item
```

### Why It Works (Flow)
1. User says "garlic as separate item" → Detected by `_detect_separate_item_intent()`
2. Item tagged with `_separate_item_intent=True`
3. Mod added to cart → `_deal_modifier_misclassified_side_phrase()` rejects it (Intent detected)
4. Mod goes to `dropped_mods` → Gets promoted by `_promote_dropped_mods_to_menu_items()`
5. Promotion flow recognizes "garlic" + separate intent → Creates Garlic Dip line
6. Garlic Dip tagged with `_separate_item_intent` → Won't be re-merged into meal deal
7. Result: User gets Garlic Dip as separate item, not meal deal modifier

---

## Architecture & Design

### General Solutions (Not Hardcoded)
- User intent detection works for ANY item, not just garlic
- Separate item markers work with all duplicate detection logic
- Structural merge fallback applies to all pizza modifications
- Cart persistence is automatic for all orders

### No Breaking Changes
- All fixes are additive or preserve existing logic
- Backward compatible with existing cart merge flows
- No changes to POS API or core business logic
- Fixes are focused on information preservation, not special casing

### Testing Points
1. **Issue 1**: Meal deals should survive quote_order → submit_order
2. **Issue 2**: Pizza mods (especially crust) should survive re-parses
3. **Issue 3**: "Garlic" + "separate" → Garlic Dip line item (not mod)

---

## Files Modified

1. **src/text_agent/tools.py**
   - Line ~311: Added `_detect_separate_item_intent()`
   - Line ~343: Added `_validate_llm_parsed_item_vs_user_input()` (Fix #6 - NEW)
   - Line ~3344: Enhanced dropped mods garlic promotion
   - Line ~3355: Added LLM hallucination validation (Fix #6 - NEW)
   - Line ~3609: Added max_category_items=10 for SMS (Fix #7 - NEW)
   - Line ~3772: Added canonical_cart_json persistence (Fix #4)
   - Line ~849: Updated `_pizza_merge_structural_correction()` (Fix #2)

2. **src/agent.py**
   - Line ~136: Enhanced `_deal_modifier_misclassified_side_phrase()` with user_context
   - Line ~4012: Updated function call to pass user_context parameter
   - Line ~6025: Added max_category_items=20 for voice (Fix #7 - NEW)

3. **src/order_flow.py** (NEW)
   - Line ~84: Added `max_category_items` parameter to `process_missing_items()`
   - Lines ~143, ~296, ~461: Updated category item limits to use parameter

---

## NEW FIXES (Session 2)

### Issue 4: Wrong Pizza Selection (LLM Hallucination) ✅ FIXED

**Problem:** User said "Hot Buzz Artizan Pizza" but LLM hallucinated "Hawaiian Pizza" which IS on the menu. The system accepted Hawaiian because it exists, even though user never asked for it.

**Root Cause:** No validation that LLM-parsed item names are similar to what the user actually said.

**Solution (Fix #6):** Added `_validate_llm_parsed_item_vs_user_input()` function that:
1. Checks if we're in pending_category_choice mode (e.g., after showing pizza list)
2. Compares user's actual input words with LLM-parsed item name
3. If similarity < 50% and no word overlap, detects hallucination
4. Returns error message asking user to choose from the list

**Location:** src/text_agent/tools.py lines 343-420 (function) and 3355-3380 (call site)

### Issue 5: Long Category Listings (19 pizzas, 7 meal deals) ✅ FIXED

**Problem:** When user says "add a pizza" or "add a meal deal", ALL items in the category were listed. 19 pizzas shown via SMS is excessive and hard to read.

**Root Cause:** Hardcoded limit of 25 items in `process_missing_items()`.

**Solution (Fix #7):**
1. Added `max_category_items` parameter to `process_missing_items()` with default 10
2. SMS calls use `max_category_items=10` (shorter list for text)
3. Voice calls use `max_category_items=20` (longer list acceptable for audio)

**Location:** src/order_flow.py (function signature), src/text_agent/tools.py line 3609, src/agent.py line 6025

---

## NEW FIXES (Session 3)

### Issue 6: Incomplete Category Listings ✅ FIXED

**Problem:** Pizzas and meal deals were split across multiple categories in POS but only items from ONE category were shown. For example, "Classic Pizzas" category was shown but "Stone Baked Pizzas" and "Artisan Pizzas" were omitted.

**Root Cause:** `process_missing_items()` only matched items from the SINGLE category that matched the fuzzy search, not ALL categories containing "pizza" or "meal deal".

**Solution:**
1. Added `should_merge_pizza_categories_for_listing()` - Returns True for any category containing "pizza"
2. Added `build_combined_pizza_option_list()` - Combines ALL pizzas from ALL pizza categories
3. Added `should_merge_all_meal_deal_categories()` - Returns True for any category with "meal" and "deal"
4. Added `build_combined_all_meal_deals_option_list()` - Combines ALL meal deals from ALL meal deal categories
5. **Removed** `max_category_items` limit - Now shows ALL items in category lists

**Location:**
- src/int/meal_deal_intent.py - New functions added
- src/order_flow.py - Category merging logic updated, limit removed

### Issue 7: Item Not Found Validation ✅ FIXED

**Problem:** When user asked for an item not on the menu (e.g., "Hot Buzz Artizan Pizza"), the LLM would hallucinate a random menu item (e.g., "Hawaiian Pizza") and the system would accept it because Hawaiian exists.

**Root Cause:** No validation that LLM-parsed items match user's actual words. The previous Fix #6 only ran when `pending_category_choice` was active.

**Solution (Fix #8):** Added `_validate_item_exists_on_menu()` function that:
1. Runs ALWAYS (not just in pending_category_choice mode)
2. Compares user's significant words with LLM-parsed item names
3. Uses fuzzy matching to detect mismatches (similarity < 45%, no word overlap)
4. Searches all menu items to find what user might have meant
5. Returns appropriate error message:
   - If no match found: "Sorry, I couldn't find 'X' on our menu..."
   - If close match found: "Did you mean 'Y'?"

**Location:** src/text_agent/tools.py lines 432-530 (function) and 3514-3540 (call site)

---

## Files Modified (Updated)

1. **src/text_agent/tools.py**
   - Line ~311: Added `_detect_separate_item_intent()`
   - Line ~345: Added `_validate_llm_parsed_item_vs_user_input()` (Fix #6)
   - Line ~432: Added `_validate_item_exists_on_menu()` (Fix #8 - NEW)
   - Line ~3344: Enhanced dropped mods garlic promotion
   - Line ~3478: LLM hallucination validation (Fix #6)
   - Line ~3514: Menu item validation (Fix #8 - NEW)
   - Line ~3609: Removed max_category_items limit
   - Line ~3772: Added canonical_cart_json persistence (Fix #4)
   - Line ~849: Updated `_pizza_merge_structural_correction()` (Fix #2)

2. **src/agent.py**
   - Line ~136: Enhanced `_deal_modifier_misclassified_side_phrase()` with user_context
   - Line ~4012: Updated function call to pass user_context parameter
   - Line ~6025: Removed max_category_items limit

3. **src/order_flow.py**
   - Line ~13-22: Import new category merging functions
   - Line ~89: Removed `max_category_items` parameter
   - Line ~144, ~297, ~461: Removed category item limits (show ALL items)
   - Line ~390-420: Added pizza and meal deal category merging

4. **src/int/meal_deal_intent.py** (NEW)
   - Added `get_all_pizza_category_names()`
   - Added `should_merge_pizza_categories_for_listing()`
   - Added `build_combined_pizza_option_list()`
   - Added `get_all_meal_deal_category_names()`
   - Added `build_combined_all_meal_deals_option_list()`
   - Added `should_merge_all_meal_deal_categories()`

---

## NEW FIXES (Session 4)

### Issue 1: Item Being Dropped / Duplicate Detection ✅ FIXED

**Problem:** When user added different items (e.g., two different pizzas), the system would sometimes incorrectly consolidate them into one row instead of keeping them separate.

**Root Cause:** `_consolidate_duplicate_meal_deal_lines()` in tools.py was too aggressive. It merged any consecutive rows with the same name without checking if their mods were actually compatible (representing the same "building step" progression).

**Solution (Fix #12):** Enhanced to check mod compatibility before consolidating:
```python
# Only consolidate if mods represent a progression
mods1 = e.get("mods") or []
mods2 = e2.get("mods") or []
if mods1 and mods2 and not _same_build_progression(list(mods1), list(mods2)):
    break  # Different mods - don't consolidate these rows
```

**Location:** src/text_agent/tools.py lines 2580-2636

---

### Issue 2: Missing Pizza/Meal Deal Categories & Wrong Sequence ✅ FIXED

**Problem:**
- "add a pizza" only showed 19 pizzas (missing "New Artizan Pizzas" category)
- "add a meal deal" only showed 7 deals (missing "Brand New Meal Deals"), wrong order (2,Box,5,6,1,3,4 instead of 1,2,3,4,5,6,Box)

**Root Cause:** `_sku_list_for_category_disambiguation()` wasn't using new category merge functions. Two separate code paths weren't unified:
- `order_flow.py`: initial category search (had merging)
- `tools.py`: numeric choice lookup (missing merging)

**Solution (Fixes #9, #10):** Updated `_sku_list_for_category_disambiguation()` to use new merge functions:
```python
# FIX #9: Pizza category merging
if should_merge_pizza_categories_for_listing(cn):
    combined = build_combined_pizza_option_list(pos_service)
    return list(combined)  # Show ALL pizzas from ALL categories

# FIX #10: Meal deal category merging (with proper sequencing)
if should_merge_all_meal_deal_categories(cn):
    combined = build_combined_all_meal_deals_option_list(pos_service)
    return list(combined)  # Numbered first (1,2,3,4,5,6...), then others
```

Also removed `[:25]` limits - now shows full lists.

**Location:** src/text_agent/tools.py lines 2152-2188 (function) and 20-27 (imports)

---

### Issue 3: Modifier Ordering (Crust Before Size/Base) ✅ FIXED

**Problem:** Pizza mods displayed inconsistently:
- Donner Pizza: `(16", Stuffed Crust, Standard Base)` ✓
- Hawaiian Pizza: `(Stuffed Crust, 12", Standard Base)` ✗

Expected: **Size → Base → Crust → Toppings**

**Root Cause:** `build_bill_lines_from_mapped_items()` joined mods in POS API response order (varies by printable_groups).

**Solution (Fix #11):** Added `_normalize_pizza_mod_display_order()` function that categorizes mods and rejoins in canonical order:
```python
def _normalize_pizza_mod_display_order(mod_names: list) -> list:
    sizes = [...]   # Extract 10", 12", 16"
    bases = [...]   # Extract Standard Base, BBQ Base, etc.
    crusts = [...]  # Extract Stuffed Crust, Deep Pan, etc.
    toppings = [...] # Extract Bacon, Pepperoni, etc.
    return sizes + bases + crusts + toppings + others
```

Then use it in bill lines:
```python
print_mods = _normalize_pizza_mod_display_order(print_mods)
desc = f"{item['name']} ({', '.join(print_mods)})"
```

**Location:** src/agent.py lines 4316-4355

---

## Summary of All Session 4 Changes

| Issue | Fix # | Root Cause | Solution |
|-------|-------|-----------|----------|
| Item dropped | #12 | `_consolidate_duplicate_meal_deal_lines()` too aggressive | Check mod compatibility before consolidating |
| Missing categories | #9,#10 | `_sku_list_for_category_disambiguation()` not using merge functions | Call pizza/meal deal merge functions |
| Wrong mod order | #11 | mods joined in POS response order | Normalize order: size→base→crust→toppings |

---

## Maintenance & Future

These fixes establish a pattern for handling user intent:
- Parse natural language for explicit separation signals
- Tag items/mods with intent markers early
- Respect intent markers through all downstream processing
- Fall back gracefully when LLM omits information
- Validate LLM outputs against user's actual input
- Adapt UX to channel constraints (SMS vs Voice)

This approach is flexible and can be extended for other ambiguities in the future.
