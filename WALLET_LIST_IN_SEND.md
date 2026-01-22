# Wallet List in Send Destination Modal

## Overview

The Send Address modal now displays **both your loaded wallets AND recent destinations**, making it easy to send funds between your own wallets or to frequently used addresses.

## What Changed

### Before
- Only showed recent destinations
- To send to another wallet, you had to:
  1. Open the other wallet
  2. Copy its address
  3. Switch back to sending wallet
  4. Paste the address

### After
- Shows **Your wallets** section with all loaded wallets (except the sending wallet)
- Shows **Recent destinations** section (wallet-specific)
- Click any wallet to select it as destination
- Shows wallet name + shortened address for clarity
- Prevents sending to yourself (filtered automatically)

## Features

### 1. **Wallet List Section**

The modal now includes a "Your wallets" section showing all wallets loaded in the app:

```
Your wallets:
┌──────────────────────────────┐
│ Alice Wallet (tz1alice...)   │  ← Click to send to this wallet
│ Bob Wallet (tz1bob...)       │
│ Charlie Wallet (tz1charlie..)│
└──────────────────────────────┘
```

**Display Format:**
- Shows: `Name (shortened_address)`
- Example: `Alice Wallet (tz1alice12...abc456)`
- Shortened: First 10 characters + "..." + Last 6 characters

### 2. **Automatic Filtering**

The sending wallet is **automatically excluded** from the destination list:

```python
# Filter out the sending wallet (can't send to yourself)
self.accounts = [acc for acc in accounts if acc.address != from_address]
```

**Examples:**
- If Alice is sending → Alice's wallet is hidden
- If Bob is sending → Bob's wallet is hidden
- If only one wallet exists → Wallet section is empty

### 3. **Two Sections**

The modal is organized into two clear sections:

1. **Your wallets** (top)
   - All loaded wallets except the sender
   - Show wallet name for easy identification
   - Max height: 6 rows (scrollable if more)

2. **Recent destinations** (bottom)
   - Wallet-specific recent sends
   - Shows full addresses
   - Max height: 6 rows (scrollable if more)

### 4. **Selection Behavior**

Click or navigate to any wallet/address:
- Automatically fills the input field
- Press OK to confirm
- Press Cancel to abort

## Technical Implementation

### Code Changes

**1. Updated DestinationPickerScreen initialization:**

```python
def __init__(self, recents: list[str], accounts: list, from_address: str):
    super().__init__()
    self.recents = recents[:10]
    # Filter out the sending wallet (can't send to yourself)
    self.accounts = [acc for acc in accounts if acc.address != from_address]
    self.from_address = from_address
```

**2. Updated compose method:**

```python
def compose(self) -> ComposeResult:
    with Vertical():
        yield Static("[b]Send to Address[/b]", markup=True)
        yield Static("Enter destination address (tz1/tz2/tz3/tz4 or KT1)", markup=True)
        yield Input(placeholder="Paste address here…", id="dest_inp")

        # Your wallets section (NEW!)
        if self.accounts:
            yield Static("Your wallets:", id="wallets_title", markup=True)
            yield ListView(id="wallets_list")

        # Recent destinations section
        yield Static("Recent destinations:", id="recent_title", markup=True)
        yield ListView(id="recent_list")

        with Horizontal():
            yield Button("OK", id="ok")
            yield Button("Cancel", id="cancel")
```

**3. Updated on_mount to populate wallets:**

```python
def on_mount(self) -> None:
    self.query_one("#dest_inp", Input).focus()

    # Populate wallets list (NEW!)
    if self.accounts:
        wl = self.query_one("#wallets_list", ListView)
        wl.clear()
        for acc in self.accounts:
            # Show name and shortened address
            display = f"{acc.name} ({acc.address[:10]}...{acc.address[-6:]})"
            lbl = Label(display)
            lbl.tooltip = acc.address  # Full address on hover
            wl.append(ListItem(lbl))

    # Populate recent destinations list
    lv = self.query_one("#recent_list", ListView)
    lv.clear()
    if not self.recents:
        lv.append(ListItem(Label("[dim]No recent destinations yet[/dim]", markup=True)))
    else:
        for a in self.recents:
            lv.append(ListItem(Label(a)))
```

**4. Added wallet selection handler:**

```python
@on(ListView.Selected, "#wallets_list")
def pick_wallet(self, event: ListView.Selected) -> None:
    idx = event.list_view.index
    if idx is None:
        return
    if 0 <= idx < len(self.accounts):
        self.query_one("#dest_inp", Input).value = self.accounts[idx].address
```

