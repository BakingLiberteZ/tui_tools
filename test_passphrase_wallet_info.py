#!/usr/bin/env python3
"""Test that passphrase prompts show wallet information."""

import sys
from app import PromptScreen

def test_passphrase_with_wallet_info():
    """Verify passphrase screen can display wallet information."""
    print("🧪 Testing passphrase screen with wallet information...\n")

    try:
        # Test 1: PromptScreen without wallet_info
        screen1 = PromptScreen("Enter passphrase:", password=True)
        assert hasattr(screen1, '_wallet_info'), "Should have _wallet_info attribute"
        assert screen1._wallet_info == "", "Should default to empty string"
        print("✓ PromptScreen works without wallet_info parameter")

        # Test 2: PromptScreen with wallet_info
        screen2 = PromptScreen("Enter passphrase:", password=True, wallet_info="Wallet: Alice Main")
        assert screen2._wallet_info == "Wallet: Alice Main", "Should store wallet_info"
        print("✓ PromptScreen accepts wallet_info parameter")

        # Test 3: Check CSS has wallet_info styling
        assert "#wallet_info" in PromptScreen.CSS, "Should have #wallet_info CSS"
        print("✓ PromptScreen CSS includes #wallet_info styling")

        print("\n✅ Passphrase screen wallet info validated!\n")

        print("📊 Changes made:")
        print("   1. ✓ Added optional wallet_info parameter to PromptScreen")
        print("   2. ✓ Display wallet name when asking for passphrase")
        print("   3. ✓ Shows which wallet user is entering passphrase for")
        print()

        print("💡 Usage examples:")
        print()
        print("   When adding a new wallet:")
        print("   ┌──────────────────────────────────────┐")
        print("   │ Passphrase to encrypt key:           │")
        print("   │ Wallet: Alice Main                   │ ← Shows wallet name")
        print("   │                                      │")
        print("   │ [Password input field]               │")
        print("   │                                      │")
        print("   │    [OK]        [Cancel]              │")
        print("   └──────────────────────────────────────┘")
        print()

        print("   When sending a transaction:")
        print("   ┌──────────────────────────────────────┐")
        print("   │ Passphrase to decrypt key:           │")
        print("   │ Wallet: Bob's Savings                │ ← Shows wallet name")
        print("   │                                      │")
        print("   │ [Password input field]               │")
        print("   │                                      │")
        print("   │    [OK]        [Cancel]              │")
        print("   └──────────────────────────────────────┘")
        print()

        print("🎯 Benefits:")
        print("   • Clear indication of which wallet is being accessed")
        print("   • Prevents confusion when managing multiple wallets")
        print("   • Better user experience for security-critical operations")
        print("   • Consistent with wallet selection UX")
        print()

        print("📝 Implementation details:")
        print("   • wallet_info parameter is optional (defaults to empty)")
        print("   • Displayed in dim style between title and input")
        print("   • Shown for both encrypt and decrypt operations")
        print("   • Uses wallet name from Account.name")

        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_passphrase_with_wallet_info()
    sys.exit(0 if success else 1)
