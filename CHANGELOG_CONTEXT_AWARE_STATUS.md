# Changelog: Context-Aware Status with Baking Theme

## Date
2026-01-21

## Summary
Transformed the status line from a temporary notification system to a context-aware status display that maintains information about the last action performed, all using a fun baking theme.

## Changes Made

### 1. Removed Auto-Reset to "Ready"

**Before:**
- All actions reset status to "✓ Ready" after completion
- Information disappeared quickly
- Users couldn't reference what just happened

**After:**
- Status messages stay visible until the next action
- Transaction details persist (hash, baker, TzKT link)
- Users always know the last action performed

**Modified:**
- `_set_status()` - Removed `duration` parameter and auto-reset logic
- `_stop_spinner()` - No longer resets to "Ready"

### 2. Updated Transaction Messages to Baking Theme

| Message Type | Before | After |
|--------------|--------|-------|
| Initial | ✓ Ready | 🍞 Oven ready! |
| Sending | 🥖 Sending to the baker… | 🥖 Putting the bread in the oven… |
| Injected | (unchanged) | 🥐 Transaction in the oven: [hash] \| [link] |
| Pending | 🥐 In the oven: [hash] | 🥐 Still in the oven: [hash] |
| Success | (unchanged) | 🍞 Fresh from the oven! Block baked by [baker] |
| Error | Send failed: [error] | ❌ Baking failed: [error] |

### 3. Added Refresh Status Messages

**New Messages:**
- While loading: `⏳ Checking the oven…`
- On success: `🔄 Oven refreshed!`
- On error: `❌ Oven check failed: [error]`

**Modified:**
- `action_refresh()` - Added status message for refresh completion
- `_load_history()` - Changed loading message and added success status

### 4. Status Persistence Behavior

**Changed Files:**

#### app.py - Line 1416-1424
```python
# BEFORE:
def _set_status(self, text: str, duration: float = 0) -> None:
    # ... with auto-reset after duration

# AFTER:
def _set_status(self, text: str) -> None:
    """Update status message (stays visible until next action)."""
    self._last_status = text
    try:
        self.query_one("#status_line", Static).update(text)
    except Exception:
        pass
```

#### app.py - Line 1376-1382
```python
# BEFORE:
def _stop_spinner(self) -> None:
    # ... stop spinner
    self.query_one("#status_line", Static).update("✓ Ready")

# AFTER:
def _stop_spinner(self) -> None:
    # ... stop spinner
    # Don't reset status - let each action set its own final message
```

#### app.py - Line 1311
```python
# BEFORE:
yield Static("✓ Ready", id="status_line", markup=True)

# AFTER:
yield Static("🍞 Oven ready!", id="status_line", markup=True)
```

#### app.py - Line 1991
```python
# BEFORE:
self._ui(self._start_spinner, "🥖 Sending to the baker…")

# AFTER:
self._ui(self._start_spinner, "🥖 Putting the bread in the oven…")
```

#### app.py - Lines 2042-2047
```python
# BEFORE:
if baker:
    self._ui(self._set_status, f"🍞 Fresh from the oven! Block baked by {baker} · {oph}", 5.0)
else:
    self._ui(self._set_status, f"🍞 Transaction baked successfully! · {oph}", 5.0)
else:
    self._ui(self._set_status, f"🥐 In the oven: {oph} (waiting for baker to finish…)", 5.0)

# AFTER:
if baker:
    self._ui(self._set_status, f"🍞 Fresh from the oven! Block baked by {baker} · {oph}")
else:
    self._ui(self._set_status, f"🍞 Transaction baked successfully! · {oph}")
else:
    self._ui(self._set_status, f"🥐 Still in the oven: {oph} (waiting for baker to finish…)")
```

