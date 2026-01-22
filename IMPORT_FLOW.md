# 📥 Wallet Import Flow Guide

## 🎯 Optimized Import Process

The wallet import process has been streamlined for maximum efficiency. Choose from three import methods:
- **Secret Key Import**: Auto-derives address from private key
- **Watch-Only Import**: Monitor without sending capability
- **Backup Import**: Restore from backup files

---

## 🔀 Three Import Modes

### Mode 1: Full Wallet (With Private Key) 🔑

**When to use:** You have your secret key and want to send/receive XTZ

**Flow:**
```
Step 1: Name Your Wallet
  ↓
Step 2: Enter Secret Key (edsk...)
  ↓
  🔮 Address Automatically Derived! ✨
  ↓
Step 3: Create Passphrase (to encrypt key)
  ↓
🥐 Wallet Baked to Perfection!
```

**Advantages:**
- ✅ Fewer steps (no need to enter address manually)
- ✅ No risk of address mismatch
- ✅ Can send and receive XTZ
- ✅ Address derived automatically

---

### Mode 2: Watch-Only Wallet (No Private Key) 👀

**When to use:** You want to monitor an address without sending capability

**Flow:**
```
Step 1: Name Your Wallet
  ↓
Step 2: Skip Secret Key (leave blank)
  ↓
Step 3: Enter Tezos Address (tz1/tz2/tz3/tz4)
  ↓
👀 Watch-Only Wallet on Display!
```

**Use cases:**
- 👁️ Monitor someone else's wallet
- 📊 Track a cold wallet without exposing the key
- 🏢 Watch organizational wallets
- 📈 Portfolio tracking

---

### Mode 3: From Backup File 📦

**When to use:** You have a backup JSON file from a previous export

**Flow:**
```
Step 1: Enter Backup File Path
  ↓
  🔍 Reading & Validating Backup File ✨
  ↓
Step 2: Confirm/Rename Wallet
  ↓
  📦 Recent Destinations Restored!
  ↓
🥖 Wallet Reheated from the Pantry!
```

**Advantages:**
- ✅ **Clear path suggestions**: Placeholder shows exact default location
- ✅ Complete wallet restoration (including encrypted key if present)
- ✅ Recent destinations automatically restored
- ✅ Can rename wallet during import
- ✅ Duplicate detection (by address)
- ✅ Full validation of backup structure
- ✅ Flexible path formats: relative, absolute, or `~` expansion

**Backup file structure:**
```json
{
  "backup_timestamp": "2026-01-21T10:30:00",
  "backup_type": "single_wallet",
  "wallet": {
    "name": "My Wallet",
    "address": "tz1abc...",
    "enc": { /* encrypted key if present */ }
  },
  "recent_destinations": ["tz1...", "tz2..."]
}
```

**What gets restored:**
- ✅ Wallet name (with option to rename)
- ✅ Tezos address
- ✅ Encrypted private key (if wallet had one)
- ✅ Recent transaction destinations

---

## 📋 Step-by-Step Examples

### Example 1: Import Full Wallet

```
[Import Button Pressed]

┌───────────────────────────────────────────────────────────┐
│ 🎯 Step 1: Name Your Wallet                              │
│                                                           │
│ 💡 Choose a memorable name! Like naming a pet, but      │
│    for money. 💰                                         │
│                                                           │
│ Input: My Main Wallet                                    │
│ [Next →] [Cancel]                                        │
└───────────────────────────────────────────────────────────┘

[User enters name and clicks Next]

┌───────────────────────────────────────────────────────────┐
│ 🔑 Step 2: Secret Key (Optional)                        │
│                                                           │
│ Wallet: My Main Wallet                                   │
│                                                           │
│ 💡 Got a key? We'll figure out your address!            │
│    No key? No problem, we'll ask! 🎩✨                   │
│                                                           │
│ Input: edskRkJz4Rw...                                    │
│ [Next →] [Cancel]                                        │
└───────────────────────────────────────────────────────────┘

[App derives address automatically]
Status: 🔮 Deriving your address from the secret key...
Status: ✨ Address derived: tz1abc123...def456

┌───────────────────────────────────────────────────────────┐
│ 🔐 Step 3: Create Passphrase                            │
│                                                           │
│ Wallet: My Main Wallet                                   │
│ Address: tz1abc123...def456                              │
│                                                           │
│ 💡 Make it strong! Like a coffee, but for security.     │
│    ☕🔒                                                    │
│                                                           │
│ Input: ••••••••••                                        │
│ [🎉 Import!] [Cancel]                                    │
└───────────────────────────────────────────────────────────┘

[Success!]
Status: ✓ 🎉 New pastry 'My Main Wallet' fresh from the oven!
        Golden-brown and ready to roll! 🥐✨ Full wallet powers unlocked! 🔥
[Status bar glows GREEN for 5 seconds]
```

---

### Example 2: Import Watch-Only Wallet

