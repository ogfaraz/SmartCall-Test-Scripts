# Test Cases for Pizza Guys Fixes

## Test Setup
- Channel: SMS (text_agent) and Voice (agent.py)
- Session persistence: canonical_cart_json via session_metadata
- Menu context: POS service with meal deals, pizzas, garlic options

---

## TEST CASE 1: Meal Deal Disappearance (Issue 1 Fix)

### Scenario
User orders Meal Deal 6, completes the build, asks to revert, then submits.

### Steps
1. User: "Meal Deal 6"
2. System: Prompts for pizza selections (Pizza 1, Pizza 2, Pizza 3, Pizza 4)
3. User: [Selects all 4 pizzas with toppings]
4. System: Asks for dips/sides
5. User: "garlic dip"
6. System: Quotes order with full Meal Deal 6 + Garlic Dip
7. User: "revert the original shape" (or similar modification request)
8. System: Calls quote_order again with modified intent
9. User: "submit" or "pay now"
10. System: Calls submit_order

### Expected Result (Before Fix)
- Order submitted with only separate items (Garlic Dip), Meal Deal 6 missing
- POS receives incomplete order

### Expected Result (After Fix)
- `canonical_cart_json` persisted after step 6 quote_order
- Even after modification in step 8, full cart preserved
- submit_order receives complete Meal Deal 6 + Garlic Dip
- Order submitted correctly with all items

### Validation Points
- Check session_metadata["canonical_cart_json"] contains all 4 pizzas
- Check session_metadata["last_quoted_items"] matches canonical_cart_json
- Verify mapped_items in submit_order includes all pizzas + dips
- POS API payload contains complete deal structure

---

## TEST CASE 2: Stuffed Crust Loss (Issue 2 Fix)

### Scenario
User builds pizza with Stuffed Crust, then user adds garlic as separate (LLM re-parses without crust).

### Steps
1. User: "Meal Deal 5"
2. System: Prompts for Pizza 1
3. User: "16\" Stuffed Crust with Donner on top and BBQ base"
4. System: Updates Pizza 1 mods: ["16\" size", "BBQ base", "Stuffed Crust", "Donner On Top"]
5. System: Quotes: Pizza 1 with all mods confirmed
6. User: "add garlic as a separate item"
7. System: Calls quote_order with updated intent
   - LLM re-parses Pizza 1: ["16\" size", "BBQ base", "Donner On Top"] - (missing Stuffed Crust!)
   - LLM adds Garlic Dip as separate item
8. System: merge logic processes Pizza 1 modification

### Expected Result (Before Fix)
- Pizza merge fails strict validation check
- Stuffed Crust is lost from Pizza 1
- User receives pizza without desired crust

### Expected Result (After Fix)
- `_pizza_merge_structural_correction()` uses conditional fallback
- Missing crust detected: `sn["crust"]` is empty
- Falls back to existing crust: `so["crust"]` = "Stuffed Crust"
- Pizza 1 retains: ["16\" size", "BBQ base", "Stuffed Crust", "Donner On Top"]
- Garlic Dip added as separate item
- Order correct with all preferences preserved

### Validation Points
- Check pizza mods include "Stuffed Crust" after re-parse
- Verify merge logic executed (not rejected with None return)
- Confirm mapped_items[Pizza 1] has all 4 original mods
- Bill lines show pizza with crust option

---

## TEST CASE 3A: "Garlic" Standalone - Separate Item (Issue 3 Fix)

### Scenario
User explicitly wants garlic as a separate item, not in meal deal.

### Steps
1. User: "Meal Deal 6"
2. System: Prompts for pizzas
3. User: [Selects pizzas]
4. System: Asks for dips
5. User: "garlic as a separate item" OR "garlic not in the meal deal"
6. System: Calls quote_order with this intent

### LLM Parsing
- Intent detection: `_detect_separate_item_intent("garlic as separate item")` → True
- Items tagged: `_separate_item_intent: True`
- Mods include attempt: `{"name": "Garlic Dip", ...}`

### Expected Result (Before Fix)
- "Garlic" rejected by `_deal_modifier_misclassified_side_phrase()`
- Goes to dropped_mods
- No promotion fallback
- User: "Where's my garlic?" 🤷

### Expected Result (After Fix)
- Separate intent detected and tagged early
- Mod "Garlic Dip" rejected by misclassified_side_phrase (because standalone garlic + separate intent)
- Dropped mod promotion detects "garlic" + no "bread"
- Filters candidates to Garlic Dip items only
- Creates separate item: `{"name": "Garlic Dip", "qty": 1, "_separate_item_intent": True}`
- Duplicate detection respects intent marker, doesn't merge it back into meal deal
- Final order: Meal Deal 6 + Garlic Dip as line item
- User gets exactly what they asked for

