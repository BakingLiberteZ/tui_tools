# 🔴 Delete Button Visual Warnings

## 📅 Date
2026-01-21

## 🎯 Change Summary

Added visual warnings to Delete flow with red buttons to alert users before dangerous operations.

---

## ❓ User Request

"El boton dentro del modal de Delete, una vez el usuario seleccione la cartera, debe ser ROJO también para generar un aviso visual de que va a hacer algo delicado. Igual podemos generar un warning adicional una vez le de click o enter al botón delete dentro del modal para que confirme la acción."

---

## 🔧 Changes Implemented

### 1. Red Delete Button in Wallet Selector

**Modified**: `WalletSelectorScreen` class to support button variants

**Added Parameter**:
```python
def __init__(self, accounts: list, title: str = "Select Wallet",
             message: str = "Choose a wallet:",
             button_label: str = "Select",
             button_variant: str = "primary"):  # ✅ New parameter
    # ...
    self.button_variant = button_variant
```

**Updated compose**:
```python
def compose(self) -> ComposeResult:
    with Vertical():
        yield Static(f"[b]{self.title_text}[/b]\n{self.message_text}", id="title", markup=True)
        yield ListView(id="wallets_list")
        with Horizontal():
            yield Button(self.button_label, id="select", variant=self.button_variant)  # ✅ Uses variant
            yield Button("Cancel", id="cancel")
```

**Updated DeleteWalletSelectorScreen call**:
```python
selected_account = await self.push_screen_wait(
    DeleteWalletSelectorScreen(
        self.accounts,
        title="Delete Wallet",
        message="Select wallet to delete:",
        button_label="Delete",
        button_variant="error"  # ✅ Red button
    )
)
```

---

### 2. Confirmation Dialog (Already Existed)

The confirmation dialog already has excellent visual warnings:

```python
confirmed = await self.push_screen_wait(
    ConfirmScreen(
        f"Are you sure you want to delete wallet '[b]{wallet_name}[/b]'?\n\n"
        f"Address: [dim]{wallet_addr}[/dim]\n\n"
        f"[yellow]⚠️ This action cannot be undone![/yellow]\n"  # ⚠️ Warning
        f"[dim](The wallet will only be removed from this app,\n"
        f"not from the blockchain)[/dim]",
        title="Delete Wallet",
        yes_label="Delete",  # Red button (variant="error")
        no_label="Cancel"    # Blue button (variant="primary")
    )
)
```

**ConfirmScreen** already implements:
- ✅ `variant="error"` for Delete button (RED)
- ✅ `variant="primary"` for Cancel button (BLUE)
- ✅ Focus on Cancel by default (safer)
- ✅ Yellow warning text "⚠️ This action cannot be undone!"

---

## 🎨 Visual Flow

### Step 1: Click Delete Button (Top Panel)
```
┌────────────────────────────────────┐
│ [Import] [Backup] [Delete]         │
└────────────────────────────────────┘
                      ↑
                   RED button (#ef4444)
```

### Step 2: Select Wallet Modal
```
┌──────────────────────────────────────────┐
│ Delete Wallet                            │  ← Red border
├──────────────────────────────────────────┤
│ Select wallet to delete:                 │
│                                          │
│ ┌──────────────────────────────────────┐ │
│ │ • My Wallet     (tz1abc...)          │ │
│ │ • Test Wallet   (tz2def...)          │ │
│ └──────────────────────────────────────┘ │
│                                          │
│     [DELETE (RED)] [Cancel]              │  ← Delete button is RED!
└──────────────────────────────────────────┘
```

### Step 3: Confirmation Dialog
```
┌──────────────────────────────────────────┐
│ Delete Wallet                            │
├──────────────────────────────────────────┤
│                                          │
│ Are you sure you want to delete          │
│ wallet 'My Wallet'?                      │
│                                          │
│ Address: tz1abc...                       │
│                                          │
│ ⚠️ This action cannot be undone!         │  ← Yellow warning
│                                          │
│ (The wallet will only be removed from    │
│ this app, not from the blockchain)       │
│                                          │
│     [DELETE (RED)] [Cancel (BLUE)]       │  ← Delete is RED!
│              ↑                           │  ← Cancel is focused
└──────────────────────────────────────────┘
```

