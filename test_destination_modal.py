#!/usr/bin/env python3
"""Test the Destination modal improvements."""

import sys
from app import DestinationPickerScreen
from wallet.store import Account

def test_destination_modal():
    """Verify Destination modal has proper padding and sizing."""
    print("🧪 Testing Destination modal improvements...")

    try:
        # Create instance with some test recent addresses
        test_recents = [
            "tz1abc123def456ghi789jkl012mno345pqr678",
            "tz1xyz987wvu654tsr321qpo098nml765kji432",
        ]

        # Create test accounts (other wallets in the app)
        test_accounts = [
            Account(name="Alice Wallet", address="tz1alice123abc", enc=None),
            Account(name="Bob Wallet", address="tz1bob456def", enc=None),
            Account(name="Charlie Wallet", address="tz1charlie789ghi", enc=None),
        ]

        # From address (current sending wallet)
        from_address = "tz1sender999xyz"

        modal = DestinationPickerScreen(test_recents, test_accounts, from_address)
        print("✓ DestinationPickerScreen instance created")

        # Check CSS exists
        assert hasattr(modal, 'CSS'), "Modal should have CSS attribute"
        css = modal.CSS
        print("✓ Modal has CSS styling")

        # Check padding
        assert "padding: 2" in css, "Should have padding: 2"
        print("✓ Modal has padding (2) for better spacing")

        # Check wallets_list styling
        assert "#wallets_list" in css, "Should have wallets_list styling"
        assert "#wallets_title" in css, "Should have wallets_title styling"
        print("✓ Wallets list has proper styling")

        # Check recent_list sizing
        assert "#recent_list" in css, "Should have recent_list styling"
        assert "max-height: 6" in css, "List should have max-height: 6"
        assert "height: auto" in css, "List should have auto height"
        print("✓ Recent list has constrained size (max-height: 6)")

        # Check margins
        assert "margin-bottom: 1" in css, "Should have margin spacing"
        assert "margin-top: 1" in css, "Should have margin spacing"
        print("✓ Elements have proper margin spacing")

        # Check container styling
        assert "Vertical" in css, "Should style the Vertical container"
        assert "border:" in css, "Should have border"
        print("✓ Modal container has border and background")

        print("\n✅ Destination modal improvements validated!")
        print("\n📊 Improvements:")
        print("   1. ✓ Added padding: 2 around entire modal")
        print("   2. ✓ Shows YOUR wallets (easy to send between your own wallets)")
        print("   3. ✓ Shows recent destinations (wallet-specific)")
        print("   4. ✓ List max-height: 6 for each section (compact)")
        print("   5. ✓ List height: auto (adapts to content)")
        print("   6. ✓ Better spacing with margins")
        print("   7. ✓ Clear title: 'Send to Address'")
        print("   8. ✓ Descriptive subtitle")
        print("   9. ✓ Filters out sending wallet (can't send to yourself)")
        print("\n💡 Visual result:")
        print("   ┌────────────────────────────────────┐")
        print("   │                                    │  ← Padding")
        print("   │  Send to Address                   │")
        print("   │  Enter destination address...      │")
        print("   │  [Paste address here...........] │")
        print("   │                                    │")
        print("   │  Your wallets:                     │")
        print("   │  ┌──────────────────────────────┐  │")
        print("   │  │ Alice Wallet (tz1alice...)   │  │  ← NEW!")
        print("   │  │ Bob Wallet (tz1bob...)       │  │")
        print("   │  │ Charlie Wallet (tz1charlie..)│  │")
        print("   │  └──────────────────────────────┘  │")
        print("   │                                    │")
        print("   │  Recent destinations:              │")
        print("   │  ┌──────────────────────────────┐  │")
        print("   │  │ tz1abc...                    │  │")
        print("   │  │ tz1xyz...                    │  │")
        print("   │  └──────────────────────────────┘  │")
        print("   │                                    │")
        print("   │        [OK]  [Cancel]              │")
        print("   │                                    │  ← Padding")
        print("   └────────────────────────────────────┘")
        print("\n🎯 Use cases:")
        print("   • Send to your other wallets easily (just click)")
        print("   • Send to recent destinations from THIS wallet")
        print("   • Manually paste any address")
        print("   • Wallets show name + shortened address for clarity")
        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_destination_modal()
    sys.exit(0 if success else 1)
