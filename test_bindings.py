#!/usr/bin/env python3
"""Test the cleaned up keybindings."""

import sys
from app import WalletApp

def test_bindings():
    """Verify keybindings are properly configured."""
    print("🧪 Testing keybindings...")

    try:
        app = WalletApp()
        print("✓ App instance created successfully")

        # Count visible vs hidden bindings
        visible_bindings = [b for b in app.BINDINGS if b.show]
        hidden_bindings = [b for b in app.BINDINGS if not b.show]

        print(f"\n📋 Visible bindings in footer ({len(visible_bindings)}):")
        for b in visible_bindings:
            print(f"   {b.key:8} → {b.description}")

        print(f"\n🔒 Hidden bindings (still work, not in footer) ({len(hidden_bindings)}):")
        for b in hidden_bindings:
            print(f"   {b.key:8} → {b.description}")

        # Verify specific bindings
        assert any(b.key == "a" and b.show for b in app.BINDINGS), "Add account should be visible"
        assert any(b.key == "s" and b.show for b in app.BINDINGS), "Send should be visible"
        assert any(b.key == "x" and b.show for b in app.BINDINGS), "Receive should be visible"
        assert any(b.key == "r" and b.show for b in app.BINDINGS), "Refresh should be visible"
        assert any(b.key == "n" and b.show for b in app.BINDINGS), "Network should be visible"
        assert any(b.key == "q" and b.show for b in app.BINDINGS), "Quit should be visible"
        print("\n✓ All essential bindings are visible")

        # Verify hidden bindings still exist
        assert any(b.key == "d" and not b.show for b in app.BINDINGS), "Tx details should be hidden"
        assert any(b.key == "m" and not b.show for b in app.BINDINGS), "More history should be hidden"
        assert any(b.key == "enter" and not b.show for b in app.BINDINGS), "Enter (tx details) should be hidden"
        assert any(b.key == "up" and not b.show for b in app.BINDINGS), "Up arrow should be hidden"
        assert any(b.key == "down" and not b.show for b in app.BINDINGS), "Down arrow should be hidden"
        print("✓ Non-essential bindings are hidden from footer")

        print("\n✅ Keybindings configured correctly!")
        print("\n💡 Footer will show only: a, r, s, x, n, q")
        print("   But d, enter, m, up, down still work!")
        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_bindings()
    sys.exit(0 if success else 1)
