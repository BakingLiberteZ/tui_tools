# Advanced Mode - Already Implemented!

## Good News! 🎉

The **Advanced mode** with manual Gas and Storage values is **already fully implemented** and working in your app!

## Quick Guide

### How to Access

1. Click **Send** button
2. Enter destination and amount
3. In the **Confirm Transaction** screen, click **[Advanced]** button
4. Three input fields appear:
   - Fee (XTZ)
   - Gas limit
   - Storage limit

### Visual Flow

```
Normal Mode:                     Advanced Mode (after clicking):
┌─────────────────────┐         ┌─────────────────────────┐
│ Confirm transaction │         │ Confirm transaction     │
│                     │         │                         │
│ Fee (↑/↓ choose)    │         │ Fee (↑/↓ choose)        │
│ • Economy           │         │ • Economy               │
│ • Normal            │         │ • Normal                │
│ • Priority          │         │ • Priority              │
│                     │         │                         │
│ [SEND] [Advanced]   │  ═══►   │ Advanced (TX overrides) │
│        [Cancel]     │         │ Fee (XTZ):    [0.0012]  │ ← Edit
│                     │         │ Gas limit:    [1520]    │ ← Edit
└─────────────────────┘         │ Storage limit:[0]       │ ← Edit
                                │                         │
                                │ [SEND] [Basic] [Cancel] │
                                └─────────────────────────┘
```

## Features Already Working

✅ **Toggle Button** - Switch between Basic/Advanced modes
✅ **Pre-filled Values** - Suggested values shown as defaults
✅ **Manual Input** - Edit Fee, Gas, or Storage limits
✅ **Validation** - Values checked before sending
✅ **Auto-fill** - Leave blank to use suggested values
✅ **Error Handling** - Invalid inputs show error messages
✅ **Proper Styling** - Padding and spacing already applied

## What Each Field Does

### Fee (XTZ)
- Transaction fee paid to bakers
- **Higher fee** = Faster confirmation
- **Lower fee** = Slower confirmation
- Pre-filled with suggested value

### Gas Limit
- Maximum computational resources
- Usually 1000-2000 for transfers
- Increase if transaction fails with "gas exhausted"
- Unused gas is not charged

### Storage Limit
- Maximum blockchain storage allocation
- Usually 0 for simple transfers
- Non-zero for contract interactions
- You pay for storage allocated

## When to Use It

### Use Basic Mode (Most Users)
- Simple transfers
- Trust automatic estimation
- Don't want to worry about details

### Use Advanced Mode
- Need urgent confirmation (increase fee)
- Transaction failed (adjust gas/storage)
- Smart contract interactions
- You know exact values needed
- You want full control

## Code Already Implemented

The functionality exists in `app.py`:

1. **Input Fields** (lines 574-583)
   ```python
   with Vertical(id="advanced"):
       yield Static("[b]Advanced (TX overrides)[/b]...")
       with Horizontal():
           yield Static("Fee (XTZ):", id="lbl_fee")
           yield Input(placeholder="e.g. 0.0012", id="fee_xtz")
       with Horizontal():
           yield Static("Gas limit:", id="lbl_gas")
           yield Input(placeholder="e.g. 2000", id="gas_limit")
       with Horizontal():
           yield Static("Storage limit:", id="lbl_storage")
           yield Input(placeholder="e.g. 0", id="storage_limit")
   ```

2. **Toggle Logic** (lines 781-793)
   ```python
   def _toggle_advanced(self) -> None:
       self._advanced = not self._advanced
       adv = self.query_one("#advanced", Vertical)
       adv.styles.display = "block" if self._advanced else "none"
       self.query_one("#toggle", Button).label = "Basic" if self._advanced else "Advanced"
   ```

3. **Value Parsing** (lines 795-820)
   ```python
   def _parse_overrides(self) -> tuple[Optional[int], Optional[int], Optional[int]]:
       # Reads and validates manual values
       # Returns fee_mutez, gas, storage
       # Raises ValueError if invalid
   ```

4. **Send Logic** (lines 841-849)
   ```python
   @on(Button.Pressed, "#send")
   def send_pressed(self) -> None:
       if self._advanced:
           fee_mutez, gas, storage = self._parse_overrides()
           # Uses manual values
       else:
           # Uses selected fee tier
   ```

## Testing

Run the test to verify:
```bash
python3 test_advanced_mode.py
```

All tests pass ✅

## Documentation

- **User Guide:** `ADVANCED_MODE_GUIDE.md` (comprehensive guide)
- **Test File:** `test_advanced_mode.py` (demonstrates functionality)
- **This Summary:** `ADVANCED_MODE_SUMMARY.md`

## Example Usage

### Scenario: Urgent Transfer

1. Click Send button
2. Enter destination: `tz1xyz...`
3. Enter amount: `5.0`
4. In Confirm screen, click **[Advanced]**
5. Change **Fee (XTZ)** from `0.002` to `0.005` (higher priority)
6. Leave **Gas limit** and **Storage limit** as suggested
7. Click **[SEND]**
8. Transaction sent with higher fee = faster confirmation! 🚀

### Scenario: Failed Transaction

1. Transaction failed: "gas exhausted"
2. Try sending again
3. In Confirm screen, click **[Advanced]**
4. Increase **Gas limit** from `1520` to `2280` (+50%)
5. Click **[SEND]**
6. Transaction succeeds! ✅

## Summary

✅ **Already Implemented** - No code changes needed
✅ **Fully Functional** - All features working
✅ **Well Tested** - Test file included
✅ **Documented** - Complete user guide available
✅ **Easy to Use** - One button to access

Just click **[Advanced]** in the Confirm Transaction screen and you'll see the three input fields ready to use!
