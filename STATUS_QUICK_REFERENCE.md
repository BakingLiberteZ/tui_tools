# Status Messages Quick Reference

## Transaction Send Flow

```
┌──────────────────────────────────────────────────────────────┐
│                    TRANSACTION FLOW                          │
└──────────────────────────────────────────────────────────────┘

START: User clicks "Send"
   ↓
┌──────────────────────────────────────────────────────────────┐
│ 🥖 Putting the bread in the oven…                           │ ← Spinner active
│                                                              │    + rotating fun messages
│    [Rotating every 6 seconds:]                              │    + blinking effect
│    • Waking up the baker... 👨‍🍳                             │
│    • Preheating the oven... 🔥                              │
│    • Kneading the dough... 🥖                               │
│    • Baking fresh blocks... 🍞                              │
│    • Rolling croissants... 🥐                               │
│    • [20 more fun messages...]                              │
└──────────────────────────────────────────────────────────────┘
   ↓
INJECTED: Transaction broadcast to network
   ↓
┌──────────────────────────────────────────────────────────────┐
│ 🥐 Transaction in the oven: op123abc...def | tzkt.io/op... │ ← Stays visible
└──────────────────────────────────────────────────────────────┘
   ↓
WAITING: Polling for confirmation (spinner still active)
   ↓
┌─────────────────────── SUCCESS ──────────────────────────────┐
│                                                              │
│ With baker info:                                            │
│ 🍞 Fresh from the oven! Block baked by tz1baker... · op123 │ ← Stays forever
│                                                              │
│ Without baker info:                                         │
│ 🍞 Transaction baked successfully! · op123abc...           │ ← Stays forever
│                                                              │
└──────────────────────────────────────────────────────────────┘

         OR

┌─────────────────────── PENDING ──────────────────────────────┐
│ 🥐 Still in the oven: op123abc... (waiting for baker...)   │ ← Stays visible
└──────────────────────────────────────────────────────────────┘

         OR

┌──────────────────────── ERROR ───────────────────────────────┐
│ ❌ Baking failed: [error message]                           │ ← Stays visible
└──────────────────────────────────────────────────────────────┘
```

## Refresh Flow

```
┌──────────────────────────────────────────────────────────────┐
│                       REFRESH FLOW                           │
└──────────────────────────────────────────────────────────────┘

START: User presses "Refresh" or presses 'r'
   ↓
┌──────────────────────────────────────────────────────────────┐
│ ⏳ Checking the oven…                                        │ ← Spinner active
└──────────────────────────────────────────────────────────────┘
   ↓
LOADING: Fetching balance, history, delegation, staking
   ↓
┌─────────────────────── SUCCESS ──────────────────────────────┐
│ 🔄 Oven refreshed!                                           │ ← Stays visible
└──────────────────────────────────────────────────────────────┘

         OR

┌──────────────────────── ERROR ───────────────────────────────┐
│ ❌ Oven check failed: [error message]                       │ ← Stays visible
└──────────────────────────────────────────────────────────────┘
```

## Initial State

```
┌──────────────────────────────────────────────────────────────┐
│ 🍞 Oven ready!                                               │ ← App just loaded
└──────────────────────────────────────────────────────────────┘
```

## Key Principles

### 1. Status Persistence
✅ Messages **stay visible** until the next action
❌ No automatic reset to "Ready"
💡 Users can always see what the last action was

### 2. Context Awareness
Every action has its own final status:
- Transaction sent → Shows transaction details with hash
- Refresh completed → Shows "Oven refreshed!"
- Error occurred → Shows error with context

### 3. Baking Theme
All messages use baking terminology:
- "Putting the bread in the oven" = Sending transaction
- "Transaction in the oven" = Transaction injected
- "Fresh from the oven" = Transaction confirmed
- "Checking the oven" = Refreshing data
- "Oven refreshed" = Refresh complete

### 4. Visual Feedback During Waiting
While spinner is active:
- Rotating fun baker-themed messages (every 6 seconds)
- Blinking effect (every 1 second)
- 24 different messages for variety

## Status Emoji Legend

| Emoji | Meaning | When Used |
|-------|---------|-----------|
| 🍞 | Bread | Ready state, successful completion |
| 🥖 | Baguette | Starting an action |
| 🥐 | Croissant | In progress, pending |
| ⏳ | Hourglass | Loading |
| 🔄 | Refresh | Refresh completed |
| ❌ | Error | Action failed |
| ℹ️ | Info | Informational |
| ⚠️ | Warning | Warning/caution |
| 👨‍🍳 | Baker | Fun messages |
| 🔥 | Fire | Fun messages |

## Examples of Status Staying Visible

### Example 1: Transaction Success
```
User sends transaction
  → Status shows: "🥖 Putting the bread in the oven…"
  → After 5 seconds: "🥐 Transaction in the oven: op123… | link"
  → After confirmation: "🍞 Fresh from the oven! Block baked by tz1..."
  → User continues working
  → Status STILL shows: "🍞 Fresh from the oven! Block baked by tz1..."
  → User refreshes
  → Status changes to: "🔄 Oven refreshed!"
```

### Example 2: Multiple Actions
```
1. App starts → "🍞 Oven ready!"
2. User refreshes → "🔄 Oven refreshed!" (stays)
3. User sends transaction → "🍞 Transaction baked successfully! · op456" (stays)
4. User refreshes again → "🔄 Oven refreshed!" (stays)
5. User sends another transaction → "🍞 Fresh from the oven! Block baked by..." (stays)
```

## Benefits

✅ **Clear History**: Always know what the last action was
✅ **No Information Loss**: Transaction hashes don't disappear
✅ **Better UX**: Status provides context, not just notifications
✅ **Fun Theme**: Baking terminology adds personality
✅ **Consistent**: All actions follow the same pattern

## Technical Notes

### No Auto-Reset
The `_stop_spinner()` method no longer resets to "Ready":
```python
def _stop_spinner(self) -> None:
    # Stop the spinner
    self._spin_msg = None
    self._spin_i = 0
    # Don't reset status - let each action set its own final message
```

### Each Action Sets Status
Every action explicitly sets its final status:
```python
# Transaction success
self._ui(self._set_status, f"🍞 Fresh from the oven! Block baked by {baker} · {oph}")

# Refresh success
self._ui(self._set_status, "🔄 Oven refreshed!")

# Error
self._ui(self._set_status, f"❌ Baking failed: {e}")
```

### Status Stays Until Changed
```python
def _set_status(self, text: str) -> None:
    """Update status message (stays visible until next action)."""
    self._last_status = text
    self.query_one("#status_line", Static).update(text)
```

No duration parameter, no auto-reset. Simple and predictable!
