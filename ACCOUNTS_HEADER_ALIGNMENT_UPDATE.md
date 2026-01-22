# Accounts Header - Text Alignment and Button Update

## Overview

Updated the accounts header to improve vertical text alignment and changed the button text to "Import Wallet" for better clarity.

---

## Changes Made

### 1. Button Text Update

**Before:**
```python
yield Button("Add (a)", id="add")
```

**After:**
```python
yield Button("Import Wallet", id="add")
```

**Reason:**
- More descriptive action name
- "Import Wallet" is clearer than "Add"
- Standard terminology in crypto wallets
- Better indicates what the action does
- Removes keyboard shortcut from visual (can be added elsewhere)

---

### 2. Vertical Text Alignment

**Before:**
```css
#add {
    width: auto;
    background: #3b82f6;
    color: white;
}
```

**After:**
```css
#add {
    width: auto;
    background: #3b82f6;
    color: white;
    content-align: center middle;  /* NEW: Vertical alignment */
}
```

**Reason:**
- Ensures button text aligns vertically with "ACCOUNTS:" label
- Both elements now use `middle` vertical alignment
- Creates professional, balanced appearance

---

## Visual Comparison

### Before
```
┌───────────────────────────────────────────────────────────────┐
│                                                               │
│        ACCOUNTS:             [Add (a)]                        │
│        ↑ Title               ↑ Short text                     │
│        May not be            Generic action                   │
│        perfectly aligned                                      │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

❌ Button text might not align perfectly
❌ "Add (a)" is generic and unclear
❌ Doesn't describe the actual action

### After
```
┌───────────────────────────────────────────────────────────────┐
│                                                               │
│        ACCOUNTS:             [Import Wallet]                  │
│        ↑ Title               ↑ Aligned text                   │
│        Perfectly aligned     Clear action                     │
│        vertically            description                      │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

✅ Perfect vertical alignment
✅ "Import Wallet" is descriptive and clear
✅ Indicates you're importing an existing wallet
✅ Professional appearance

---

## Alignment Details

### Header Container
```css
#accounts_header {
    height: auto;
    margin-bottom: 1;
    align: left middle;  /* Middle vertical alignment */
}
```

### Title Label
```css
#accounts_title {
    width: auto;
    padding-right: 2;
    text-style: bold;
    content-align: left middle;  /* Middle vertical alignment */
}
```

### Button
```css
#add {
    width: auto;
    background: #3b82f6;
    color: white;
    content-align: center middle;  /* NEW: Middle vertical alignment */
}
```

**Result:** All three elements (container, label, button) now share `middle` vertical alignment, ensuring perfect text alignment.

---

## Benefits

### 1. Better Text Alignment
- **ACCOUNTS:** label and **Import Wallet** button text align perfectly
- Both use `middle` vertical alignment
- Professional, polished appearance
- Consistent visual baseline

### 2. Clearer Action Description
- **"Import Wallet"** is more descriptive than **"Add (a)"**
- Users immediately understand what the button does
- Standard terminology in cryptocurrency wallets
- Reduces confusion

### 3. Professional Terminology
- "Import" is the correct term for adding existing wallets
- Aligns with industry standards
- Better UX (User Experience)
- More intuitive for users

### 4. Visual Hierarchy
- Clear section label: **ACCOUNTS:**
- Clear action button: **[Import Wallet]**
- Both elements properly aligned
- Easy to scan and understand

---

## Technical Details

### CSS Changes (app.py line 1083)

```css
/* Added content-align for vertical alignment */
#add {
    width: auto;
    background: #3b82f6;
    color: white;
    content-align: center middle;  /* NEW */
}
```

### Python Changes (app.py line 1304)

```python
# Updated button text
yield Button("Import Wallet", id="add")  # Changed from "Add (a)"
```

---

## Complete Layout with Alignment

```
┌───────────────────────────────────────────────────────────────┐
│                                                               │
│        🍞 TEZOS WALLET                                        │
│                                                               │
│        ACCOUNTS:             [Import Wallet]                  │
│        ├─ Bold label         ├─ Blue button                  │
│        ├─ Colon separator    ├─ Center middle aligned        │
│        └─ Left middle        └─ Descriptive action           │
│           aligned                                             │
│                                                               │
│        Alice Main                 │ tz1abc...def            │
│        Bob Savings                │ tz1ghi...jkl            │
│        Carol Trading Company      │ tz1mno...pqr            │
│        Dave (watch)               │ tz1stu...vwx            │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

---

## Comparison with Other Sections

### Before
```
Top section:    ACCOUNTS:             [Add (a)]
                                       ↑ Generic