---

## ✅ Safety Features

### Visual Warnings
1. ✅ **Red border** on DeleteWalletSelectorScreen (#ef4444)
2. ✅ **Red Delete button** in selector modal (variant="error")
3. ✅ **Red Delete button** in confirmation dialog (variant="error")
4. ✅ **Yellow warning icon** ⚠️ in confirmation text
5. ✅ **Bold wallet name** to emphasize what's being deleted

### Behavioral Safeguards
1. ✅ **Two-step process**: Select wallet → Confirm deletion
2. ✅ **Cancel focused by default** in confirmation (prevents accidental Enter)
3. ✅ **Escape key cancels** at any point
4. ✅ **Clear messaging**: "This action cannot be undone!"
5. ✅ **Blockchain clarification**: Wallet only removed from app, not blockchain

---

## 🧪 Testing

Test the delete flow:

1. **Click Delete button** (top panel)
   - [ ] Red button color visible

2. **Select wallet modal**
   - [ ] Red border around modal
   - [ ] Delete button is RED (not blue)
   - [ ] Cancel button is visible
   - [ ] Can cancel with Escape

3. **Click Delete button in modal**
   - [ ] Confirmation dialog appears
   - [ ] Delete button is RED
   - [ ] Cancel button is BLUE and focused
   - [ ] Yellow warning icon ⚠️ visible
   - [ ] Wallet name in bold

4. **Test cancellation**
   - [ ] Escape cancels at any step
   - [ ] Cancel button works in both modals
   - [ ] No wallet deleted when cancelled

5. **Test deletion**
   - [ ] Delete button confirms action
   - [ ] Wallet removed from list
   - [ ] Success message shown

---

## 📊 Color Scheme

| Element | Color | Variant | Purpose |
|---------|-------|---------|---------|
| Delete button (top) | #ef4444 | - | Red = danger |
| Selector modal border | #ef4444 | - | Red = danger |
| Delete button (selector) | Red | error | Visual warning |
| Delete button (confirm) | Red | error | Visual warning |
| Cancel button | Blue | primary | Safe default |
| Warning text | Yellow | - | Attention |

---

## 💡 UX Design Notes

### Why Two Steps?
1. **Selection**: User picks which wallet to delete
   - Prevents accidental deletion of wrong wallet
   - Shows red visual warning

2. **Confirmation**: User confirms the specific wallet
   - Shows exact wallet name and address
   - Requires explicit confirmation
   - Focus on Cancel prevents accidental Enter

### Why Red Buttons?
- Universal color for danger/destructive actions
- Creates visual consistency (red throughout delete flow)
- Immediately signals "be careful" to user
- Matches other UI patterns (error messages, warnings)

### Why Cancel Focused?
- Safer default (prevents accidental deletion)
- User must actively Tab/click to Delete button
- Common pattern in destructive operation confirmations
- Gives user moment to reconsider

---

## 📚 Files Modified

### app.py

1. **WalletSelectorScreen.__init__** (line ~767)
   - Added `button_variant` parameter

2. **WalletSelectorScreen.compose** (line ~780)
   - Uses `self.button_variant` for button variant

3. **action_delete_wallet** (line ~2727)
   - Added `button_variant="error"` to DeleteWalletSelectorScreen call

---

## 🎉 Result

Delete flow now has **triple visual protection**:

1. 🔴 Red border on selector modal
2. 🔴 Red Delete button in selector
3. 🔴 Red Delete button in confirmation
4. ⚠️ Yellow warning text
5. 🎯 Cancel focused by default

**Users cannot accidentally delete wallets!** 🛡️

---

**Change Type**: UI Enhancement (Safety)
**Status**: ✅ Completed
**Impact**: Positive (prevents accidental deletions)
**User-facing Change**: Yes (red buttons)
