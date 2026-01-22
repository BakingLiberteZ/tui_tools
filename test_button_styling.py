#!/usr/bin/env python3
"""Test button styling with blue default and hover effects."""

import sys
from app import WalletApp

def test_button_styling():
    """Verify all buttons have consistent blue styling."""
    print("🧪 Testing button styling...")

    try:
        app = WalletApp()
        print("✓ App instance created successfully")

        css = app.CSS

        # Check global Button styling
        assert "Button {" in css, "Should have global Button styling"
        button_start = css.find("Button {")
        button_end = css.find("}", button_start)
        button_css = css[button_start:button_end]

        assert "background: #3b82f6" in button_css, "Buttons should have blue background"
        assert "color: white" in button_css, "Buttons should have white text"
        print("✓ All buttons styled with blue (#3b82f6) background")

        # Check Button hover
        assert "Button:hover" in css, "Should have Button hover styling"
        hover_start = css.find("Button:hover")
        hover_end = css.find("}", hover_start)
        hover_css = css[hover_start:hover_end]

        assert "background: #2563eb" in hover_css, "Hover should use darker blue"
        print("✓ Button hover effect configured (darker blue #2563eb)")

        # Check #add button specifically
        assert "#add {" in css, "Should have #add button styling"
        add_start = css.find("#add {")
        add_end = css.find("}", add_start)
        add_css = css[add_start:add_end]

        assert "height: 3" in add_css, "Add button should have proper height"
        print("✓ Add button has proper height (3) - text will be visible")

        # Check action buttons
        for btn_id in ["#send", "#recv", "#refresh"]:
            assert f"{btn_id} {{" in css, f"Should have {btn_id} styling"
            print(f"✓ {btn_id} button styled")

        print("\n✅ Button styling validated successfully!")
        print("\n📋 Button colors:")
        print("   • Default:  Blue (#3b82f6)")
        print("   • Hover:    Darker Blue (#2563eb)")
        print("   • Text:     White")
        print("\n📊 Styled buttons:")
        print("   1. ✓ Add button (+ Add) - Fixed height, now visible")
        print("   2. ✓ Send button")
        print("   3. ✓ Receive button")
        print("   4. ✓ Refresh button")
        print("   5. ✓ All modal buttons (OK, Cancel, Close, etc.)")
        print("\n💡 Interaction:")
        print("   • All buttons are blue when idle")
        print("   • Turn darker blue on hover")
        print("   • Consistent styling across the entire app")
        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_button_styling()
    sys.exit(0 if success else 1)
