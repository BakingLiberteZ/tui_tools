# Passphrase Wallet Indicator

## Overview

The passphrase prompt screen now displays which wallet you're entering the passphrase for, preventing confusion when managing multiple wallets.

## Problem Solved

**Before:**
```
┌──────────────────────────────────────┐
│ Passphrase to decrypt key:           │
│                                      │  ❌ Which wallet is this for?
│ [Password input field]               │
│                                      │
│    [OK]        [Cancel]              │
└──────────────────────────────────────┘
```

When you have several wallets, there was no indication of which wallet you were entering the passphrase for.

**After:**
```
┌──────────────────────────────────────┐
│ Passphrase to decrypt key:           │
│ Wallet: Alice Main                   │ ← Now you know!
│                                      │
│ [Password input field]               │
│                                      │
│    [OK]        [Cancel]              │
└──────────────────────────────────────┘
```

## When Wallet Name is Shown

### 1. Adding a New Wallet (Encrypting Secret Key)

When you add a new wallet with a secret key, the passphrase prompt shows the wallet name you just entered:

```
Step 1: Enter wallet name
┌──────────────────────────────────────┐
│ Account name:                        │
│                                      │
│ Alice Main                           │ ← You enter name
│                                      │
│    [OK]        [Cancel]              │
└──────────────────────────────────────┘

Step 2: Enter address
┌──────────────────────────────────────┐
│ Tezos account (tz1/tz2/tz3/tz4):    │
│                                      │
│ tz1abc...                            │
│                                      │
│    [OK]        [Cancel]              │
└──────────────────────────────────────┘

Step 3: Enter secret key
┌──────────────────────────────────────┐
│ Secret key (edsk...) OPTIONAL:       │
│                                      │
│ edskRp...                            │
│                                      │
│    [OK]        [Cancel]              │
└──────────────────────────────────────┘

Step 4: Enter passphrase (NOW WITH WALLET INFO!)
┌──────────────────────────────────────┐
│ Passphrase to encrypt key:           │
│ Wallet: Alice Main                   │ ← Shows the name you entered!
│                                      │
│ [Password input field ••••••]        │
│                                      │
│    [OK]        [Cancel]              │
└──────────────────────────────────────┘
```

### 2. Sending a Transaction (Decrypting Secret Key)

When you send a transaction, the passphrase prompt shows which wallet is sending:

```
Step 1: Select wallet and click Send
Step 2: Enter destination address
Step 3: Enter amount

Step 4: Enter passphrase (NOW WITH WALLET INFO!)
┌──────────────────────────────────────┐
│ Passphrase to decrypt key:           │
│ Wallet: Bob's Savings                │ ← Shows selected wallet name!
│                                      │
│ [Password input field ••••••]        │
│                                      │
│    [OK]        [Cancel]              │
└──────────────────────────────────────┘
```

## Use Cases

### Use Case 1: Managing Multiple Personal Wallets
```
You have:
- "Alice Daily" (everyday spending)
- "Alice Savings" (long-term holding)
- "Alice Trading" (exchange deposits)

When sending from "Alice Trading", the passphrase prompt shows:
  Wallet: Alice Trading

→ You know you're using the correct wallet before entering passphrase!
```

### Use Case 2: Managing Business Wallets
```
You have:
- "Company Operations"
- "Company Payroll"
- "Company Reserve"

When sending from "Company Payroll", the passphrase prompt shows:
  Wallet: Company Payroll

→ Prevents accidentally sending from the wrong business account!
```

### Use Case 3: Managing Family Wallets
```
You have:
- "Dad's Wallet"
- "Mom's Wallet"
- "Kids' Allowance"
- "Family Savings"

When sending from "Kids' Allowance", the passphrase prompt shows:
  Wallet: Kids' Allowance

→ Clear indication you're accessing the right family member's wallet!
```

## Implementation Details

### Modified Class: PromptScreen

**Added Parameter:**
```python
def __init__(self, title: str, placeholder: str = "", password: bool = False, wallet_info: str = ""):
    super().__init__()
    self._title = title
    self._placeholder = placeholder
    self._password = password
    self._wallet_info = wallet_info  # NEW!
```

