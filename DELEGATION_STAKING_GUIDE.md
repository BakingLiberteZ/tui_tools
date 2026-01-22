# Delegation and Staking Display

## Overview

The wallet details section now displays **delegation** and **staking** information, providing a complete view of your wallet's status at a glance.

## What Changed

### Removed
- ❌ **Address line** - Redundant since addresses are already shown in the accounts list

### Added
- ✅ **Delegation info** - Shows which baker your wallet is delegated to
- ✅ **Staking balance** - Shows how much you have staked

## Visual Comparison

### Before
```
┌─────────────────────────────────┐
│ Alice Main Wallet               │
│                                 │
│ Address: tz1abc123de…fgh890xyz  │ ← Redundant
│                                 │
│ Balance: 12.456789 XTZ          │
│                                 │
│ Network: mainnet                │
└─────────────────────────────────┘
```

### After
```
┌─────────────────────────────────┐
│ Status: Connected               │ ← NEW!
│                                 │
│ Balance: 12.456789 XTZ          │
│                                 │
│ Delegated to: tz1baker12…456    │ ← NEW!
│                                 │
│ Staking: 5.000000 XTZ           │ ← NEW!
│                                 │
│ Network: mainnet                │
└─────────────────────────────────┘
```

## Display Logic

### 1. RPC Status
- **Always shown**
- Format: `Status: [dim]Connected[/dim]` or `Status: [dim]Disconnected[/dim]`
- Shows "Connected" when RPC connection is successful
- Shows "Disconnected" when RPC connection fails

### 2. Balance
- **Always shown**
- Format: `Balance: [b]X.XXXXXX XTZ[/b]` (bold amount)
- Shows 6 decimal places

### 3. Delegation (Always Shown)
- **Always shown with current delegation status**
- Format when delegated: `Delegated to: [dim]tz1baker12…456[/dim]` (dimmed)
- Address is shortened: first 10 chars + "…" + last 8 chars
- Format when not delegated: `Delegated to: [dim]not delegated[/dim]` (dimmed)

### 4. Staking (Always Shown)
- **Always shown with current staking status**
- Format when staking: `Staking: [dim]X.XXXXXX XTZ[/dim]` (dimmed)
- Shows 6 decimal places
- Format when not staking: `Staking: [dim]-[/dim]` (dimmed)

### 5. Network
- **Always shown**
- Format: `Network: Mainnet` or `Network: Ghostnet`
- Derived from current RPC URL

## Data Sources

### Delegation Information
- **API:** TzKT API
- **Endpoint:** `/v1/accounts/{address}`
- **Field:** `delegate.address`
- **Returns:** Baker address (tz1...) or null

### Staking Balance
- **API:** TzKT API
- **Endpoint:** `/v1/accounts/{address}`
- **Field:** `stakedBalance`
- **Returns:** Integer (mutez) or 0

## Implementation

### New Functions (wallet/tezos.py)

#### get_delegation_info()
```python
def get_delegation_info(rpc: str, address: str) -> Optional[str]:
    """
    Get the baker address this account is delegated to.
    Returns None if not delegated.
    """
```

#### get_staking_balance()
```python
def get_staking_balance(rpc: str, address: str) -> int:
    """
    Get the staking balance (staked amount) for this account in mutez.
    Returns 0 if not staking or if information is unavailable.
    """
```

### UI Updates (app.py)

#### Compose Changes
```python
# Removed:
yield Static("", id="wallet_address", markup=True)

# Added:
yield Static("", id="wallet_delegation", markup=True)
yield Static("", id="wallet_staking", markup=True)
```

#### CSS Changes
```python
# Added spacing for new elements:
#wallet_delegation {
    height: auto;
    margin-bottom: 1;
}

#wallet_staking {
    height: auto;
    margin-bottom: 1;
}
```

#### Display Logic (_update_status_balance)
```python
# Delegation info
delegate = get_delegation_info(self.rpc, self.selected.address)
if delegate:
    delegate_short = delegate[:10] + "…" + delegate[-8:]
    self.query_one("#wallet_delegation", Static).update(
        f"Delegated to: [dim]{delegate_short}[/dim]"
    )
else:
    self.query_one("#wallet_delegation", Static).update("")

# Staking balance
staking_bal = get_staking_balance(self.rpc, self.selected.address)
if staking_bal > 0:
    self.query_one("#wallet_staking", Static).update(
        f"Staking: [dim]{mutez_to_xtz(staking_bal):.6f} XTZ[/dim]"
    )
else:
    self.query_one("#wallet_staking", Static).update("")
```

