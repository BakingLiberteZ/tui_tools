#!/usr/bin/env python3
"""Test the full flow of wallet-specific recent destinations."""

import sys
from app import WalletApp

def test_wallet_specific_flow():
    """Simulate the full user flow with wallet-specific recents."""
    print("🧪 Testing wallet-specific recent destinations flow...\n")

    try:
        app = WalletApp()
        print("✓ App initialized\n")

        # Simulate scenario
        print("📋 Scenario:")
        print("   • Alice has wallet A (has sent to 3 addresses)")
        print("   • Bob has wallet B (has sent to 2 addresses)")
        print("   • Charlie has wallet C (brand new, no transactions)")
        print()

        # Setup test data
        wallet_a = "tz1AliceWalletABC123456789"
        wallet_b = "tz1BobWalletXYZ987654321"
        wallet_c = "tz1CharlieWalletNEW000000"

        # Alice's recent destinations
        alice_dests = ["tz1alice_friend1", "tz1alice_friend2", "tz1alice_exchange"]
        app.recent_to_by_wallet[wallet_a] = alice_dests

        # Bob's recent destinations
        bob_dests = ["tz1bob_friend", "tz1bob_shop"]
        app.recent_to_by_wallet[wallet_b] = bob_dests

        # Charlie has no transactions yet (wallet_c not in dict)

        print("✓ Test wallets setup complete\n")

        # Test 1: Alice's view
        print("Test 1: Alice selects her wallet")
        alice_recents = app._get_recent_to_for_wallet(wallet_a)
        print(f"   Alice sees recent destinations: {len(alice_recents)}")
        for i, dest in enumerate(alice_recents, 1):
            print(f"      {i}. {dest}")
        assert alice_recents == alice_dests, "Alice should see only her destinations"
        print("   ✓ Alice sees only HER recent destinations\n")

        # Test 2: Bob's view
        print("Test 2: Bob selects his wallet")
        bob_recents = app._get_recent_to_for_wallet(wallet_b)
        print(f"   Bob sees recent destinations: {len(bob_recents)}")
        for i, dest in enumerate(bob_recents, 1):
            print(f"      {i}. {dest}")
        assert bob_recents == bob_dests, "Bob should see only his destinations"
        assert "tz1alice_friend1" not in bob_recents, "Bob should NOT see Alice's destinations"
        print("   ✓ Bob sees only HIS recent destinations")
        print("   ✓ Bob does NOT see Alice's destinations\n")

        # Test 3: Charlie's view (new wallet)
        print("Test 3: Charlie selects his brand new wallet")
        charlie_recents = app._get_recent_to_for_wallet(wallet_c)
        print(f"   Charlie sees recent destinations: {len(charlie_recents)}")
        if charlie_recents:
            for i, dest in enumerate(charlie_recents, 1):
                print(f"      {i}. {dest}")
        else:
            print("      (empty list - no transactions yet)")
        assert len(charlie_recents) == 0, "Charlie's new wallet should have no recents"
        print("   ✓ Charlie's new wallet shows empty list\n")

        # Test 4: Add a new destination for Charlie
        print("Test 4: Charlie sends his first transaction")
        charlie_first_dest = "tz1charlie_first_tx"
        app._push_recent_to(wallet_c, charlie_first_dest)

        charlie_recents_after = app._get_recent_to_for_wallet(wallet_c)
        print(f"   Charlie now has {len(charlie_recents_after)} recent destination")
        print(f"      1. {charlie_recents_after[0]}")
        assert len(charlie_recents_after) == 1, "Charlie should have 1 recent"
        assert charlie_recents_after[0] == charlie_first_dest, "Should be the correct address"
        print("   ✓ Charlie's destination added successfully\n")

        # Test 5: Verify isolation still maintained
        print("Test 5: Verify all wallets still isolated")
        alice_check = app._get_recent_to_for_wallet(wallet_a)
        bob_check = app._get_recent_to_for_wallet(wallet_b)
        charlie_check = app._get_recent_to_for_wallet(wallet_c)

        assert charlie_first_dest not in alice_check, "Alice shouldn't see Charlie's tx"
        assert charlie_first_dest not in bob_check, "Bob shouldn't see Charlie's tx"
        assert len(alice_check) == 3, "Alice still has 3 recents"
        assert len(bob_check) == 2, "Bob still has 2 recents"
        assert len(charlie_check) == 1, "Charlie has 1 recent"
        print(f"   Alice:   {len(alice_check)} destinations (unchanged)")
        print(f"   Bob:     {len(bob_check)} destinations (unchanged)")
        print(f"   Charlie: {len(charlie_check)} destination (new)")
        print("   ✓ All wallets remain completely isolated\n")

        print("✅ All flow tests passed!\n")
        print("🎯 Key improvements:")
        print("   1. ✓ Each wallet has its own recent destinations")
        print("   2. ✓ New wallets start with empty list (not confusing)")
        print("   3. ✓ Privacy maintained between wallets")
        print("   4. ✓ Better user experience - only relevant addresses shown")
        print("   5. ✓ No cross-contamination between wallet histories")

        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_wallet_specific_flow()
    sys.exit(0 if success else 1)
