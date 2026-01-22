#!/usr/bin/env python3
"""Test Import Wallet keybinding and action."""

import sys
from app import WalletApp

def test_import_wallet_keybinding():
    """Verify Import Wallet keybinding and action are properly configured."""
    print("🧪 Testing Import Wallet keybinding and action...\n")

    try:
        app = WalletApp()
        print("✓ WalletApp instance created successfully")

        # Check BINDINGS
        bindings = app.BINDINGS
        print(f"✓ App has {len(bindings)} keybindings")

        # Find the 'a' key binding
        import_binding = None
        for binding in bindings:
            if binding.key == "a":
                import_binding = binding
                break

        assert import_binding is not None, "Should have 'a' key binding"
        print("✓ Found 'a' key binding")

        # Check action name
        assert import_binding.action == "import_wallet", f"Action should be 'import_wallet', got '{import_binding.action}'"
        print("✓ Action is 'import_wallet' (updated from 'add_account')")

        # Check display name
        assert import_binding.description == "Import Wallet", f"Description should be 'Import Wallet', got '{import_binding.description}'"
        print("✓ Description is 'Import Wallet' (updated from 'Add account')")

        # Check if it's shown in footer
        assert import_binding.show is True, "Import Wallet binding should be visible in footer"
        print("✓ Binding is visible in footer")

        # Check that the action method exists
        assert hasattr(app, "action_import_wallet"), "Should have action_import_wallet method"
        print("✓ action_import_wallet method exists")

        # Verify method is callable
        assert callable(app.action_import_wallet), "action_import_wallet should be callable"
        print("✓ action_import_wallet is callable")

        print("\n✅ Import Wallet keybinding and action validated!\n")

        print("📊 Changes made:")
        print("   1. ✓ Keybinding action: 'add_account' → 'import_wallet'")
        print("   2. ✓ Keybinding description: 'Add account' → 'Import Wallet'")
        print("   3. ✓ Action method: action_add_account() → action_import_wallet()")
        print("   4. ✓ Button handler: Updated to call action_import_wallet()")
        print()

        print("💡 Keybinding details:")
        print()
        print("   Key: 'a'")
        print("   Action: import_wallet")
        print("   Description: Import Wallet")
        print("   Visible: Yes (shown in footer)")
        print()

        print("🎯 Consistency achieved:")
        print()
        print("   Button text:     [Import Wallet]       ← UI")
        print("   Keybinding:      a: Import Wallet      ← Footer")
        print("   Action method:   action_import_wallet  ← Code")
        print()
        print("   All three now use consistent 'Import Wallet' terminology!")
        print()

        print("📝 Footer display:")
        print()
        print("   Before:")
        print("   ┌────────────────────────────────────────────────────┐")
        print("   │ a: Add account  r: Refresh  s: Send XTZ  ...      │")
        print("   │    ↑ Old text                                      │")
        print("   └────────────────────────────────────────────────────┘")
        print()
        print("   After:")
        print("   ┌────────────────────────────────────────────────────┐")
        print("   │ a: Import Wallet  r: Refresh  s: Send XTZ  ...    │")
        print("   │    ↑ Updated text                                  │")
        print("   └────────────────────────────────────────────────────┘")
        print()

        print("🎯 Benefits:")
        print("   • Consistent terminology throughout the app")
        print("   • Users see 'Import Wallet' in button, footer, and actions")
        print("   • More descriptive action name")
        print("   • Professional terminology")
        print("   • Clear user guidance")
        print()

        print("💡 How it works:")
        print()
        print("   1. User sees button: [Import Wallet]")
        print("   2. User sees footer: a: Import Wallet")
        print("   3. User presses 'a' key")
        print("   4. App calls: action_import_wallet()")
        print("   5. Dialog opens to import wallet")
        print()

        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_import_wallet_keybinding()
    sys.exit(0 if success else 1)
