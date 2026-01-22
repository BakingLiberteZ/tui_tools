# Status Message Timing Improvements

## Overview

Enhanced the status line messaging system to provide better visual feedback during transactions by slowing down animations and adding duration-based message display.

## Changes Made

### 1. Slowed Down Animation Timing

**Fun Message Rotation**:
- **Before**: Messages rotated every 30 ticks (3 seconds)
- **After**: Messages rotate every 60 ticks (6 seconds)
- **Benefit**: Users have more time to read each fun baker-themed message

**Blinking Effect**:
- **Before**: Blinked every 5 ticks (0.5 seconds)
- **After**: Blinks every 10 ticks (1 second)
- **Benefit**: Slower, more noticeable blinking effect

### 2. Added Duration-Based Display

Added `duration` parameter to `_set_status()` method:
```python
def _set_status(self, text: str, duration: float = 0) -> None
```

When `duration > 0`, the message stays visible for that many seconds before automatically returning to "✓ Ready" state.

### 3. Updated Transaction Messages

All transaction status messages now use duration to stay visible longer:

#### Transaction Injection (3 seconds)
```python
self._ui(self._set_status, f"🥐 Transaction in the oven: {oph}  |  {tzkt}/{oph}", 3.0)
```
Shows transaction hash and TzKT link for 3 seconds.

#### Transaction Success (5 seconds)
```python
# With baker information
self._ui(self._set_status, f"🍞 Fresh from the oven! Block baked by {baker} · {oph}", 5.0)

# Without baker information
self._ui(self._set_status, f"🍞 Transaction baked successfully! · {oph}", 5.0)
```
Success messages remain visible for 5 seconds so users can read them.

#### Transaction Pending (5 seconds)
```python
self._ui(self._set_status, f"🥐 In the oven: {oph} (waiting for baker to finish…)", 5.0)
```
When transaction is injected but not yet indexed, message stays visible for 5 seconds.

#### Transaction Failure (5 seconds)
```python
self._ui(self._set_status, f"❌ Baking failed: {e}", 5.0)
```
Error messages display for 5 seconds with baker theme consistency.

## User Experience Flow

### During Transaction Send:

1. **Start**: 🥖 Sending to the baker… *(spinner with blinking, rotating fun messages)*
2. **Injected**: 🥐 Transaction in the oven: [hash] | [tzkt link] *(3 seconds)*
3. **Waiting**: *(spinner continues with fun messages while polling for confirmation)*
4. **Success**: 🍞 Fresh from the oven! Block baked by [baker] · [hash] *(5 seconds)*
5. **Ready**: ✓ Ready *(automatic after 5 seconds)*

### Fun Messages During Waiting:

While the spinner runs, users see rotating baker-themed messages (every 6 seconds):
- "Waking up the baker... 👨‍🍳"
- "Preheating the oven... 🔥"
- "Kneading the dough... 🥖"
- "Baking fresh blocks... 🍞"
- "Rolling croissants... 🥐"
- And 19 more fun messages!

## Technical Implementation

### Threading Architecture

Status messages with duration use background threads:
```python
if duration > 0:
    def _reset_to_ready():
        time.sleep(duration)
        try:
            self.query_one("#status_line", Static).update("✓ Ready")
        except Exception:
            pass

    threading.Thread(target=_reset_to_ready, daemon=True).start()
```

This ensures:
- Non-blocking execution
- Automatic cleanup
- No UI freezing

### Timing Constants

```python
# Spinner tick rate: 0.1 seconds (10 ticks per second)
self.set_interval(0.1, self._tick_spinner)

# Fun message rotation: 60 ticks = 6 seconds
if self._spin_i > 0 and self._spin_i % 60 == 0:
    fun_idx = (self._spin_i // 60) % len(self.FUN_LOADING_MESSAGES)

# Blinking effect: 10 ticks = 1 second
blink = (self._spin_i // 10) % 2 == 0
```

## Benefits

### 1. Better Readability
- Messages stay visible long enough to read
- Slower animations are less jarring
- Success messages don't disappear too quickly

### 2. Visual Feedback
- Users know exactly what's happening
- Fun messages provide entertainment during waits
- Baker theme reinforces Tezos identity

### 3. Professional UX
- Consistent timing across all messages
- Smooth transitions
- No abrupt message changes

### 4. User Control
- Messages automatically clear to "Ready"
- No manual dismissal needed
- Focus returns to history automatically

## Testing

All existing tests pass:
```bash
✅ test_new_layout.py - Layout structure validated
✅ test_wallet_details_spacing.py - Spacing improvements validated
✅ test_delegation_staking.py - Delegation/staking display validated
```

## Files Modified

- **app.py**:
  - Updated `_tick_spinner()` timing (lines ~1388-1410)
  - Enhanced `_set_status()` with duration parameter (lines ~1416-1440)
  - Updated transaction messages (lines ~2020, 2056, 2058, 2061, 2072)

## Summary

✅ **Slowed animation timing** - 6s message rotation, 1s blinking
✅ **Added duration parameter** - Messages stay visible for specified time
✅ **Updated all transaction messages** - 3-5 second display times
✅ **Baker-themed error messages** - Consistent with app theme
✅ **Automatic cleanup** - Returns to "Ready" without user action
✅ **Non-blocking execution** - Uses background threads

The status line now provides excellent visual feedback during all operations while maintaining the fun, baker-themed personality!