## Use Cases

### Use Case 1: Delegated Wallet
```
┌─────────────────────────────────┐
│ Status: Connected               │
│                                 │
│ Balance: 100.000000 XTZ         │
│                                 │
│ Delegated to: tz1baker...       │ ← Shows baker
│                                 │
│ Staking: -                      │ ← Shows dash
│                                 │
│ Network: mainnet                │
└─────────────────────────────────┘
```

### Use Case 2: Staking Wallet
```
┌─────────────────────────────────┐
│ Status: Connected               │
│                                 │
│ Balance: 50.000000 XTZ          │
│                                 │
│ Delegated to: not delegated     │ ← Shows status
│                                 │
│ Staking: 25.500000 XTZ          │ ← Shows amount
│                                 │
│ Network: mainnet                │
└─────────────────────────────────┘
```

### Use Case 3: Both Delegation and Staking
```
┌─────────────────────────────────┐
│ Status: Connected               │
│                                 │
│ Balance: 200.000000 XTZ         │
│                                 │
│ Delegated to: tz1baker...       │ ← Shows baker
│                                 │
│ Staking: 100.000000 XTZ         │ ← Shows amount
│                                 │
│ Network: mainnet                │
└─────────────────────────────────┘
```

### Use Case 4: Neither Delegation nor Staking
```
┌─────────────────────────────────┐
│ Status: Connected               │
│                                 │
│ Balance: 5.000000 XTZ           │
│                                 │
│ Delegated to: not delegated     │ ← Always visible
│                                 │
│ Staking: -                      │ ← Always visible
│                                 │
│ Network: mainnet                │
└─────────────────────────────────┘
```

## Benefits

### 1. No Redundancy
- Address is already visible in the accounts list
- Removed from details to avoid duplication
- Better use of screen space

### 2. Delegation Monitoring
- See at a glance if wallet is delegated
- Identify which baker you're delegating to
- No need to check external tools

### 3. Staking Awareness
- Monitor your staking balance easily
- See how much is currently staked
- Track staking participation

### 4. Consistent Display
- Always shows delegation and staking status
- Clear indication when not delegated or staking
- Consistent layout regardless of wallet state

### 5. Auto-Updated
- Refreshes when switching wallets
- Updates when pressing Refresh button
- Always shows current data from blockchain

## When Information Updates

The delegation and staking information is fetched and displayed:

1. **When selecting a wallet** - Clicking a wallet in the accounts list
2. **When refreshing** - Pressing Refresh button (r)
3. **After network change** - When switching RPC endpoints
4. **On app startup** - If a wallet is auto-selected

## Error Handling

### Network Errors
- If TzKT API is unreachable, fields remain empty
- No error is shown (graceful degradation)
- User can try refreshing

### Invalid Data
- If delegate field is missing: shows nothing
- If stakedBalance is 0 or missing: shows nothing
- Prevents displaying incorrect information

## Styling

### Text Styling
- **Balance:** Bold (emphasizes main value)
- **Delegation:** Dimmed (secondary info)
- **Staking:** Dimmed (secondary info)
- **Network:** Normal (tertiary info)

### Spacing
- Each line has `margin-bottom: 1`
- Clean, readable layout
- Consistent with rest of app

## Testing

### Test Files
1. **test_delegation_staking.py** - Verifies new fields exist and work
2. **test_wallet_details_spacing.py** - Updated to test new structure
3. **test_app_initialization.py** - Ensures app still initializes

Run tests:
```bash
python3 test_delegation_staking.py
python3 test_wallet_details_spacing.py
python3 test_app_initialization.py
```

## API Reference

### TzKT API Response Structure

```json
{
  "address": "tz1...",
  "balance": 1000000,
  "stakedBalance": 500000,
  "delegate": {
    "address": "tz1baker..."
  }
}
```

### Field Mapping
- `balance` → Balance display (always)
- `delegate.address` → Delegation display (if present)
- `stakedBalance` → Staking display (if > 0)

## Future Enhancements

Possible improvements:
- Show baker name (from TzKT metadata)
- Display delegation rewards
- Show staking rewards
- Add delegation history
- Include unstaking operations
- Show baker performance metrics

## Summary

✅ **Removed redundant address line**
✅ **Added delegation information**
✅ **Added staking balance**
✅ **Conditional display (only when relevant)**
✅ **Auto-updated from blockchain**
✅ **Cleaner, more informative UI**

The wallet details section now provides a complete overview of your wallet's status without cluttering the interface!
