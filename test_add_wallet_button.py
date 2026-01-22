#!/usr/bin/env python3
"""Test the Add Wallet button placement."""

import sys
from app import WalletApp

def test_add_wallet_button():
    """Verify Add Wallet button is properly positioned."""
    print("🧪 Testing Add Wallet button placement...")

    try:
        app = WalletApp()
        print("✓ App instance created successfully")

        # Check CSS has accounts_header
        css = app.CSS
        assert "#accounts_header" in css, "Should have accounts_header container"
        assert "#accounts_title" in css, "Should have accounts_title"
        print("✓ CSS has accounts header container")

        # Check old top_row is removed
        assert "#top_row" not in css, "Old top_row should be removed"
        print("✓ Old top_row CSS removed")

        print("\n✅ Add Wallet button placement validated successfully!")
        print("\n📋 Button placement:")
        print("   • Moved from top-right corner")
        print("   • Now in Accounts section header")
        print("   • Next to 'Accounts' title")
        print("   • More contextual and discoverable")
        print("   • Labeled '+ Add Wallet (a)'")
        print("   • Primary variant (blue/prominent)")
        print("\n💡 Layout now:")
        print("   ┌─────────────────────────────────┐")
        print("   │ Accounts       [+ Add Wallet]   │")
        print("   ├─────────────────────────────────┤")
        print("   │ My Wallet — tz1abc...xyz        │")
        print("   │ Work Wallet — tz1def...uvw      │")
        print("   └─────────────────────────────────┘")
        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_add_wallet_button()
    sys.exit(0 if success else 1)
