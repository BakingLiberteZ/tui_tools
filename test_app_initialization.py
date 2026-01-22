#!/usr/bin/env python3
"""Test that the app initializes correctly with the new wallet-specific recents."""

import sys
from app import WalletApp

def test_app_initialization():
    """Verify the app can initialize with new recent_to_by_wallet structure."""
    print("🧪 Testing app initialization with wallet-specific recents...\n")

    try:
        # Create app instance
        app = WalletApp()
        print("✓ WalletApp instance created successfully")

        # Check that recent_to_by_wallet exists
        assert hasattr(app, 'recent_to_by_wallet'), "App should have recent_to_by_wallet attribute"
        print("✓ App has recent_to_by_wallet attribute")

        # Check that it's a dictionary
        assert isinstance(app.recent_to_by_wallet, dict), "recent_to_by_wallet should be a dict"
        print("✓ recent_to_by_wallet is a dictionary")

        # Check helper method exists
        assert hasattr(app, '_get_recent_to_for_wallet'), "App should have _get_recent_to_for_wallet method"
        print("✓ App has _get_recent_to_for_wallet helper method")

        # Test getting recents for a non-existent wallet (should return empty list)
        fake_addr = "tz1fakeaddress123"
        recents = app._get_recent_to_for_wallet(fake_addr)
        assert isinstance(recents, list), "Should return a list"
        assert len(recents) == 0, "New wallet should have empty recents"
        print(f"✓ Getting recents for new wallet returns empty list")

        # Check store structure
        assert "recent_to_by_wallet" in app.store, "Store should have recent_to_by_wallet key"
        print("✓ Store has recent_to_by_wallet key")

        print("\n✅ All initialization tests passed!")
        print("\n📊 App structure:")
        print(f"   • Accounts loaded: {len(app.accounts)}")
        print(f"   • RPC: {app.rpc}")
        print(f"   • Wallet-specific recents: {len(app.recent_to_by_wallet)} wallets")

        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_app_initialization()
    sys.exit(0 if success else 1)
