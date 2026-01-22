# Baking-Themed Status Messages

## Overview

The status line now maintains context-specific messages that reflect the last action performed, all using a fun baking theme that aligns with Tezos terminology.

## Key Changes

### 1. Context-Aware Status (No More Generic "Ready")

**Before**: All actions reset to "✓ Ready" after completion
**After**: Each action leaves a meaningful status message describing what just happened

### 2. Baking Theme Throughout

All status messages use baking-related terminology and emojis to create a fun, cohesive experience.

## Status Messages by Action

### Initial State
```
🍞 Oven ready!
```
Shows when the app first loads.

### Transaction Flow

#### 1. Sending Transaction (Spinner)
```
🥖 Putting the bread in the oven…
```
Shows while broadcasting the transaction to the network.

**Fun rotating messages** (every 6 seconds):
- "Waking up the baker... 👨‍🍳"
- "Preheating the oven... 🔥"
- "Kneading the dough... 🥖"
- "Baking fresh blocks... 🍞"
- "Rolling croissants... 🥐"
- "Sprinkling flour on validators... 👨‍🍳"
- "Mixing the sourdough starter... 🧑‍🍳"
- "Letting the dough rise... ⏰"
- "Checking the oven temperature... 🌡️"
- "Adding yeast to the network... 🧪"
- And 14 more fun messages!

#### 2. Transaction Injected
```
🥐 Transaction in the oven: [hash]  |  [tzkt-link]
```
Shows the transaction hash and TzKT explorer link. **Stays visible until next action.**

#### 3. Transaction Confirmed (Success)

**With baker information:**
```
🍞 Fresh from the oven! Block baked by [baker] · [hash]
```

**Without baker information:**
```
🍞 Transaction baked successfully! · [hash]
```

**Stays visible permanently** - no auto-reset to "Ready"!

#### 4. Transaction Pending
```
🥐 Still in the oven: [hash] (waiting for baker to finish…)
```
Shows when transaction is injected but not yet indexed. **Stays visible.**

#### 5. Transaction Failed
```
❌ Baking failed: [error message]
```
Shows if the transaction fails with error details. **Stays visible.**

### Refresh Action

#### While Loading (Spinner)
```
⏳ Checking the oven…
```
Shows during history/balance refresh.

#### After Successful Refresh
```
🔄 Oven refreshed!
```
Shows when refresh completes successfully. **Stays visible until next action.**

#### Refresh Failed
```
❌ Oven check failed: [error]
```
Shows if refresh encounters an error. **Stays visible.**

### Other Actions

#### No Account Selected (various actions)
```
ℹ️ No account selected
```

#### Watch-Only Account (trying to send)
```
⚠️ Selected account is watch-only. Add a secret key to send
```

#### No History Items
```
ℹ️ No history items
```

#### Invalid Selection
```
⚠️ Invalid selection
```

## User Experience Benefits

### 1. Context Awareness
Users always know what the last action was by reading the status line:
- Transaction sent? Status tells you which one
- Refreshed? Status confirms it
- Error? Status explains what failed

### 2. No Information Loss
Success messages **stay visible** instead of disappearing into "Ready":
- Transaction hashes remain visible for copying
- TzKT links remain visible for clicking
- Success confirmations don't vanish

### 3. Fun & Personality
Baking theme reinforces Tezos identity while adding personality:
- "Putting the bread in the oven" instead of "Sending transaction"
- "Oven refreshed" instead of "Refresh complete"
- "Fresh from the oven" instead of "Transaction confirmed"

### 4. Clear Feedback
Every action provides clear, themed feedback:
- Starting actions show what's happening (spinner + fun messages)
- Completing actions show what happened (final status)
- Errors clearly indicate what failed

## Technical Implementation

### Status Persistence

```python
def _set_status(self, text: str) -> None:
    """Update status message (stays visible until next action)."""
    self._last_status = text
    try:
        self.query_one("#status_line", Static).update(text)
    except Exception:
        pass
```

No automatic reset - each action explicitly sets its own status.

### Spinner Behavior

```python
def _stop_spinner(self) -> None:
    self._spin_msg = None
    self._spin_i = 0
    if self._spin_timer is not None:
        self._spin_timer.stop()
        self._spin_timer = None
    # Don't reset status - let each action set its own final message
```

Spinner stops without changing the status line.

### Transaction Messages

```python
# Start
self._ui(self._start_spinner, "🥖 Putting the bread in the oven…")

# Injected
self._ui(self._set_status, f"🥐 Transaction in the oven: {oph}  |  {tzkt}/{oph}")

# Success
if baker:
    self._ui(self._set_status, f"🍞 Fresh from the oven! Block baked by {baker} · {oph}")
else:
    self._ui(self._set_status, f"🍞 Transaction baked successfully! · {oph}")

# Pending
self._ui(self._set_status, f"🥐 Still in the oven: {oph} (waiting for baker to finish…)")

# Error
self._ui(self._set_status, f"❌ Baking failed: {e}")
```

### Refresh Messages

```python
# While loading
self._ui(self._start_spinner, "⏳ Checking the oven…")

# Success
self._ui(self._set_status, "🔄 Oven refreshed!")

# Error
self._ui(self._set_status, f"❌ Oven check failed: {e}")
```

## Visual Examples

### Transaction Success Flow
```
┌─────────────────────────────────────────────────────┐
│ Status: 🥖 Putting the bread in the oven…          │ ← Sending (spinner + rotating fun messages)
└─────────────────────────────────────────────────────┘

↓ After injection

┌─────────────────────────────────────────────────────┐
│ Status: 🥐 Transaction in the oven: op123… | link  │ ← Injected (stays visible)
└─────────────────────────────────────────────────────┘

↓ After confirmation

┌─────────────────────────────────────────────────────┐
│ Status: 🍞 Fresh from the oven! Block baked by …   │ ← Success (stays visible)
└─────────────────────────────────────────────────────┘

↓ User continues working, status remains until next action
```

### Refresh Flow
```
┌─────────────────────────────────────────────────────┐
│ Status: ⏳ Checking the oven…                       │ ← Refreshing (spinner)
└─────────────────────────────────────────────────────┘

↓ After refresh completes

┌─────────────────────────────────────────────────────┐
│ Status: 🔄 Oven refreshed!                          │ ← Complete (stays visible)
└─────────────────────────────────────────────────────┘
```

## Emoji Guide

| Emoji | Meaning | Usage |
|-------|---------|-------|
| 🍞 | Bread | Initial ready state, successful transactions |
| 🥖 | Baguette | Starting a transaction |
| 🥐 | Croissant | Transaction in progress, pending |
| 👨‍🍳 | Baker | Fun loading messages |
| 🔥 | Fire | Fun loading messages (preheating oven) |
| ⏳ | Hourglass | Loading/refreshing |
| 🔄 | Refresh | Refresh completed |
| ❌ | Error | Failed actions |
| ℹ️ | Info | Informational messages |
| ⚠️ | Warning | Warning messages |

## Testing

All tests pass with the new context-aware status system:
```bash
✅ test_new_layout.py
✅ test_wallet_details_spacing.py
✅ test_delegation_staking.py
```

## Summary

✅ **Context-aware status** - Shows what actually happened
✅ **No generic "Ready"** - Every action has meaningful status
✅ **Baking theme throughout** - Fun, consistent personality
✅ **Status persistence** - Messages stay until next action
✅ **Clear feedback** - Always know what the last action was
✅ **Transaction details preserved** - Hashes and links remain visible

The status line is now a useful reference for what just happened, not just a temporary notification!
