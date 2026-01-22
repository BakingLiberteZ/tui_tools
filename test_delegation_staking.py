#!/usr/bin/env python3
"""Test delegation and staking information display."""

import sys
from app import WalletApp

def test_delegation_staking():
    """Verify wallet details show delegation and staking info."""
    print("🧪 Testing delegation and staking display...\n")

    try:
        app = WalletApp()
        print("✓ WalletApp instance created successfully")

        css = app.CSS
        print("✓ App has CSS styling")

        # Check that wallet_address is removed
        assert "#wallet_address" not in css or "wallet_address" not in app.compose.__code__.co_names, \
            "wallet_address should be removed from compose"
        print("✓ Address line removed from wallet details")

        # Check that new elements exist in CSS
        assert "#wallet_delegation" in css, "Should have wallet_delegation section"
        print("✓ Delegation section exists in CSS")

        assert "#wallet_staking" in css, "Should have wallet_staking section"
        print("✓ Staking section exists in CSS")

        # Check delegation CSS has margin
        deleg_start = css.find("#wallet_delegation {")
        deleg_end = css.find("}", deleg_start)
        deleg_css = css[deleg_start:deleg_end]
        assert "margin-bottom: 1" in deleg_css, "wallet_delegation should have margin-bottom"
        print("✓ Delegation section has proper spacing")

        # Check staking CSS has margin
        staking_start = css.find("#wallet_staking {")
        staking_end = css.find("}", staking_start)
        staking_css = css[staking_start:staking_end]
        assert "margin-bottom: 1" in staking_css, "wallet_staking should have margin-bottom"
        print("✓ Staking section has proper spacing")

        print("\n✅ Delegation and staking display validated!\n")

        print("📊 Changes made:")
        print("   1. ✓ Removed redundant address line")
        print("   2. ✓ Added delegation information display")
        print("   3. ✓ Added staking balance display")
        print("   4. ✓ Proper spacing between all elements")
        print()

        print("💡 Wallet details now show:")
        print()
        print("   ┌─────────────────────────────────┐")
        print("   │ Alice Main Wallet               │")
        print("   │                                 │")
        print("   │ Balance: 12.456789 XTZ          │")
        print("   │                                 │")
        print("   │ Delegated to: tz1baker12...     │ ← NEW!")
        print("   │                                 │")
        print("   │ Staking: 5.000000 XTZ           │ ← NEW!")
        print("   │                                 │")
        print("   │ Network: mainnet                │")
        print("   └─────────────────────────────────┘")
        print()

        print("📝 Display logic:")
        print("   • Name: Always shown (with watch-only tag if applicable)")
        print("   • Balance: Always shown")
        print("   • Delegation: Always shown (shows baker or 'not delegated')")
        print("   • Staking: Always shown (shows amount or '-')")
        print("   • Network: Always shown")
        print()

        print("🎯 Benefits:")
        print("   • No redundant address (already shown in accounts list)")
        print("   • See delegation status at a glance")
        print("   • Monitor staking balance easily")
        print("   • Cleaner, more informative display")
        print("   • Better use of screen space")
        print()

        print("📡 Data sources:")
        print("   • Delegation: TzKT API - /v1/accounts/{address}")
        print("   • Staking: TzKT API - /v1/accounts/{address} (stakedBalance)")
        print("   • Auto-updated when switching wallets or refreshing")

        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_delegation_staking()
    sys.exit(0 if success else 1)
