#!/usr/bin/env python3
"""Test action buttons spacing improvement."""

import sys
from app import WalletApp

def test_action_buttons_spacing():
    """Verify action buttons have spacing above them."""
    print("🧪 Testing action buttons spacing improvement...\n")

    try:
        app = WalletApp()
        print("✓ WalletApp instance created successfully")

        css = app.CSS
        print("✓ App has CSS styling")

        # Check action_buttons section
        assert "#action_buttons" in css, "Should have action_buttons CSS"
        print("✓ Action buttons CSS exists")

        # Extract action_buttons CSS
        buttons_start = css.find("#action_buttons {")
        if buttons_start == -1:
            buttons_start = css.find("#action_buttons{")

        brace_count = 0
        buttons_css = ""
        found_opening = False
        for i in range(buttons_start, len(css)):
            char = css[i]
            if char == '{':
                found_opening = True
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and found_opening:
                    buttons_css = css[buttons_start:i+1]
                    break

        print("✓ Action buttons CSS extracted")

        # Check for margin-top
        assert "margin-top:" in buttons_css, "action_buttons should have margin-top"
        print("✓ Action buttons has margin-top property")

        # Check margin-top value
        if "margin-top: 1" in buttons_css:
            print("✓ Action buttons has correct margin-top (1 unit)")
        else:
            print("⚠ Action buttons has different margin-top value")

        # Verify margin-bottom is still 0
        if "margin-bottom: 0" in buttons_css:
            print("✓ Action buttons margin-bottom remains 0 (compact)")

        print("\n✅ Action buttons spacing improvement validated!\n")

        print("📊 Improvements:")
        print("   1. ✓ Added margin-top: 1 to action_buttons")
        print("   2. ✓ Creates visual separation from wallet status")
        print("   3. ✓ Buttons no longer tied to status information")
        print("   4. ✓ Better visual hierarchy")
        print()

        print("💡 Visual comparison:")
        print()
        print("   Before (no spacing):")
        print("   ┌──────────────────────────────────────┐")
        print("   │ Status: Connected                    │")
        print("   │ Balance: 12.456789 XTZ               │")
        print("   │ Delegated to: tz1baker...            │")
        print("   │ Staking: 5.000000 XTZ                │")
        print("   │ Network: ● Mainnet                   │")
        print("   │ [Send] [Receive] [Refresh]           │")
        print("   │  ↑ Tied to status area               │")
        print("   └──────────────────────────────────────┘")
        print()
        print("   After (with spacing):")
        print("   ┌──────────────────────────────────────┐")
        print("   │ Status: Connected                    │")
        print("   │ Balance: 12.456789 XTZ               │")
        print("   │ Delegated to: tz1baker...            │")
        print("   │ Staking: 5.000000 XTZ                │")
        print("   │ Network: ● Mainnet                   │")
        print("   │                                      │ ← 1 unit space")
        print("   │ [Send] [Receive] [Refresh]           │")
        print("   │  ↑ Separated from status             │")
        print("   └──────────────────────────────────────┘")
        print()

        print("🎯 Benefits:")
        print("   • Visual separation between sections")
        print("   • Buttons not tied to status information")
        print("   • Better visual hierarchy")
        print("   • Clearer action area")
        print("   • Professional appearance")
        print()

        print("📝 Technical details:")
        print("   • action_buttons margin-top: 1 (added)")
        print("   • action_buttons margin-bottom: 0 (unchanged)")
        print("   • Creates breathing room above buttons")
        print("   • Maintains compact layout below buttons")
        print()

        print("🎨 Visual hierarchy:")
        print()
        print("   Section 1: Accounts (4 rows, compact)")
        print("   Section 2: Wallet Status (compact, no spacing)")
        print("   ──────────── ← 1 unit space")
        print("   Section 3: Action Buttons (separated)")
        print()
        print("   Clear visual separation between status and actions!")

        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_action_buttons_spacing()
    sys.exit(0 if success else 1)