```
[Import Button Pressed]

┌───────────────────────────────────────────────────────────┐
│ 🎯 Step 1: Name Your Wallet                              │
│                                                           │
│ 💡 Choose a memorable name! Like naming a pet, but      │
│    for money. 💰                                         │
│                                                           │
│ Input: Cold Storage Monitor                              │
│ [Next →] [Cancel]                                        │
└───────────────────────────────────────────────────────────┘

[User enters name and clicks Next]

┌───────────────────────────────────────────────────────────┐
│ 🔑 Step 2: Secret Key (Optional)                        │
│                                                           │
│ Wallet: Cold Storage Monitor                             │
│                                                           │
│ 💡 Got a key? We'll figure out your address!            │
│    No key? No problem, we'll ask! 🎩✨                   │
│                                                           │
│ Input: [leave blank]                                     │
│ [Next →] [Cancel]                                        │
└───────────────────────────────────────────────────────────┘

[User leaves blank and clicks Next]
Status: 👀 Watch-only mode! Let's get your address...

┌───────────────────────────────────────────────────────────┐
│ 🔑 Step 3: Your Tezos Address                           │
│                                                           │
│ Wallet: Cold Storage Monitor                             │
│                                                           │
│ 💡 Watch-only = You can monitor but not send.           │
│    Like a diet at the bakery! 🪟🥖                       │
│                                                           │
│ Input: tz1abc123def456...                                │
│ [🎉 Import!] [Cancel]                                    │
└───────────────────────────────────────────────────────────┘

[Success!]
Status: ✓ 👁️ New display pastry 'Cold Storage Monitor' in the showcase!
        Gorgeous to look at, but not for eating! 🪟✨ Watch-only mode activated! 🥖
[Status bar glows GREEN for 5 seconds]
```

---

### Example 3: Import from Backup File

```
[Import Button Pressed]

┌───────────────────────────────────────────────────────────┐
│ 🎯 Choose Import Method                                  │
│ How would you like to add your wallet?                   │
│                                                           │
│ Pick your flavor! Fresh baked, window shopping,          │
│ or reheated? 🥐                                          │
│                                                           │
│ Options:                                                  │
│ ▸ 🔑 Import with Secret Key                             │
│   👀 Watch-Only Address                                  │
│   📦 From Backup File                                    │
│                                                           │
│ [Continue] [Cancel]                                      │
└───────────────────────────────────────────────────────────┘

[User selects "From Backup File"]

┌───────────────────────────────────────────────────────────┐
│ 📦 Step 1: Backup File Path                             │
│                                                           │
│ 💡 Time to reheat some fresh bread from the pantry!     │
│    🥖📂                                                   │
│    Default location: /full/path/to/data/backups/        │
│                                                           │
│ Input: data/backups/wallet_backup_YYYY-MM-DD.json       │
│                                                           │
│ [Next →] [Cancel]                                        │
└───────────────────────────────────────────────────────────┘

Tip: You can use:
  • Relative paths: data/backups/file.json
  • Absolute paths: /home/user/backups/file.json
  • Home expansion: ~/backups/file.json

[App reads and validates file]
Status: 🔍 Reading the recipe from the pantry...
Status: ✨ Found wallet: My Trading Account

┌───────────────────────────────────────────────────────────┐
│ 📝 Step 2: Confirm/Rename Wallet                        │
│                                                           │
│ Original: My Trading Account                             │
│ Address: tz1abc123...def456                              │
│                                                           │
│ 💡 Keep the name or give it a fresh label! Like         │
│    renaming bread... baguette? 🥖                        │
│                                                           │
│ Input: My Trading Account                                │
│ [🎉 Import!] [Cancel]                                    │
└───────────────────────────────────────────────────────────┘

[Success!]
Status: ✓ 📦 Vintage pastry 'My Trading Account' restored from the recipe book!
        Restored pastry with full powers! Ready to send! 🔥 ✨
[Status bar glows GREEN for 5 seconds]

[Transaction link area shows if recent destinations restored]
📋 Restored 3 recent destinations
```

---

## 🔐 Security Notes

### For Full Wallets:
- ✅ Secret key is **encrypted** with your passphrase
- ✅ Uses AES-256-GCM encryption
- ✅ Key derivation with Argon2id
- ⚠️ **Never share your secret key or passphrase**
- 💾 Backup your secret key separately!

### For Watch-Only Wallets:
- ✅ No private key stored
- ✅ Cannot send transactions
- ✅ Safe for monitoring public addresses
- 👁️ Perfect for tracking without risk

### For Backup Files:
- ✅ Backup files contain encrypted keys (if wallet had one)
- ✅ Same encryption as stored wallets (AES-256-GCM)
- ✅ Passphrase still required to send XTZ after restore
- ⚠️ **Store backup files securely** - they contain your wallet data
- 💾 Keep backups in multiple safe locations
- 🔒 Consider encrypting the backup file itself (OS-level encryption)

---

## ❓ FAQ

### Q: What if I enter the wrong secret key?
**A:** The app will detect invalid keys and show an error. You'll see:
```
❌ Invalid secret key! Can't bake bread with bad flour! 😅
```

### Q: Can I convert a watch-only wallet to a full wallet?
**A:** No, but you can delete the watch-only wallet and re-import it with the secret key.

