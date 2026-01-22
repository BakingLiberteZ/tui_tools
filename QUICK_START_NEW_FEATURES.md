# 🚀 Quick Start Guide - New Features

## Running the App

```bash
python3 app.py
```

---

## 🎹 All Keyboard Shortcuts

### Main Shortcuts (shown in footer):
- **i** - Import wallet
- **r** - Refresh balance and history
- **s** - Send XTZ
- **x** - Receive (show address)
- **n** - Switch network (mainnet/ghostnet)
- **q** - Quit

### Hidden Shortcuts (not shown in footer):
- **Delete** - Delete selected wallet
- **b** - Backup wallets
- **a** - Show full address
- **e** - Export history to CSV
- **Ctrl+R** - Toggle auto-refresh
- **d** or **Enter** - Show transaction details
- **m** - Load more history
- **Up/Down** - Navigate lists

---

## 💰 Number Formatting

All XTZ amounts now display with thousands separators:

```
Before: 12345.678000
After:  12,345.678
```

Where you'll see it:
- Balance display
- Transaction amounts
- Fee estimates
- Staking balances

---

## 📝 Logging

All operations are logged to `logs/wallet.log`:

```bash
# View recent logs
tail -f logs/wallet.log

# Search for errors
grep ERROR logs/wallet.log

# Search for specific wallet
grep "tz1abc..." logs/wallet.log
```

Log includes:
- Application start/stop
- Wallet operations
- RPC calls
- Transaction sends
- Errors with stack traces

---

## 🕒 Relative Time in History

Transaction timestamps now show relative time:

```
just now
5 min ago
2 hr ago
3 days ago
2 weeks ago
```

---

## ⚡ Balance Caching

Balances are cached for 30 seconds to reduce RPC calls.

To force fresh balance:
- Press **r** (refresh)
- Send a transaction
- Wait 30 seconds

---

## 🗑️ Delete Wallet

**Shortcut**: Press **Delete** key

Steps:
1. Select wallet in list
2. Press **Delete**
3. Confirm in dialog
4. Wallet removed from app

⚠️ **Note**: This only removes the wallet from the app, not from the blockchain!

---

## 💾 Backup Wallets

**Shortcut**: Press **b** key

Creates timestamped backup:
```
data/backups/wallet_backup_20260121_160428.json
```

What's backed up:
- All wallet addresses
- Wallet names
- Encrypted private keys
- Recent destinations
- Settings

💡 **Tip**: Make regular backups before major changes!

---

## 👁️ Show Full Address

**Shortcut**: Press **a** key

Shows:
- Full wallet address (not truncated)
- Wallet name
- Copy button

Great for:
- Sharing your address
- Verifying full address
- Double-checking before send

---

## 📊 Export History to CSV

**Shortcut**: Press **e** key

Creates CSV file:
```
data/exports/transactions_My_Wallet_20260121_160428.csv
```

CSV contains:
- Timestamp (ISO 8601)
- Direction (IN/OUT)
- Amount (XTZ)
- Counterparty address
- Transaction hash
- Wallet name
- Wallet address

Perfect for:
- Tax reporting
- Accounting
- Analysis in Excel/Google Sheets

---

## 🔄 Auto-Refresh

**Shortcut**: Press **Ctrl+R** to toggle

When enabled:
- Refreshes every 60 seconds
- Updates balance
- Reloads transaction history
- Silent (no notifications)
- Setting persists between sessions

Status messages:
```
✅ Auto-refresh enabled (every 60s)
🛑 Auto-refresh disabled
```

---

## ✅ Balance Validation

Before sending, the app checks:
- Current balance
- Estimated fees (~0.01 XTZ)
- Total needed (amount + fees)

If insufficient:
```
❌ Insufficient balance.
Have: 0.5 XTZ, Need: ~1.51 XTZ (including fees)
```

This prevents failed transactions!

---

## 📋 Clipboard Fallback

When copying address fails:
- Shows warning message
- Displays address prominently
- Highlights address for selection
- Modal stays open for manual copy

No more lost addresses!

---

## ⏱️ Elapsed Time Display

During long operations (>5 seconds), shows elapsed time:

```
⠋ Checking the oven… (⏱️ 8s)
```

Helps you know:
- Operation is still running
- How long it's taking
- If you should wait or cancel

---

## 📁 New Directory Structure

```
tui-tezos-wallet/
├── app.py                      # Main application
├── data/
│   ├── wallet.json            # Your wallet data
│   ├── backups/               # Timestamped backups
│   │   └── wallet_backup_*.json
│   └── exports/               # CSV exports
│       └── transactions_*.csv
└── logs/
    ├── wallet.log             # Current log
    ├── wallet.log.1           # Backup 1
    └── wallet.log.2           # Backup 2
```

---

## 🔧 Configuration

All settings are in the `Config` class (app.py):

```python
class Config:
    # RPC timeouts
    RPC_TIMEOUT = 2.5                    # Quick checks
    RPC_FETCH_TIMEOUT = 5.0              # Normal fetches
    RPC_LONG_TIMEOUT = 15.0              # Long operations

    # History
    HISTORY_DEFAULT_LIMIT = 20           # Initial transactions
    HISTORY_INCREMENT = 20               # "Load more" adds

    # Caching
    BALANCE_CACHE_SECONDS = 30.0         # Balance cache duration

    # Auto-refresh
    AUTO_REFRESH_INTERVAL_SECONDS = 60.0 # Refresh frequency

    # UI
    RECENT_DESTINATIONS_MAX = 10         # Recent addresses kept

    # Logging
    LOG_FILE = "logs/wallet.log"         # Log location
    LOG_MAX_BYTES = 10 * 1024 * 1024    # 10MB per file
    LOG_BACKUP_COUNT = 5                 # Keep 5 backups
```

To change settings, edit these values in `app.py`.

---

## 🆘 Troubleshooting

### Problem: Clipboard not working
**Solution**: Use 'a' key to show full address, then copy manually

### Problem: Balance not updating
**Solution**: Press 'r' to force refresh (ignores cache)

### Problem: Transaction not appearing
**Solution**: Indexers can lag 20-30 seconds, be patient

### Problem: Can't find logs
**Solution**: Run `ls -la logs/` to verify location

### Problem: CSV export fails
**Solution**: Check `data/exports/` directory permissions

### Problem: Auto-refresh not working
**Solution**: Toggle off then on with Ctrl+R, check status message

---

## 💡 Pro Tips

1. **Make regular backups**: Press 'b' before making changes
2. **Export for taxes**: Press 'e' at end of month/year
3. **Use auto-refresh**: Press Ctrl+R if you monitor frequently
4. **Check logs**: Look at `logs/wallet.log` if something fails
5. **Validate first**: The app checks balance before sending
6. **Cache is smart**: Reduces RPC calls but refreshes on manual 'r'

---

## 📞 Getting Help

- Check logs: `tail -f logs/wallet.log`
- Run tests: `python3 test_all_improvements.py`
- Read docs: `IMPROVEMENTS_COMPLETE.md`
- Debug mode: Check log file for stack traces

---

## 🎉 Enjoy Your Enhanced Wallet!

All features are production-ready and tested. Happy Tezos-ing! 🚀
