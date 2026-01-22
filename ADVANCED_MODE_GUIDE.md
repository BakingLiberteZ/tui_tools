# Advanced Mode User Guide

## Overview

The **Advanced Mode** in the Confirm Transaction screen allows you to **manually specify** transaction parameters:
- **Fee** (in XTZ)
- **Gas limit**
- **Storage limit**

This feature is already fully implemented and working!

## How to Use Advanced Mode

### Step-by-Step Guide

1. **Start a transaction**
   - Select a wallet
   - Click "Send" (or press `s`)
   - Enter destination address
   - Enter amount

2. **Confirm Transaction screen appears**
   - Shows transaction summary
   - Shows fee options (Economy / Normal / Priority)
   - Shows **[Advanced]** button at the bottom

3. **Click the "Advanced" button**
   - The button label changes to "Basic"
   - Advanced section expands below the fee selection
   - Three input fields appear with suggested values

4. **Edit any values you want to override**
   - **Fee (XTZ)**: Change the transaction fee
   - **Gas limit**: Change the gas limit
   - **Storage limit**: Change the storage limit
   - Leave blank to use suggested/autofill values

5. **Click "SEND" to proceed**
   - Your manual values will be used
   - Values are validated before sending
   - Transaction is sent with your custom parameters

6. **Click "Basic" to hide advanced options**
   - Returns to simple fee selection mode
   - Advanced values are retained if you toggle back

## Visual Example

### Basic Mode (Default)
```
┌──────────────────────────────────────────────┐
│                                              │
│  Confirm transaction                         │
│                                              │
│  Network:   ghostnet                         │
│  From:      tz1abc123...                     │
│  To:        tz1xyz789...                     │
│  Amount:    1.5 XTZ                          │
│                                              │
│  Fee (↑/↓ to choose)                         │
│  ┌────────────────────────────────────────┐  │
│  │ ● Economy   - 0.001 XTZ                │  │
│  │   Normal    - 0.002 XTZ                │  │
│  │   Priority  - 0.003 XTZ                │  │
│  └────────────────────────────────────────┘  │
│                                              │
│     [SEND]  [Advanced]  [Cancel]             │
│                                              │
└──────────────────────────────────────────────┘
                    ↓
               Click here!
```

### Advanced Mode (After clicking "Advanced")
```
┌──────────────────────────────────────────────┐
│                                              │
│  Confirm transaction                         │
│                                              │
│  Network:   ghostnet                         │
│  From:      tz1abc123...                     │
│  To:        tz1xyz789...                     │
│  Amount:    1.5 XTZ                          │
│                                              │
│  Fee (↑/↓ to choose)                         │
│  ┌────────────────────────────────────────┐  │
│  │ ● Economy   - 0.001 XTZ                │  │
│  │   Normal    - 0.002 XTZ                │  │
│  │   Priority  - 0.003 XTZ                │  │
│  └────────────────────────────────────────┘  │
│                                              │
│  Advanced (TX overrides)        ← Expanded!  │
│  Leave blank to use suggested/autofill       │
│                                              │
│  Fee (XTZ):       [0.001234.........]        │ ← Edit here
│  Gas limit:       [1520.............]        │ ← Edit here
│  Storage limit:   [0................]        │ ← Edit here
│                                              │
│     [SEND]  [Basic]  [Cancel]                │
│                                              │
└──────────────────────────────────────────────┘
```

## Field Descriptions

### 1. Fee (XTZ)
**What it is:** The transaction fee paid to bakers for processing your transaction.

**Default behavior:**
- Pre-filled with suggested fee based on selected option (Economy/Normal/Priority)
- Usually around 0.001-0.003 XTZ

**When to override:**
- You want faster confirmation → Increase fee (e.g., 0.005 XTZ)
- Network is congested → Increase fee
- You want to minimize cost → Decrease fee (may take longer)
- You know the exact fee needed → Set precise value

**Example values:**
- Low priority: `0.001`
- Normal: `0.002`
- High priority: `0.005`

### 2. Gas Limit
**What it is:** Maximum computational resources the transaction can use.

**Default behavior:**
- Pre-filled with estimated gas from RPC simulation
- Usually around 1000-2000 for simple transfers
- Higher for contract interactions

**When to override:**
- Transaction fails with "gas exhausted" → Increase limit
- Calling a complex smart contract → Set higher limit
- You know the exact gas needed → Set precise value

**Example values:**
- Simple transfer: `1520`
- Contract call: `5000`
- Complex contract: `10000`

**Note:** Unused gas is not charged, so it's safer to overestimate.

### 3. Storage Limit
**What it is:** Maximum storage the transaction can allocate on the blockchain.

**Default behavior:**
- Pre-filled with estimated storage from RPC simulation
- Usually 0 for simple transfers
- Non-zero for contract interactions that allocate storage

**When to override:**
- Transaction fails with "storage exhausted" → Increase limit
- Calling a contract that needs storage → Set appropriate limit
- You know the exact storage needed → Set precise value

**Example values:**
- Simple transfer: `0`
- Contract creating storage: `257`
- Large storage allocation: `1000`

**Note:** You are charged for storage allocated, so don't set unnecessarily high.

## Common Use Cases

### Use Case 1: Urgent Transfer (High Priority)
**Scenario:** You need the transaction confirmed quickly.

