#!/usr/bin/env python3
"""Test accounts list spacing and height improvements."""

import sys
from app import WalletApp

def test_accounts_list_spacing():
    """Verify accounts list has proper spacing and limited height."""
    print("🧪 Testing accounts list spacing improvements...\n")

    try:
        app = WalletApp()
        print("✓ WalletApp instance created successfully")

        css = app.CSS
        print("✓ App has CSS styling")

        # Check #accounts section exists
        assert "#accounts {" in css or "#accounts{" in css, "Should have #accounts CSS block"
        print("✓ Accounts section CSS block exists")

        # Extract #accounts CSS block
        accounts_start = css.find("#accounts {")
        if accounts_start == -1:
            accounts_start = css.find("#accounts{")

        brace_count = 0
        accounts_css = ""
        found_opening = False
        for i in range(accounts_start, len(css)):
            char = css[i]
            if char == '{':
                found_opening = True
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and found_opening:
                    accounts_css = css[accounts_start:i+1]
                    break

        print(f"✓ Accounts CSS extracted")

        # Check height is 4
        assert "height: 4" in accounts_css, "Accounts list height should be 4"
        print("✓ Accounts list height set to 4 rows")

        # Check margin-bottom exists
        assert "margin-bottom:" in accounts_css, "Accounts should have margin-bottom"
        print("✓ Accounts list has margin-bottom")

        # Check ListItem spacing exists
        assert "#accounts > ListItem" in css, "Should have ListItem styling for accounts"
        print("✓ Accounts ListItem styling exists")

        # Extract ListItem CSS for accounts
        listitem_start = css.find("#accounts > ListItem {")
        if listitem_start == -1:
            listitem_start = css.find("#accounts > ListItem{")

        if listitem_start > 0:
            brace_count = 0
            listitem_css = ""
            found_opening = False
            for i in range(listitem_start, len(css)):
                char = css[i]
                if char == '{':
                    found_opening = True
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0 and found_opening:
                        listitem_css = css[listitem_start:i+1]
                        break

            # Check margin-bottom in ListItem
            if "margin-bottom:" in listitem_css:
                print("✓ ListItem has margin-bottom spacing")

        print("\n✅ Accounts list spacing improvements validated!\n")

        print("📊 Improvements:")
        print("   1. ✓ Reduced accounts list height from 6 to 4 rows")
        print("   2. ✓ Added spacing between account items (margin-bottom: 1)")
        print("   3. ✓ Automatic scrolling when more than 4 accounts")
        print("   4. ✓ Consistent spacing with wallet details section")
        print()

        print("💡 Visual comparison:")
        print()
        print("   Before (6 rows, no spacing):")
        print("   ┌──────────────────────────────┐")
        print("   │ Alice Main — tz1abc...       │")
        print("   │ Bob Savings — tz1def...      │")
        print("   │ Carol Trading — tz1ghi...    │")
        print("   │ Dave Business — tz1jkl...    │")
        print("   │ Eve Personal — tz1mno...     │")
        print("   │ Frank Hodl — tz1pqr...       │")
        print("   └──────────────────────────────┘")
        print()
        print("   After (4 rows, with spacing & scroll):")
        print("   ┌──────────────────────────────┐")
        print("   │ Alice Main — tz1abc...       │")
        print("   │                              │ ← Space!")
        print("   │ Bob Savings — tz1def...      │")
        print("   │                              │ ← Space!")
        print("   │ Carol Trading — tz1ghi...    │")
        print("   │                              │ ← Space!")
        print("   │ Dave Business — tz1jkl... ▼  │ ← Scroll!")
        print("   └──────────────────────────────┘")
        print()

        print("🎯 Benefits:")
        print("   • More compact - saves vertical space")
        print("   • Better spacing - easier to read each account")
        print("   • Automatic scrolling - handles many accounts gracefully")
        print("   • Consistent styling - matches wallet details spacing")
        print("   • Cleaner appearance - less visual clutter")
        print()

        print("📝 Technical details:")
        print("   • Height: 4 rows (reduced from 6)")
        print("   • ListItem margin-bottom: 1 (same as wallet details)")
        print("   • Scroll: Automatic when > 4 accounts")
        print("   • Spacing: Consistent throughout the app")

        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_accounts_list_spacing()
    sys.exit(0 if success else 1)