Bottom section: [Send (s)]  [Receive (x)]  [Refresh (r)]
                 ↑ Specific actions
```

### After
```
Top section:    ACCOUNTS:             [Import Wallet]
                                       ↑ Specific action

Bottom section: [Send (s)]  [Receive (x)]  [Refresh (r)]
                 ↑ Specific actions
```

**All buttons now use specific, descriptive action verbs!**

---

## Use Cases

### Adding a New Wallet
```
User sees:  ACCOUNTS:             [Import Wallet]
                                   ↑ Click to import

Action: Opens dialog to:
- Import from mnemonic
- Import from private key
- Create new wallet (if option available)
```

### Visual Alignment Check
```
┌─────────────────────────────────────┐
│ ACCOUNTS:        [Import Wallet]    │
│    ↕ Same         ↕ Same            │
│  baseline       baseline            │
│  alignment      alignment           │
└─────────────────────────────────────┘
```

Both texts sit on the same visual baseline thanks to `middle` alignment.

---

## Button Text Rationale

### Why "Import Wallet" instead of "Add (a)"?

| Aspect | "Add (a)" | "Import Wallet" |
|--------|-----------|-----------------|
| Clarity | ⚠️ Generic | ✅ Specific |
| Action | ❓ Add what? | ✅ Import a wallet |
| Standard | ❌ Uncommon | ✅ Industry standard |
| User understanding | ⚠️ May be unclear | ✅ Immediately clear |
| Professional | ⚠️ Casual | ✅ Professional |
| Keyboard shortcut | ✅ Shows (a) | ➡️ Can add later |

---

## Testing

### Test File
Created `test_accounts_header_alignment.py` to validate:
- ✅ Header has middle vertical alignment
- ✅ Title has middle vertical alignment
- ✅ Button has middle vertical alignment
- ✅ Button text is "Import Wallet"
- ✅ Consistent blue background color
- ✅ All styling preserved

### Test Results
```bash
✅ test_accounts_header_alignment.py - All checks pass
✅ test_accounts_header.py           - No regressions
✅ test_ui_padding.py                - No regressions
```

All tests pass! 🎉

---

## Future Enhancements

### Keyboard Shortcut
Could add keyboard shortcut indicator in a separate location:
```
ACCOUNTS:             [Import Wallet]

Press 'a' to import a wallet
```

Or in a status line:
```
a: Import | s: Send | x: Receive | r: Refresh | q: Quit
```

### Button Variants
Could offer different import methods:
```
[Import Wallet ▼]  ← Dropdown menu
├─ Import from Mnemonic
├─ Import from Private Key
└─ Create New Wallet
```

---

## Files Modified

**app.py:**
- Line 1084: Added `content-align: center middle;` to `#add` CSS
- Line 1304: Changed button text from `"Add (a)"` to `"Import Wallet"`
- Line 1301: Updated comment to match new button text

---

## Files Created

1. **test_accounts_header_alignment.py** - Automated test
2. **ACCOUNTS_HEADER_ALIGNMENT_UPDATE.md** - This documentation

---

## Alignment Summary

| Element | Horizontal | Vertical | Result |
|---------|-----------|----------|--------|
| `#accounts_header` | left | middle | Container alignment |
| `#accounts_title` | left | middle | Label alignment |
| `#add` (button) | center | middle | Button alignment |

**All use `middle` vertical alignment** = Perfect text baseline alignment ✅

---

## Before/After Summary

| Aspect | Before | After | Improvement |
|--------|--------|-------|-------------|
| Button text | Add (a) | Import Wallet | ✓ Clearer |
| Text alignment | May vary | middle (all) | ✓ Perfect |
| Descriptiveness | Generic | Specific | ✓ Better UX |
| Professional | Casual | Professional | ✓ Industry standard |
| Visual baseline | May differ | Aligned | ✓ Polished |

---

## Summary

✅ **Changed button text** from "Add (a)" to "Import Wallet"
✅ **Added vertical alignment** to button (`content-align: center middle`)
✅ **Perfect text alignment** between label and button
✅ **More descriptive action** - users know what button does
✅ **Professional terminology** - standard in crypto wallets
✅ **All tests pass** - no functionality broken

**Result**: A professional, well-aligned accounts header with clear, descriptive button text! 🎨✨
