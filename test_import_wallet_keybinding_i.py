#!/usr/bin/env python3
"""Test import wallet keybinding changed to 'i'."""

import sys
from app import WalletApp

def test_import_wallet_keybinding_i():
    """Verify import wallet keybinding is 'i' not 'a'."""
    print("🧪 Testing import wallet keybinding changed to 'i'...\n")

    try:
        app = WalletApp()
        print("✓ WalletApp instance created successfully")

        # Check BINDINGS
        bindings = app.BINDINGS
        print(f"✓ Found {len(bindings)} bindings")

        # Find import_wallet binding
        import_binding = None
        for binding in bindings:
            if binding.action == "import_wallet":
                import_binding = binding
                break

        assert import_binding is not None, "Should have import_wallet binding"
        print("✓ import_wallet binding found")

        # Check that it's 'i' not 'a'
        assert import_binding.key == "i", f"Keybinding should be 'i', got '{import_binding.key}'"
        print("✓ import_wallet keybinding is 'i' (not 'a')")

        # Check description
        assert import_binding.description == "Import Wallet", f"Description should be 'Import Wallet', got '{import_binding.description}'"
        print("✓ import_wallet description is 'Import Wallet'")

        # Check it's shown in footer
        assert import_binding.show is True, "Should be shown in footer"
        print("✓ import_wallet is shown in footer")

        print("\n✅ Import wallet keybinding validated!\n")

        print("📊 Changes:")
        print("   • Keybinding: 'a' → 'i'")
        print("   • Description: 'Import Wallet' ✓")
        print("   • Action: 'import_wallet' ✓")
        print("   • Show in footer: Yes ✓")
        print()

        print("💡 Rationale:")
        print("   • 'i' = Import (more intuitive)")
        print("   • 'a' = Add (less specific)")
        print("   • Follows common conventions")
        print("   • Easier to remember")
        print()

        print("🎯 Footer display:")
        print("   i: Import Wallet  r: Refresh  s: Send XTZ  x: Receive  q: Quit")
        print()

        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_import_wallet_keybinding_i()
    sys.exit(0 if success else 1)
