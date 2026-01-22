# Wallet-Specific Recent Destinations

## Overview

Recent destinations are now **wallet-specific** instead of global. Each wallet maintains its own independent list of recent transaction destinations.

## What Changed

### Before
- All wallets shared a single global `recent_to` list
- When Wallet A sent to address X, Wallet B would also see address X in its recent destinations
- New wallets would show destinations from other wallets
- Privacy concern: wallet transaction history was shared

### After
- Each wallet has its own `recent_to_by_wallet[wallet_address]` list
- Wallet A's destinations are **never** visible to Wallet B
- New wallets start with an empty list (no confusing pre-filled addresses)
- Complete privacy and isolation between wallets

## Technical Implementation

### Data Structure

**Old structure (deprecated but kept for backwards compatibility):**
```json
{
  "recent_to": ["tz1abc...", "tz1def..."]
}
```

**New structure:**
```json
{
  "recent_to_by_wallet": {
    "tz1wallet1address": ["tz1dest1...", "tz1dest2..."],
    "tz1wallet2address": ["tz1dest3..."],
    "tz1wallet3address": []
  }
}
```

### Key Changes

#### 1. **app.py**

**Initialization:**
```python
# New: per-wallet dictionary
self.recent_to_by_wallet: dict[str, list[str]] = self.store.get("recent_to_by_wallet", {})
```

**Helper method to get recents for a specific wallet:**
```python
def _get_recent_to_for_wallet(self, wallet_addr: str) -> list[str]:
    """Get recent destinations for a specific wallet."""
    return self.recent_to_by_wallet.get(wallet_addr, [])
```

**Updated push method:**
```python
def _push_recent_to(self, wallet_addr: str, dest_addr: str) -> None:
    """Add a destination to the recent list for a specific wallet."""
    # Get or create list for this wallet
    wallet_recents = self.recent_to_by_wallet.get(wallet_addr, [])

    # Add to front (remove duplicates)
    wallet_recents = [x for x in wallet_recents if x != dest_addr]
    wallet_recents.insert(0, dest_addr)
    wallet_recents = wallet_recents[:10]  # Keep only last 10

    # Save
    self.recent_to_by_wallet[wallet_addr] = wallet_recents
    self.store["recent_to_by_wallet"] = self.recent_to_by_wallet
    save_store(self.store)
```

**When opening Send dialog:**
```python
# Get recent destinations for the selected wallet only
wallet_recents = self._get_recent_to_for_wallet(self.selected.address)
to_addr = await self.push_screen_wait(DestinationPickerScreen(wallet_recents))
```

**After successful send:**
```python
# Save to sender wallet's recent list
self._push_recent_to(from_addr, to_addr)
```

#### 2. **wallet/store.py**

**Default store includes new field:**
```python
def _default_store() -> Dict[str, Any]:
    return {
        "rpc": "https://ghostnet.tezos.marigold.dev",
        "accounts": [],
        "recent_to": [],  # Legacy, kept for backwards compatibility
        "recent_to_by_wallet": {},  # New: per-wallet recent destinations
        "tx_prefs": {...},
    }
```

**Load function handles both formats:**
```python
# Recents by wallet (new structure)
if "recent_to_by_wallet" not in data or not isinstance(data.get("recent_to_by_wallet"), dict):
    data["recent_to_by_wallet"] = {}
```

### Migration Strategy

The app automatically migrates old data:

```python
# In WalletApp.__init__()
if "recent_to_by_wallet" not in self.store:
    # Initialize new structure
    self.store["recent_to_by_wallet"] = {}

    # Migrate old data if it exists (assign to all wallets)
    old_recent = self.store.get("recent_to", [])
    if isinstance(old_recent, list) and old_recent:
        for acc in self.accounts:
            self.store["recent_to_by_wallet"][acc.address] = list(old_recent)

    save_store(self.store)
```

## Benefits

### 1. **Privacy**
- Wallet transaction histories are completely isolated
- No way to see where other wallets have sent funds
- Important for multi-user or multi-purpose wallet management

### 2. **User Experience**
- Only relevant addresses shown per wallet
- New wallets don't show confusing pre-filled destinations
- Cleaner, more intuitive interface

### 3. **Organization**
- Each wallet maintains its own context
- Easier to find frequently used addresses for each wallet
- Better for users managing multiple wallets for different purposes

### 4. **Backwards Compatibility**
- Existing installations migrate automatically
- Old `recent_to` field preserved (not used, but kept for safety)
- No data loss during migration

## Testing

Three comprehensive test files verify the implementation:

1. **test_wallet_specific_recents.py** - Tests the core data structure
2. **test_app_initialization.py** - Verifies app initialization
3. **test_wallet_specific_flow.py** - Tests the complete user flow

Run tests:
```bash
python3 test_wallet_specific_recents.py
python3 test_app_initialization.py
python3 test_wallet_specific_flow.py
```

## User Impact

### Scenario Example

**Before:**
1. Alice adds Wallet A, sends to Friend1
2. Bob adds Wallet B, sees Friend1 in recent destinations (confusing!)
3. Bob sends to Shop1
4. Alice now sees Shop1 in her recent destinations (privacy issue!)

**After:**
1. Alice adds Wallet A, sends to Friend1
2. Bob adds Wallet B, sees empty list (correct!)
3. Bob sends to Shop1
4. Alice only sees Friend1 (her own transactions)
5. Complete isolation ✓

### For New Users
- Empty recent destinations list initially
- Clean slate for each new wallet
- No confusion from seeing addresses they didn't send to

### For Existing Users
- Automatic migration preserves old data
- Each wallet gets a copy of the old global list (safe fallback)
- Can delete irrelevant entries per wallet going forward

## Future Enhancements

Possible improvements:
- Add ability to manually edit recent destinations per wallet
- Add "favorites" or "contacts" that persist across wallets
- Add address labels/nicknames per wallet
- Import/export recent destinations