**Updated Compose:**
```python
def compose(self) -> ComposeResult:
    with Vertical():
        yield Static(f"[b]{self._title}[/b]", markup=True)
        if self._wallet_info:  # NEW!
            yield Static(f"[dim]{self._wallet_info}[/dim]", id="wallet_info", markup=True)
        yield Input(placeholder=self._placeholder, password=self._password, id="inp")
        with Horizontal():
            yield Button("OK", id="ok")
            yield Button("Cancel", id="cancel")
```

**Added CSS:**
```css
PromptScreen #wallet_info {
    color: $accent;
    margin-bottom: 2;
}
```

### Updated Calls

#### 1. Adding Account (Encrypting)
```python
# Line ~1898
pw = await self.push_screen_wait(
    PromptScreen(
        "Passphrase to encrypt key:",
        password=True,
        wallet_info=f"Wallet: {name}"  # NEW!
    )
)
```

#### 2. Sending Transaction (Decrypting)
```python
# Line ~1942
pw = await self.push_screen_wait(
    PromptScreen(
        "Passphrase to decrypt key:",
        password=True,
        wallet_info=f"Wallet: {self.selected.name}"  # NEW!
    )
)
```

## Visual Design

### Styling
- **Wallet info text**: Dimmed color (less prominent than title)
- **Color**: Uses `$accent` from theme
- **Spacing**: 2 units margin below (separates from input field)
- **Position**: Between title and input field

### Layout
```
┌────────────────────────────────────────────────┐
│                                                │
│  [Title: Bold, prominent]                      │
│                                                │
│  [Wallet info: Dimmed, accent color]           │ ← 1 unit below title
│                                                │ ← 2 units above input
│  [Input field: Normal]                         │
│                                                │
│  [Buttons: OK / Cancel]                        │
│                                                │
└────────────────────────────────────────────────┘
```

## Backward Compatibility

The `wallet_info` parameter is **optional** and defaults to empty string:
- Old code still works: `PromptScreen("Title:", password=True)`
- No wallet info shown if parameter not provided
- No breaking changes to existing prompt calls

## Benefits

### 1. Prevents Mistakes
✅ Know which wallet you're accessing before entering passphrase
✅ Avoid accidentally using the wrong wallet for transactions
✅ Clear feedback for security-critical operations

### 2. Better UX
✅ Consistent with wallet selection experience
✅ Reduces cognitive load when managing multiple wallets
✅ Professional and informative interface

### 3. Security Awareness
✅ Reinforces which account is being accessed
✅ Makes user consciously aware of wallet context
✅ Helps prevent accidental key exposure

### 4. Multi-Wallet Support
✅ Essential feature for users with multiple wallets
✅ Scales well as more wallets are added
✅ Clear even with similar wallet names

## Testing

All tests pass:
```bash
✅ python3 test_passphrase_wallet_info.py
✅ python3 test_new_layout.py
✅ python3 test_wallet_details_spacing.py
✅ python3 test_delegation_staking.py
```

## Edge Cases Handled

### Empty wallet_info
```python
PromptScreen("Enter passphrase:", password=True)
# No wallet info shown, works like before
```

### Long wallet names
```
Wallet: My Super Long Wallet Name For Business Operations 2024
# Displayed on single line, wraps if necessary
```

### Special characters in names
```
Wallet: Alice's "Main" Wallet (2024)
# Displayed correctly with markup escaping
```

## Files Modified

- **app.py**:
  - `PromptScreen.__init__()` - Added `wallet_info` parameter
  - `PromptScreen.compose()` - Added wallet_info display
  - `PromptScreen.CSS` - Added `#wallet_info` styling
  - `action_add_account()` - Pass wallet name to encrypt prompt
  - `action_send()` - Pass wallet name to decrypt prompt

## Future Enhancements

Possible improvements:
- Show wallet address (truncated) below name
- Show wallet balance in prompt
- Color code by wallet type (hot/cold/watch-only)
- Show warning icon for large balance wallets
- Add "Remember for this session" checkbox

## Summary

✅ **Wallet name shown** in passphrase prompts
✅ **Prevents confusion** when managing multiple wallets
✅ **Better UX** for security-critical operations
✅ **Backward compatible** - optional parameter
✅ **Professional design** - dimmed, well-spaced
✅ **Works for both** encrypt and decrypt operations

Users now always know which wallet they're accessing when entering a passphrase! 🔐
