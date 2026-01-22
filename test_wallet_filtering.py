#!/usr/bin/env python3
"""Test that the sending wallet is filtered from the destination list."""

import sys
from app import DestinationPickerScreen
from wallet.store import Account

def test_wallet_filtering():
    """Verify that the sending wallet is excluded from the destination options."""
    print("🧪 Testing wallet filtering in destination modal...\n")

    try:
        # Create test accounts
        alice = Account(name="Alice", address="tz1alice123", enc=None)
        bob = Account(name="Bob", address="tz1bob456", enc=None)
        charlie = Account(name="Charlie", address="tz1charlie789", enc=None)
        david = Account(name="David", address="tz1david012", enc=None)

        all_accounts = [alice, bob, charlie, david]

        print("📋 All wallets in app:")
        for acc in all_accounts:
            print(f"   • {acc.name} ({acc.address})")
        print()

        # Test 1: Send FROM Alice
        print("Test 1: Alice is sending")
        from_address = alice.address
        modal = DestinationPickerScreen([], all_accounts, from_address)

        print(f"   From:     {alice.name}")
        print(f"   Available destinations: {len(modal.accounts)}")
        for acc in modal.accounts:
            print(f"      • {acc.name}")

        assert len(modal.accounts) == 3, "Should have 3 destination options (excluding Alice)"
        assert alice not in modal.accounts, "Alice should NOT be in the list"
        assert bob in modal.accounts, "Bob should be available"
        assert charlie in modal.accounts, "Charlie should be available"
        assert david in modal.accounts, "David should be available"
        print("   ✓ Alice excluded from destinations (can't send to herself)\n")

        # Test 2: Send FROM Bob
        print("Test 2: Bob is sending")
        from_address = bob.address
        modal = DestinationPickerScreen([], all_accounts, from_address)

        print(f"   From:     {bob.name}")
        print(f"   Available destinations: {len(modal.accounts)}")
        for acc in modal.accounts:
            print(f"      • {acc.name}")

        assert len(modal.accounts) == 3, "Should have 3 destination options (excluding Bob)"
        assert bob not in modal.accounts, "Bob should NOT be in the list"
        assert alice in modal.accounts, "Alice should be available"
        assert charlie in modal.accounts, "Charlie should be available"
        assert david in modal.accounts, "David should be available"
        print("   ✓ Bob excluded from destinations (can't send to himself)\n")

        # Test 3: Send FROM Charlie (only wallet in app)
        print("Test 3: Charlie is the only wallet")
        from_address = charlie.address
        modal = DestinationPickerScreen([], [charlie], from_address)

        print(f"   From:     {charlie.name}")
        print(f"   Available destinations: {len(modal.accounts)}")
        if modal.accounts:
            for acc in modal.accounts:
                print(f"      • {acc.name}")
        else:
            print("      (none - Charlie has no other wallets)")

        assert len(modal.accounts) == 0, "Should have 0 destinations (Charlie is the only wallet)"
        print("   ✓ No wallets shown when only one wallet exists\n")

        # Test 4: Verify recents still work
        print("Test 4: Recent destinations still work independently")
        test_recents = ["tz1external123", "tz1external456"]
        modal = DestinationPickerScreen(test_recents, all_accounts, alice.address)

        print(f"   From:     {alice.name}")
        print(f"   Wallets available: {len(modal.accounts)}")
        print(f"   Recent destinations: {len(modal.recents)}")
        for rec in modal.recents:
            print(f"      • {rec}")

        assert len(modal.recents) == 2, "Recents should have 2 entries"
        assert len(modal.accounts) == 3, "Wallets should have 3 entries (excluding Alice)"
        print("   ✓ Both wallets and recents work together\n")

        print("✅ All filtering tests passed!\n")
        print("📊 Summary:")
        print("   1. ✓ Sending wallet is always excluded from destination list")
        print("   2. ✓ All other wallets are shown as options")
        print("   3. ✓ Works correctly with single wallet (shows nothing)")
        print("   4. ✓ Wallets and recent destinations work independently")
        print("   5. ✓ Prevents accidental self-transfers")
        print("\n💡 Benefits:")
        print("   • Impossible to accidentally send to yourself")
        print("   • Clear visual separation: your wallets vs external addresses")
        print("   • Easy transfers between your own wallets")
        print("   • No confusion about which addresses are available")

        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_wallet_filtering()
    sys.exit(0 if success else 1)
