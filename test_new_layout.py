#!/usr/bin/env python3
"""Test the new layout changes."""

import sys
from app import WalletApp

def test_new_layout():
    """Verify new layout structure."""
    print("🧪 Testing new layout...")

    try:
        app = WalletApp()
        print("✓ App instance created successfully")

        # Check CSS has new elements
        assert "#wallet_details" in app.CSS
        assert "#wallet_status" in app.CSS
        assert "#wallet_balance" in app.CSS
        assert "#wallet_delegation" in app.CSS
        assert "#wallet_staking" in app.CSS
        assert "#wallet_network" in app.CSS
        assert "#action_buttons" in app.CSS
        assert "#bottom_bar" in app.CSS
        assert "#rpc_indicator" in app.CSS
        print("✓ All new CSS elements present")

        # Check old elements are gone
        assert "#status_bar" not in app.CSS or "#status_left" not in app.CSS
        assert "#rpc_row" not in app.CSS
        assert "#menu_row" not in app.CSS
        print("✓ Old elements removed")

        # Check methods exist
        assert hasattr(app, '_update_rpc_indicator')
        assert hasattr(app, '_update_status_balance')
        print("✓ New methods exist")

        print("\n✅ New layout validated successfully!")
        print("\n📋 Layout changes:")
        print("   • RPC moved to bottom-right corner with green indicator")
        print("   • Wallet details section above history (name, address, balance, network)")
        print("   • Action buttons (Send, Receive, Refresh) below wallet details")
        print("   • Simplified status handling")
        print("   • Cleaner overall structure")
        print("\n💡 To see the new layout, run: python3 app.py")
        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_new_layout()
    sys.exit(0 if success else 1)