### Q: What happens if I forget my passphrase?
**A:** Unfortunately, you cannot recover funds without the passphrase. The wallet remains encrypted. This is why backups are important!

### Q: How does address derivation work?
**A:** The app uses cryptographic algorithms to derive your public address (tz1/tz2/tz3/tz4) from your secret key (edsk...). This is a standard Tezos operation.

### Q: Is my secret key safe?
**A:** Yes! Your secret key is:
1. Encrypted immediately with AES-256-GCM
2. Never stored in plain text
3. Only decrypted in memory when sending transactions
4. Protected by your passphrase

### Q: Can I import a backup from another device?
**A:** Yes! Backup files are portable JSON files. Just copy the backup file to your new device and use "📦 From Backup File" option to restore it.

### Q: What happens if the backup file is corrupted?
**A:** The app will detect invalid JSON or missing required fields and show an error:
```
❌ Invalid backup file format! Recipe got soggy! 💧
```

### Q: Can I import a wallet that already exists?
**A:** No. The app checks for duplicate addresses and will show:
```
⚠️ Wallet with address tz1abc...def already exists!
```
You must delete the existing wallet first if you want to re-import.

### Q: What if I lost my backup file?
**A:** If you still have access to the app, you can create a new backup using the `b` key. If you've lost both the app data and backup, you'll need your secret key to recover.

### Q: Do backup files contain my passphrase?
**A:** No! Backup files contain your **encrypted** secret key, not your passphrase. You'll still need to remember your passphrase to send XTZ after restoring from backup.

---

## 🎓 Key Benefits of the New Flow

| Benefit | Description |
|---------|-------------|
| **🚀 Faster** | One less step when importing with secret key |
| **✅ Safer** | No risk of address mismatch |
| **🎯 Simpler** | Less user input required |
| **🔮 Automatic** | Address derived magically from key |
| **🎭 Flexible** | Three import methods: Secret Key, Watch-Only, Backup |
| **📦 Portable** | Easy wallet migration via backup files |
| **🔄 Recovery** | Quick restore from backups with all data intact |
| **📍 Clear Paths** | Placeholder shows exact location of backup directory |

---

## 🆚 Old vs New Flow Comparison

### Old Flow (4 steps for full wallet):
```
1. Enter Name
2. Enter Address ← Manual, error-prone
3. Enter Secret Key
4. Enter Passphrase
```

### New Flow (3 steps for full wallet):
```
1. Enter Name
2. Enter Secret Key
   └→ Address automatically derived! ✨
3. Enter Passphrase
```

**Result:** 25% fewer steps, zero chance of address mismatch!

---

## 🎉 Success Messages

All success messages now feature:
- ✓ **Checkmark** for instant visual confirmation
- 🟢 **Green border** around the status bar
- ⏱️ **5-second duration** before reverting to normal

### Full Wallet:
```
✓ 🎉 New pastry 'name' fresh from the oven!
   Golden-brown and ready to roll! 🥐✨ Full wallet powers unlocked! 🔥
[Status bar: GREEN border + dark green background]
```

### Watch-Only:
```
✓ 👁️ New display pastry 'name' in the showcase!
   Gorgeous to look at, but not for eating! 🪟✨ Watch-only mode activated! 🥖
[Status bar: GREEN border + dark green background]
```

### From Backup:
```
✓ 📦 Vintage pastry 'name' restored from the recipe book!
   Restored pastry with full powers! Ready to send! 🔥 ✨
   (or "Restored as display-only! Watch mode activated! 👀" for watch-only backups)
[Status bar: GREEN border + dark green background]
```

### Backup Created:
```
✓ 📦 Wallet recipe saved! 'name' packaged fresh in the pantry! 🥖
   (X.X KB) → /full/path/to/backup.json
[Status bar: GREEN border + dark green background]
```

---

## 🐛 Error Messages

All error messages now feature:
- ❌ **Error icon** for instant recognition
- 🔴 **Red border** around the status bar
- ⏱️ **5-second duration** before reverting to normal

| Error | Message | Visual | Solution |
|-------|---------|--------|----------|
| Invalid key | "❌ Invalid secret key! Can't bake bread with bad flour!" | RED border | Check your secret key format (should start with edsk) |
| Invalid address | "❌ Invalid account address. Must be tz1/tz2/tz3/tz4" | RED border | Verify address format |
| Import failed | "❌ Import failed: {error}" | RED border | Check error details and try again |
| Cancelled | "↩️ Import cancelled - No dough, no bread! 🍞" | Default | Restart import process |

## ⚠️ Warning Messages

Warning messages (destructive but successful actions) feature:
- ⚠️ **Warning icon** or relevant emoji
- 🟡 **Yellow/Amber border** around the status bar
- ⏱️ **5-second duration** before reverting to normal

| Action | Message | Visual |
|--------|---------|--------|
| Delete wallet | "✓ 🔥 Wallet 'name' returned to the oven! Burned like toast!" | YELLOW border |

---

**Last Updated:** 2026-01-21
**Version:** 1.3.0 - Visual Feedback System

🥐 Happy Baking!
