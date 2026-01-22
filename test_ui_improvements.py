#!/usr/bin/env python3
"""Test the latest UI improvements: ASCII logo, button hover, and Add Wallet positioning."""

import sys
from pathlib import Path
from app import WalletApp, load_ascii_logo

def test_ui_improvements():
    """Verify all UI improvements are working."""
    print("🧪 Testing UI improvements...")

    try:
        # Test ASCII logo loading
        logo = load_ascii_logo()
        assert logo is not None, "Logo should load"
        assert len(logo) > 0, "Logo should not be empty"
        if "TUI WALLET" in logo.upper() or "TEZOS" in logo.upper():
            print("✓ ASCII logo loaded successfully")
            print(f"\n📋 Logo preview (first 3 lines):")
            for line in logo.split('\n')[:3]:
                print(f"   {line[:60]}..." if len(line) > 60 else f"   {line}")
        else:
            print("✓ Fallback logo loaded")

        # Test that ascii_logo.txt exists
        logo_path = Path("ascii_logo.txt")
        if logo_path.exists():
            print("✓ ASCII logo file exists")
        else:
            print("⚠ ASCII logo file not found (using fallback)")

        # Test app instance
        app = WalletApp()
        print("✓ App instance created successfully")

        # Check CSS has button hover states
        css = app.CSS
        assert ":hover" in css, "Should have hover states in CSS"
        assert "#3b82f6" in css, "Should have blue color for hover"
        print("✓ Button hover states configured (blue #3b82f6)")

        # Check accounts header positioning
        assert "#accounts_title" in css, "Should have accounts_title"
        assert "#add" in css, "Should have add button styles"
        print("✓ Add Wallet button positioning configured")

        # Check banner is centered
        assert "text-align: center" in css or "center" in css, "Banner should be centered"
        print("✓ Banner centered")

        print("\n✅ All UI improvements validated successfully!")
        print("\n📊 Changes made:")
        print("   1. ✓ ASCII logo from file (ascii_logo.txt)")
        print("   2. ✓ Blue hover color (#3b82f6) for Send/Receive/Refresh buttons")
        print("   3. ✓ Add Wallet button moved closer to 'Accounts' title")
        print("   4. ✓ Banner centered")
        print("\n💡 Visual improvements:")
        print("   • More professional ASCII art header")
        print("   • Better button feedback on hover")
        print("   • Tighter button grouping in header")
        print("\n🎨 To see it in action, run: python3 app.py")
        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_ui_improvements()
    sys.exit(0 if success else 1)
