# Passphrase Wallet Indicator - Quick Reference

## Visual Comparison

### Before (No Wallet Indicator)
```
┌──────────────────────────────────────┐
│ Passphrase to decrypt key:           │
│                                      │
│ ••••••••                             │  ❌ Which wallet is this?
│                                      │
│    [OK]        [Cancel]              │
└──────────────────────────────────────┘
```

### After (With Wallet Indicator)
```
┌──────────────────────────────────────┐
│ Passphrase to decrypt key:           │
│ Wallet: Alice Main                   │  ✅ Now you know!
│                                      │
│ ••••••••                             │
│                                      │
│    [OK]        [Cancel]              │
└──────────────────────────────────────┘
```

## When You See It

### 📝 Adding a New Wallet
When you add a wallet with a secret key:
```
Passphrase to encrypt key:
Wallet: [the name you just entered]
```

### 💸 Sending a Transaction
When you send XTZ from a wallet:
```
Passphrase to decrypt key:
Wallet: [the selected wallet's name]
```

## Real Examples

### Example 1: Multiple Personal Wallets
```
Your wallets:
  • Alice Daily
  • Alice Savings
  • Alice Trading

When sending from "Alice Savings":

┌──────────────────────────────────────┐
│ Passphrase to decrypt key:           │
│ Wallet: Alice Savings                │ ← Clear!
│                                      │
│ ••••••••                             │
│                                      │
│    [OK]        [Cancel]              │
└──────────────────────────────────────┘
```

### Example 2: Business Wallets
```
Your wallets:
  • Company Operations
  • Company Payroll
  • Company Reserve

When sending from "Company Payroll":

┌──────────────────────────────────────┐
│ Passphrase to decrypt key:           │
│ Wallet: Company Payroll              │ ← Clear!
│                                      │
│ ••••••••                             │
│                                      │
│    [OK]        [Cancel]              │
└──────────────────────────────────────┘
```

## Key Benefits

| Benefit | Description |
|---------|-------------|
| 🎯 **Clarity** | Always know which wallet you're accessing |
| ⚠️ **Safety** | Prevents using the wrong wallet by mistake |
| 👥 **Multi-wallet** | Essential when managing several wallets |
| 🔐 **Security** | Reinforces wallet context for sensitive operations |

## How It Works

1. You select a wallet or enter a wallet name
2. You initiate an action requiring passphrase (add wallet or send)
3. Passphrase prompt shows **"Wallet: [name]"** below the title
4. You know exactly which wallet you're about to access
5. Enter passphrase with confidence! 🎉

## Technical Details

**Optional Parameter**: `wallet_info` (defaults to empty)
**Display Style**: Dimmed text in accent color
**Location**: Between title and input field
**Backward Compatible**: Yes - old code works without changes

## Summary

✅ Wallet name shown in passphrase prompts
✅ Works for both encrypt (add) and decrypt (send)
✅ Prevents confusion with multiple wallets
✅ Professional and clear design

**No more wondering which wallet you're about to access!** 🔐