### Validation Points
- Check `user_wants_separate` is True after step 6
- Verify items tagged with `_separate_item_intent`
- Confirm dropped_mods includes garlic entry
- Check promoted items list includes Garlic Dip with intent marker
- Final mapped_items has separate Garlic Dip line
- Bill lines show "Garlic Dip" as line item, not within meal deal

---

## TEST CASE 3B: "Garlic Bread" - Category Item (Issue 3 Edge Case)

### Scenario
User wants Garlic Bread category (not dip, not sauce), not merged into meal deal.

### Steps
1. User: "Pizza meal"
2. System: [Builds meal]
3. User: "add garlic bread to go with it" OR "garlic bread on the side"
4. System: Calls quote_order

### Expected Result (After Fix)
- "Garlic Bread" + separate signals detected
- `_deal_modifier_misclassified_side_phrase()` sees: "bread" in mod_str AND "bread" not in mod_data
- Returns True → rejected from meal deal
- Dropped mod promotion: Filters to Garlic Bread SKUs (not Dip)
- Creates: `{"name": "Garlic Bread [XXL]", "qty": 1, "_separate_item_intent": True}`
- Result: Separate Garlic Bread item

### Validation Points
- Promotion candidates filtered to "bread" category
- Not matched to Garlic Dip
- Separate Garlic Bread line item created
- Intent marker prevents re-merging

---

## TEST CASE 3C: "Garlic Sauce" - Modifier on Pizza (Issue 3 Edge Case)

### Scenario
User wants Garlic Sauce AS A MODIFIER on a specific pizza.

### Steps
1. User: "Spicy Parmo with garlic sauce"
2. System: Calls quote_order

### Expected Result (After Fix)
- "Garlic sauce" parsed as mod for Parmo
- `_deal_modifier_misclassified_side_phrase()` sees: "sauce" in mod_str
- Returns False immediately (line 150-151: `if "sauce" in ms: return False`)
- Mod approved and added to pizza mods
- Result: Parmo with Garlic Sauce modifier

### Validation Points
- "sauce" detected → not rejected
- Mod appears in pizza's mods array
- Not promoted as separate item
- Works as intended modifier

---

## Integration Test: Full Order Flow

### Scenario
Complex order combining all three issue areas.

```
User Flow:
1. "Meal Deal 6"
   → Meal Deal 6 selected

2. [Completes pizza builds for all 4 slots]
   → Pizza 1-4 built with various options

3. "pizza 1 with stuffed crust"
   → Pizza 1 gets Stuffed Crust modifier

4. "garlic as a separate item"
   → Triggers separate item intent
   → Garlic becomes separate Dip line
   → Pizza 1 retains Stuffed Crust despite re-parse

5. "that's all"
   → Checkout begins

6. [Provides name, delivery type, payment]
   → submit_order called

7. Order confirmed
   → POS receives: Meal Deal 6 (all pizzas with mods) + Garlic Dip
```

### Expected Validation
- Session metadata has canonical_cart_json with all 4 pizzas
- Pizza 1 retains Stuffed Crust through all re-parses
- Garlic Dip exists as separate line item
- All three issues fixed simultaneously
- Order confirmed with correct total and all items

---

## Performance & Regression Tests

### Non-Regression Test 1: Regular Pizza Order (No Issues)
```
User: "Large Spicy Parmo with Garlic Sauce"
Expected: Standard order, no separate intent markers, normal flow
```

### Non-Regression Test 2: Multiple Meal Deals
```
User: "2x Meal Deal 3 and 1x Meal Deal 5"
Expected: All meal deals preserved, no cross-contamination
```

### Non-Regression Test 3: Drink/Side Add-ons (No Garlic)
```
User: "Pizza, add Pepsi and Chips"
Expected: Normal duplicate detection, items deduplicated correctly
```

### Non-Regression Test 4: Negative Phrases
```
User: "No onions", "Without garlic sauce"
Expected: Negative mods handled, not confused with separate intent
```

---

## Summary of Validation

All three issues should now be resolved:
1. ✅ Meal Deal persists from quote_order to submit_order
2. ✅ Stuffed Crust survives re-parsing via conditional fallback
3. ✅ Garlic requests handled appropriately:
   - Standalone "garlic" → Separate Garlic Dip
   - "Garlic bread" → Separate Garlic Bread item
   - "Garlic sauce" → Modifier on pizza

The fixes are general-purpose and don't break existing functionality.
