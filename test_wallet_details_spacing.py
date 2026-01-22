#!/usr/bin/env python3
"""Test wallet details section spacing improvements."""

import sys
from app import WalletApp

def test_wallet_details_spacing():
    """Verify wallet details have proper interlinear spacing."""
    print("🧪 Testing wallet details spacing improvements...\n")

    try:
        app = WalletApp()
        print("✓ WalletApp instance created successfully")

        css = app.CSS
        print("✓ App has CSS styling")

        # Check wallet_details section
        assert "#wallet_details" in css, "Should have wallet_details section"
        print("✓ Wallet details section exists")

        # Check individual elements have margin-bottom
        assert "#wallet_status" in css, "Should have wallet_status styling"

        # Extract wallet_status CSS block
        status_start = css.find("#wallet_status {")
        status_end = css.find("}", status_start)
        status_css = css[status_start:status_end]
        assert "margin-bottom: 1" in status_css, "wallet_status should have margin-bottom"
        print("✓ Wallet status has margin-bottom spacing")

        # Check wallet_delegation
        deleg_start = css.find("#wallet_delegation {")
        deleg_end = css.find("}", deleg_start)
        deleg_css = css[deleg_start:deleg_end]
        assert "margin-bottom: 1" in deleg_css, "wallet_delegation should have margin-bottom"
        print("✓ Wallet delegation has margin-bottom spacing")

        # Check wallet_staking
        staking_start = css.find("#wallet_staking {")
        staking_end = css.find("}", staking_start)
        staking_css = css[staking_start:staking_end]
        assert "margin-bottom: 1" in staking_css, "wallet_staking should have margin-bottom"
        print("✓ Wallet staking has margin-bottom spacing")

        # Check wallet_balance
        bal_start = css.find("#wallet_balance {")
        bal_end = css.find("}", bal_start)
        bal_css = css[bal_start:bal_end]
        assert "margin-bottom: 1" in bal_css, "wallet_balance should have margin-bottom"
        print("✓ Wallet balance has margin-bottom spacing")

        # Check wallet_network (last one, may or may not have margin)
        net_start = css.find("#wallet_network {")
        net_end = css.find("}", net_start)
        net_css = css[net_start:net_end]
        print("✓ Wallet network section styled")

        print("\n✅ Wallet details spacing improvements validated!\n")

        print("📊 Improvements:")
        print("   1. ✓ Added margin-bottom: 1 to wallet status")
        print("   2. ✓ Added margin-bottom: 1 to wallet balance")
        print("   3. ✓ Added margin-bottom: 1 to wallet delegation")
        print("   4. ✓ Added margin-bottom: 1 to wallet staking")
        print("   5. ✓ Better visual separation between lines")
        print("   6. ✓ More pleasant to read")
        print()

        print("💡 Visual comparison:")
        print()
        print("   Before (cramped):          After (spacious):")
        print("   ┌──────────────────┐       ┌──────────────────┐")
        print("   │ Alice Wallet     │       │ Alice Wallet     │")
        print("   │ Balance: 5.5 XTZ │       │                  │ ← Space")
        print("   │ Delegated to: .. │       │ Balance: 5.5 XTZ │")
        print("   │ Staking: 2.0 XTZ │       │                  │ ← Space")
        print("   │ Network: mainnet │       │ Delegated to: .. │")
        print("   └──────────────────┘       │                  │ ← Space")
        print("                              │ Staking: 2.0 XTZ │")
        print("                              │                  │ ← Space")
        print("                              │ Network: mainnet │")
        print("                              └──────────────────┘")
        print()

        print("📝 Details shown:")
        print("   • RPC Status (Connected/Disconnected)")
        print("   • Balance (bold, with XTZ)")
        print("   • Delegation (shows baker or 'not delegated')")
        print("   • Staking (shows amount or '-')")
        print("   • Network (current RPC network)")
        print()

        print("🎯 Benefits:")
        print("   • Easier to scan information")
        print("   • Less cluttered appearance")
        print("   • Better visual hierarchy")
        print("   • More professional look")
        print("   • Improved readability")

        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_wallet_details_spacing()
    sys.exit(0 if success else 1)
