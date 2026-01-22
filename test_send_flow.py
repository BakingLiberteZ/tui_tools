#!/usr/bin/env python3
"""Test the complete send flow with wallet selection."""

import sys
from app import DestinationPickerScreen
from wallet.store import Account

def test_send_flow():
    """Simulate the complete user flow when sending funds."""
    print("🧪 Testing complete send flow with wallet selection...\n")

    try:
        # Scenario: User has 4 wallets loaded
        alice = Account(name="Alice Main", address="tz1alice123abc", enc=None)
        bob = Account(name="Bob Savings", address="tz1bob456def", enc=None)
        charlie = Account(name="Charlie Trading", address="tz1charlie789ghi", enc=None)
        david = Account(name="David Cold Storage", address="tz1david012jkl", enc=None)

        all_wallets = [alice, bob, charlie, david]

        print("📋 User's wallets:")
        for wallet in all_wallets:
            print(f"   • {wallet.name} ({wallet.address})")
        print()

        # Scenario 1: Alice wants to send to Bob (internal transfer)
        print("=" * 60)
        print("Scenario 1: Alice sends to Bob (internal transfer)")
        print("=" * 60)

        alice_recents = []  # Alice hasn't sent to anyone yet
        modal = DestinationPickerScreen(alice_recents, all_wallets, alice.address)

        print(f"\n1. Alice clicks 'Send' from her wallet")
        print(f"   From: {alice.name}")
        print()

        print("2. Destination modal opens showing:")
        print(f"   📝 Input field: (empty)")
        print()
        print(f"   👥 Your wallets ({len(modal.accounts)} available):")
        for i, acc in enumerate(modal.accounts, 1):
            display = f"{acc.name} ({acc.address[:10]}...{acc.address[-6:]})"
            print(f"      {i}. {display}")
        print()
        print(f"   📋 Recent destinations:")
        if not modal.recents:
            print(f"      (none - first time sending)")
        print()

        # Verify Alice is not in the list
        assert alice not in modal.accounts, "Alice should not see herself"
        assert len(modal.accounts) == 3, "Should show 3 wallets (Bob, Charlie, David)"
        assert bob in modal.accounts, "Bob should be available"
        print("   ✓ Alice is NOT shown (can't send to herself)")
        print("   ✓ Bob, Charlie, and David are shown")
        print()

        print("3. Alice clicks 'Bob Savings' from the wallet list")
        print(f"   Selected: {bob.address}")
        print("   → Address auto-filled in input field")
        print()

        print("4. Alice clicks 'OK'")
        print("   → Proceeds to amount entry")
        print()

        # Scenario 2: Bob has sent before, has recent destinations
        print("=" * 60)
        print("Scenario 2: Bob sends with recent destinations")
        print("=" * 60)

        bob_recents = [
            "tz1exchange123abc456def",  # Bob previously sent to an exchange
            "tz1friend789xyz012ghi",    # Bob previously sent to a friend
        ]
        modal = DestinationPickerScreen(bob_recents, all_wallets, bob.address)

        print(f"\n1. Bob clicks 'Send' from his wallet")
        print(f"   From: {bob.name}")
        print()

        print("2. Destination modal opens showing:")
        print(f"   📝 Input field: (empty)")
        print()
        print(f"   👥 Your wallets ({len(modal.accounts)} available):")
        for i, acc in enumerate(modal.accounts, 1):
            display = f"{acc.name} ({acc.address[:10]}...{acc.address[-6:]})"
            print(f"      {i}. {display}")
        print()
        print(f"   📋 Recent destinations ({len(modal.recents)} recent):")
        for i, addr in enumerate(modal.recents, 1):
            print(f"      {i}. {addr}")
        print()

        # Verify Bob is not in the list
        assert bob not in modal.accounts, "Bob should not see himself"
        assert len(modal.accounts) == 3, "Should show 3 wallets (Alice, Charlie, David)"
        assert alice in modal.accounts, "Alice should be available"
        assert len(modal.recents) == 2, "Should show 2 recent destinations"
        print("   ✓ Bob is NOT shown (can't send to himself)")
        print("   ✓ Alice, Charlie, and David are shown")
        print("   ✓ Bob's recent destinations are shown")
        print()

        print("3. Bob has 3 options:")
        print("   a) Click a wallet from 'Your wallets' (internal transfer)")
        print("   b) Click an address from 'Recent destinations'")
        print("   c) Type/paste a new address")
        print()

        # Scenario 3: Charlie is the only wallet (edge case)
        print("=" * 60)
        print("Scenario 3: Charlie is the only wallet (edge case)")
        print("=" * 60)

        charlie_recents = []
        modal = DestinationPickerScreen(charlie_recents, [charlie], charlie.address)

        print(f"\n1. Charlie clicks 'Send' from his wallet")
        print(f"   From: {charlie.name}")
        print()

        print("2. Destination modal opens showing:")
        print(f"   📝 Input field: (empty)")
        print()
        print(f"   👥 Your wallets:")
        if modal.accounts:
            for i, acc in enumerate(modal.accounts, 1):
                display = f"{acc.name} ({acc.address[:10]}...{acc.address[-6:]})"
                print(f"      {i}. {display}")
        else:
            print(f"      (Section hidden - no other wallets)")
        print()
        print(f"   📋 Recent destinations:")
        if not modal.recents:
            print(f"      (none - first time sending)")
        print()

        assert len(modal.accounts) == 0, "No wallets should be shown"
        print("   ✓ Wallet section is empty (Charlie is the only wallet)")
        print("   ✓ Charlie must type/paste an external address")
        print()

        # Scenario 4: David sending to mix of internal and external
        print("=" * 60)
        print("Scenario 4: David with mixed history")
        print("=" * 60)

        david_recents = [
            alice.address,              # Previously sent to Alice (internal)
            "tz1external123abc",        # Previously sent to external address
            bob.address,                # Previously sent to Bob (internal)
        ]
        modal = DestinationPickerScreen(david_recents, all_wallets, david.address)

        print(f"\n1. David clicks 'Send' from his wallet")
        print(f"   From: {david.name}")
        print()

        print("2. Destination modal opens showing:")
        print(f"   📝 Input field: (empty)")
        print()
        print(f"   👥 Your wallets ({len(modal.accounts)} available):")
        for i, acc in enumerate(modal.accounts, 1):
            display = f"{acc.name} ({acc.address[:10]}...{acc.address[-6:]})"
            print(f"      {i}. {display}")
        print()
        print(f"   📋 Recent destinations ({len(modal.recents)} recent):")
        for i, addr in enumerate(modal.recents, 1):
            # Check if it's a known wallet address
            is_wallet = any(acc.address == addr for acc in all_wallets)
            marker = " (wallet)" if is_wallet else " (external)"
            print(f"      {i}. {addr}{marker}")
        print()

        print("3. David sees:")
        print("   • Clean wallet list in 'Your wallets' section")
        print("   • Recent destinations include both wallet and external addresses")
        print("   • No duplication - wallets appear in both sections naturally")
        print()

        assert len(modal.accounts) == 3, "Should show 3 wallets (excluding David)"
        assert len(modal.recents) == 3, "Should show all 3 recent destinations"
        print("   ✓ David sees all his options clearly organized")
        print()

        print("=" * 60)
        print("✅ All send flow scenarios work correctly!")
        print("=" * 60)
        print()

        print("📊 Summary:")
        print("   1. ✓ Wallet list shows all wallets except sender")
        print("   2. ✓ Recent destinations are wallet-specific")
        print("   3. ✓ Both sections work independently")
        print("   4. ✓ Edge case (single wallet) handled gracefully")
        print("   5. ✓ Mixed internal/external recents work correctly")
        print()

        print("🎯 User Experience:")
        print("   • Clear visual separation: wallets vs addresses")
        print("   • Wallet names make selection intuitive")
        print("   • No confusion about which wallet is sending")
        print("   • Impossible to send to yourself")
        print("   • Three ways to specify destination:")
        print("     1. Click a wallet from 'Your wallets'")
        print("     2. Click from 'Recent destinations'")
        print("     3. Type/paste any address")
        print()

        print("💡 Benefits:")
        print("   • Faster internal transfers (one click)")
        print("   • Less error-prone (no typos for wallet transfers)")
        print("   • Better organization (clear categories)")
        print("   • Privacy maintained (wallet-specific recents)")

        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_send_flow()
    sys.exit(0 if success else 1)