#### app.py - Lines 1764-1775
```python
# BEFORE:
@work(exclusive=True, thread=True)
def _load_history(self, address: str, limit: int) -> None:
    self._ui(self._start_spinner, "⏳ Loading wallet information…")
    try:
        items = get_xtz_history(self.rpc, address, limit=limit)
        self.history_cache[(address, limit)] = items
        self._ui(self._render_history, items)
    except Exception as e:
        self._ui(self._render_history, [])
        self._ui(self._set_status, f"❌ History error: {e}")
    finally:
        self._ui(self._stop_spinner)
        self._ui(self._update_status_balance)

# AFTER:
@work(exclusive=True, thread=True)
def _load_history(self, address: str, limit: int) -> None:
    self._ui(self._start_spinner, "⏳ Checking the oven…")
    try:
        items = get_xtz_history(self.rpc, address, limit=limit)
        self.history_cache[(address, limit)] = items
        self._ui(self._render_history, items)
        self._ui(self._set_status, "🔄 Oven refreshed!")
    except Exception as e:
        self._ui(self._render_history, [])
        self._ui(self._set_status, f"❌ Oven check failed: {e}")
    finally:
        self._ui(self._stop_spinner)
        self._ui(self._update_status_balance)
```

#### app.py - Lines 1806-1811
```python
# BEFORE:
def action_refresh(self) -> None:
    self._update_status_balance()
    if self.selected:
        self._invalidate_history_cache(self.selected.address)
        self._load_history_for_selected(force=True)

# AFTER:
def action_refresh(self) -> None:
    self._update_status_balance()
    if self.selected:
        self._invalidate_history_cache(self.selected.address)
        self._load_history_for_selected(force=True)
    else:
        self._set_status("🔄 Oven refreshed!")
```

## User Experience Improvements

### Before
```
User sends transaction
  → Status: "🥖 Sending to the baker…"
  → Status: "🥐 Transaction in the oven: op123…"
  → Status: "🍞 Transaction baked successfully!"
  → [After 5 seconds] Status: "✓ Ready"
  ❌ Transaction hash is gone!
```

### After
```
User sends transaction
  → Status: "🥖 Putting the bread in the oven…"
  → Status: "🥐 Transaction in the oven: op123… | tzkt.io/op123"
  → Status: "🍞 Fresh from the oven! Block baked by tz1baker... · op123"
  → Status STAYS: "🍞 Fresh from the oven! Block baked by tz1baker... · op123"
  ✅ Transaction details remain visible!
```

## Testing

All existing tests pass:
```bash
✅ python3 test_new_layout.py
✅ python3 test_wallet_details_spacing.py
✅ python3 test_delegation_staking.py
✅ python3 -c "from app import WalletApp; app = WalletApp()"
```

## Documentation

Created three new documentation files:
1. **BAKING_THEMED_STATUS.md** - Complete guide to all status messages
2. **STATUS_QUICK_REFERENCE.md** - Quick visual reference for status flows
3. **CHANGELOG_CONTEXT_AWARE_STATUS.md** - This file

Updated:
- **STATUS_MESSAGE_IMPROVEMENTS.md** - Now outdated (replaced by new docs)

## Files Modified

- `app.py` - Main application file with all status message logic

## Breaking Changes

None. This is a UX improvement that doesn't change any APIs or data structures.

## Benefits

✅ **Context Preservation**: Users always know what the last action was
✅ **Information Retention**: Transaction hashes and links stay visible
✅ **Better Feedback**: Each action has meaningful final status
✅ **Consistent Theme**: All messages use baking terminology
✅ **Improved UX**: No more "Ready" generic state

## Future Enhancements

Possible improvements:
- Add more baking-themed messages for other actions
- Show time elapsed since last action
- Add clickable transaction hashes in status
- Status history (previous N statuses)

## Migration Notes

If you were relying on status being reset to "Ready":
- Status now persists until the next action
- Each action sets its own final status
- Use `_set_status()` to update status from any action

## Compatibility

- Fully compatible with existing code
- No changes to wallet functionality
- No changes to transaction processing
- Only affects UI status display

## Summary

This update transforms the status line from a temporary notification system into a persistent context display that maintains useful information about the last action performed, all while adding personality through consistent baking-themed messaging.

**Key Quote from User:**
> "I would like to have the Status to be more precise with the last thing performed in the App, if it was a Transaction, then at the end it should say something related to the transaction being sent, if the user press or click in refresh, then in the status show something related with that action"

This has been fully implemented! 🍞
