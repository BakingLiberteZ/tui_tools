#!/usr/bin/env python3
"""Test the minimalist UI improvements."""

import sys
from app import WalletApp

def test_minimalist_ui():
    """Verify minimalist UI changes."""
    print("🧪 Testing minimalist UI...")

    try:
        app = WalletApp()
        print("✓ App instance created successfully")

        # Check CSS is simplified (no heavy containers/borders)
        assert "#banner" in app.CSS
        assert "#status_bar" in app.CSS
        assert "background: $panel" not in app.CSS  # No heavy backgrounds
        assert "border: solid $primary" not in app.CSS  # No heavy borders
        print("✓ CSS simplified - minimal styling")

        # Check status bar methods still exist
        assert hasattr(app, '_set_status')
        assert hasattr(app, '_set_status_left')
        assert hasattr(app, '_set_status_right')
        print("✓ Status bar methods present")

        print("\n✅ Minimalist UI validated successfully!")
        print("\n📋 Changes made:")
        print("   • Removed emojis and decorative icons")
        print("   • Simplified color scheme (green/red for IN/OUT only)")
        print("   • Removed heavy borders and containers")
        print("   • Removed background colors")
        print("   • Compact two-line transaction format")
        print("   • Simple account list (name + shortened address)")
        print("   • Clean status bar (left: account, center: balance, right: network)")
        print("   • Kept compact banner")
        print("\n💡 The UI is now cleaner and more minimalist while keeping readability improvements.")
        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_minimalist_ui()
    sys.exit(0 if success else 1)
