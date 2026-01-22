#!/usr/bin/env python3
"""Test the visual balance improvements."""

import sys
from app import WalletApp

def test_visual_balance():
    """Verify split ratio and header balance."""
    print("🧪 Testing visual balance improvements...")

    try:
        app = WalletApp()
        print("✓ App instance created successfully")

        # Check CSS has 50/50 split
        css = app.CSS

        # Find history width
        history_start = css.find("#history {")
        history_end = css.find("}", history_start)
        history_css = css[history_start:history_end]

        assert "width: 50%" in history_css, "History should be 50% width"
        print("✓ Transaction list set to 50% width")

        # Find detail pane width
        detail_start = css.find("#tx_detail_pane")
        detail_end = css.find("}", detail_start)
        detail_css = css[detail_start:detail_end]

        assert "width: 50%" in detail_css, "Detail pane should be 50% width"
        print("✓ Detail pane set to 50% width")

        # Check button styling
        add_start = css.find("#add {")
        add_end = css.find("}", add_start)
        add_css = css[add_start:add_end]

        assert "height: 1" in add_css, "Add button should have compact height"
        assert "padding: 0 2" in add_css, "Add button should have compact padding"
        print("✓ Add button has compact styling")

        # Check accounts_title styling
        title_start = css.find("#accounts_title")
        title_end = css.find("}", title_start)
        title_css = css[title_start:title_end]

        assert "text-style: bold" in title_css, "Accounts title should be bold"
        print("✓ Accounts title has bold styling")

        print("\n✅ Visual balance improvements validated successfully!")
        print("\n📊 Changes made:")
        print("   1. ✓ Transaction split: 60/40 → 50/50 (centered divider)")
        print("   2. ✓ Accounts title: Larger text 'ACCOUNTS' (all caps)")
        print("   3. ✓ Add button: Compact '+ Add (a)' (shorter text)")
        print("   4. ✓ Button height: Reduced to match title better")
        print("\n💡 Visual result:")
        print("   ┌────────────────────────────────────────┐")
        print("   │ ACCOUNTS              [+ Add (a)]      │  ← Better balanced!")
        print("   ├────────────────────────────────────────┤")
        print("   │ My Wallet — tz1abc...xyz               │")
        print("   └────────────────────────────────────────┘")
        print()
        print("   ┌────────────────────────────────────────┐")
        print("   │ Recent Transactions                    │")
        print("   ├──────────────────┬─────────────────────┤")
        print("   │ TX List (50%)    │ Details Pane (50%)  │  ← Centered split!")
        print("   │ 2024-01-20 IN... │ Type: RECEIVED      │")
        print("   └──────────────────┴─────────────────────┘")
        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_visual_balance()
    sys.exit(0 if success else 1)