**Steps:**
1. Click "Advanced"
2. Increase **Fee (XTZ)** to `0.005` or higher
3. Leave gas and storage as suggested
4. Click "SEND"

### Use Case 2: Failed Transaction (Gas Exhausted)
**Scenario:** Transaction failed with "gas exhausted" error.

**Steps:**
1. Try sending again
2. Click "Advanced"
3. Increase **Gas limit** by 50% (e.g., from `1520` to `2280`)
4. Leave fee and storage as suggested
5. Click "SEND"

### Use Case 3: Smart Contract Interaction
**Scenario:** Calling a smart contract function.

**Steps:**
1. Click "Advanced"
2. Review suggested values
3. If you know the contract's requirements:
   - Set appropriate **Gas limit** (usually higher)
   - Set appropriate **Storage limit** (if contract allocates storage)
4. Click "SEND"

### Use Case 4: Minimum Cost Transfer
**Scenario:** Network is not busy, you want minimum fee.

**Steps:**
1. Click "Advanced"
2. Set **Fee (XTZ)** to minimum: `0.0001`
3. Leave gas and storage as suggested
4. Click "SEND"
5. **Warning:** May take longer to confirm!

## Important Notes

### ✅ Do's
- ✓ Leave fields blank to use suggested values (safest)
- ✓ Increase gas if transaction fails with "gas exhausted"
- ✓ Increase fee for faster confirmation during busy periods
- ✓ Review suggested values before overriding
- ✓ Use "Basic" mode for simple transfers (most users)

### ❌ Don'ts
- ✗ Don't set gas too low (transaction will fail)
- ✗ Don't set storage unnecessarily high (costs money)
- ✗ Don't set fee too low (transaction may never confirm)
- ✗ Don't set negative values (will be rejected)
- ✗ Don't use Advanced mode unless you understand these parameters

## Validation and Safety

The app validates your inputs:

### Fee Validation
- ✓ Must be >= 0
- ✓ Must be valid decimal number
- ✓ Negative fees rejected

### Gas Validation
- ✓ Must be >= 0
- ✓ Must be integer
- ✓ Negative gas rejected

### Storage Validation
- ✓ Must be >= 0
- ✓ Must be integer
- ✓ Negative storage rejected

### Error Messages
If validation fails, you'll see an error message in the summary section:
```
[red]Fee estimate failed:[/red] fee must be >= 0
```

You can correct the value and try again.

## When to Use Basic vs Advanced

### Use Basic Mode (Default) When:
- ✓ Simple XTZ transfer between addresses
- ✓ You're not familiar with gas/storage concepts
- ✓ You trust the automatic estimation
- ✓ You want quick and easy transactions
- ✓ Most common use case (recommended for most users)

### Use Advanced Mode When:
- ✓ Transaction failed and you need to adjust parameters
- ✓ You need urgent confirmation (increase fee)
- ✓ You're interacting with smart contracts
- ✓ You know exactly what gas/storage is needed
- ✓ You want fine-grained control
- ✓ You're an advanced user who understands the blockchain

## Keyboard Navigation

In Advanced mode:
- `Tab` - Move between fields
- `Enter` - Accept value and move to next field
- `Escape` - Cancel transaction
- Click "Basic" - Return to simple mode
- Click "SEND" - Send with your custom values

## Technical Details

### How Values Are Applied

**Basic Mode:**
- Uses selected fee tier (Economy/Normal/Priority)
- Uses estimated gas from RPC simulation
- Uses estimated storage from RPC simulation

**Advanced Mode:**
- Fee: Uses your manual value OR suggested if blank
- Gas: Uses your manual value OR suggested if blank
- Storage: Uses your manual value OR suggested if blank

### Estimation Process

1. When confirm screen opens, app calls RPC to estimate transaction
2. RPC simulates the transaction
3. Returns suggested fee, gas, and storage
4. These values are shown as defaults
5. You can override any or all of them

### Code Reference

The parsing logic is in `_parse_overrides()` (app.py:795-820):
```python
def _parse_overrides(self) -> tuple[Optional[int], Optional[int], Optional[int]]:
    fee_xtz_s = (self.query_one("#fee_xtz", Input).value or "").strip()
    gas_s = (self.query_one("#gas_limit", Input).value or "").strip()
    storage_s = (self.query_one("#storage_limit", Input).value or "").strip()

    fee_mutez = None
    gas = None
    storage = None

    if fee_xtz_s:
        fee_xtz = Decimal(fee_xtz_s)
        if fee_xtz < 0:
            raise ValueError("fee must be >= 0")
        fee_mutez = _xtz_to_mutez(fee_xtz)

    if gas_s:
        gas = int(gas_s)
        if gas < 0:
            raise ValueError("gas must be >= 0")

    if storage_s:
        storage = int(storage_s)
        if storage < 0:
            raise ValueError("storage must be >= 0")

    return fee_mutez, gas, storage
```

## Summary

✅ **Feature Status:** Fully implemented and working
✅ **Location:** Confirm Transaction modal → [Advanced] button
✅ **Safety:** Values validated before sending
✅ **Default:** Uses suggested values (safest)
✅ **Override:** Edit any field to customize
✅ **Toggle:** Switch between Basic/Advanced anytime

The Advanced mode gives you complete control over transaction parameters while keeping the interface simple for basic users!