**5. Updated call site in action_send:**

```python
# Get recent destinations for the selected wallet only
wallet_recents = self._get_recent_to_for_wallet(self.selected.address)
to_addr = await self.push_screen_wait(
    DestinationPickerScreen(wallet_recents, self.accounts, self.selected.address)
)
```

### CSS Styling

```python
CSS = """
DestinationPickerScreen {
    align: center middle;
}

DestinationPickerScreen > Vertical {
    width: 80;
    height: auto;
    background: $surface;
    border: solid $primary;
    padding: 2;
}

#dest_inp {
    margin-bottom: 1;
}

#wallets_title {
    margin-top: 1;
    margin-bottom: 1;
}

#wallets_list {
    height: auto;
    max-height: 6;
    margin-bottom: 1;
}

#recent_title {
    margin-top: 1;
    margin-bottom: 1;
}

#recent_list {
    height: auto;
    max-height: 6;
    margin-bottom: 1;
}
"""
```

## Use Cases

### 1. **Send Between Your Own Wallets**

**Before:**
1. Note down destination wallet address
2. Switch to sending wallet
3. Click Send
4. Manually type/paste address
5. Risk of typos

**After:**
1. Click Send
2. See all your wallets listed
3. Click the destination wallet
4. Done! ✅

### 2. **Send to Recent Address**

**Before:**
- Recent addresses were global (all wallets)
- Confusing mix of your addresses and external ones

**After:**
- Recent addresses are wallet-specific
- Clear separation: "Your wallets" vs "Recent destinations"
- Each wallet shows only its own transaction history

### 3. **Send to New Address**

**Before:**
- Type or paste address

**After:**
- Same! Just type or paste in the input field
- The lists are optional helpers

## Benefits

### 1. **Convenience**
- ✅ No need to copy/paste between your own wallets
- ✅ One click to select a destination
- ✅ Clear visual display with wallet names

### 2. **Safety**
- ✅ Impossible to send to yourself (filtered out)
- ✅ No typos when sending to your wallets (click selection)
- ✅ Clear visual confirmation of selected wallet

### 3. **Organization**
- ✅ "Your wallets" vs "Recent destinations" separation
- ✅ Easy to distinguish internal vs external transfers
- ✅ Wallet names make identification quick

### 4. **Privacy**
- ✅ Recent destinations remain wallet-specific
- ✅ Each wallet only shows its own history
- ✅ No cross-contamination between wallet histories

## Testing

Three comprehensive test files verify the implementation:

### 1. **test_destination_modal.py**
- Tests CSS styling
- Verifies wallet list and recent list exist
- Checks proper padding and spacing

### 2. **test_wallet_filtering.py**
- Verifies sending wallet is excluded
- Tests with multiple wallets
- Tests with single wallet (edge case)
- Verifies wallets and recents work independently

### 3. **test_all_modals.py**
- Ensures all modals still work correctly
- Confirms consistent styling across app

Run tests:
```bash
python3 test_destination_modal.py
python3 test_wallet_filtering.py
python3 test_all_modals.py
```

## Visual Example

```
┌────────────────────────────────────────────┐
│                                            │
│  Send to Address                           │
│  Enter destination address (tz1/tz2...)    │
│  [Paste address here...................]   │
│                                            │
│  Your wallets:                             │
│  ┌────────────────────────────────────┐   │
│  │ Alice Wallet (tz1alice12...abc456) │   │ ← Your other wallets
│  │ Bob Wallet (tz1bob345...def789)    │   │   (click to select)
│  │ Charlie Wallet (tz1charlie...ghi0) │   │
│  └────────────────────────────────────┘   │
│                                            │
│  Recent destinations:                      │
│  ┌────────────────────────────────────┐   │
│  │ tz1external123abc456def789ghi...   │   │ ← Addresses you've
│  │ tz1exchange987xyz654wvu321pqr...   │   │   sent to before
│  └────────────────────────────────────┘   │
│                                            │
│        [OK]  [Cancel]                      │
│                                            │
└────────────────────────────────────────────┘
```

## Future Enhancements

Possible improvements:
- Add wallet balance next to each wallet name
- Show last transaction time for recent destinations
- Add "favorites" or "contacts" with custom labels
- Search/filter functionality for large wallet lists
- Export/import contact lists
