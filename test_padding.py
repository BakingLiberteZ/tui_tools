#!/usr/bin/env python3
"""Test the padding between Recent Transactions and footer."""

import sys
from app import WalletApp

def test_padding():
    """Verify padding is added between transactions and footer."""
    print("🧪 Testing padding between Recent Transactions and footer...")

    try:
        app = WalletApp()
        print("✓ App instance created successfully")

        # Check CSS has margin-top on bottom_bar
        css = app.CSS
        assert "#bottom_bar" in css, "Should have bottom_bar"

        # Extract the bottom_bar CSS block
        bottom_bar_start = css.find("#bottom_bar")
        bottom_bar_end = css.find("}", bottom_bar_start)
        bottom_bar_css = css[bottom_bar_start:bottom_bar_end]

        assert "margin-top:" in bottom_bar_css, "bottom_bar should have margin-top"
        print("✓ Margin-top added to bottom_bar")

        # Check history_split has proper height
        assert "#history_split" in css, "Should have history_split"
        history_split_start = css.find("#history_split")
        history_split_end = css.find("}", history_split_start)
        history_split_css = css[history_split_start:history_split_end]

        assert "height: 1fr" in history_split_css, "history_split should use flexible height"
        print("✓ History split uses flexible height (1fr)")

        print("\n✅ Padding configuration validated successfully!")
        print("\n📊 Changes:")
        print("   • Added margin-top: 1 to #bottom_bar")
        print("   • This creates space between transactions and RPC indicator")
        print("   • History split uses flexible height for better space usage")
        print("\n💡 Visual result:")
        print("   ┌─────────────────────────────────┐")
        print("   │ Recent Transactions             │")
        print("   │ ┌─────────┬────────────────────┐│")
        print("   │ │ TX List │ Details Pane       ││")
        print("   │ │         │                    ││")
        print("   │ └─────────┴────────────────────┘│")
        print("   │                                 │  ← Space added here!")
        print("   │              ● RPC indicator    │")
        print("   ├─────────────────────────────────┤")
        print("   │ Footer palette                  │")
        print("   └─────────────────────────────────┘")
        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_padding()
    sys.exit(0 if success else 1)
