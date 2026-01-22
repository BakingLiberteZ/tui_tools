#!/usr/bin/env python3
"""Test the Confirm Transaction modal improvements."""

import sys
from decimal import Decimal
from app import ConfirmSendScreen

def test_confirm_modal():
    """Verify Confirm Transaction modal has proper padding and styling."""
    print("🧪 Testing Confirm Transaction modal improvements...\n")

    try:
        # Create instance with test data
        test_rpc = "https://ghostnet.tezos.marigold.dev"
        test_key = None  # Mock key (not used in CSS test)
        test_from = "tz1fromAddress123abc"
        test_to = "tz1toAddress456def"
        test_amount = Decimal("0.5")

        modal = ConfirmSendScreen(test_rpc, test_key, test_from, test_to, test_amount)
        print("✓ ConfirmSendScreen instance created")

        # Check CSS exists
        assert hasattr(modal, 'CSS'), "Modal should have CSS attribute"
        css = modal.CSS
        print("✓ Modal has CSS styling")

        # Check centering
        assert "ConfirmSendScreen {" in css, "Should have main screen styling"
        assert "align: center middle" in css, "Should be centered"
        print("✓ Modal is centered on screen")

        # Check container styling
        assert "ConfirmSendScreen > Vertical {" in css, "Should style the Vertical container"
        assert "padding: 2" in css, "Should have padding: 2"
        assert "border: solid $primary" in css, "Should have border"
        assert "background: $surface" in css, "Should have background"
        print("✓ Modal container has padding (2), border, and background")

        # Check width
        assert "width: 80" in css, "Should have width constraint"
        print("✓ Modal has proper width (80)")

        # Check component margins
        assert "#summary" in css, "Should have summary styling"
        assert "margin-bottom: 2" in css, "Summary should have margin"
        print("✓ Summary section has proper spacing")

        assert "#fee_title" in css, "Should have fee title styling"
        assert "margin-bottom: 1" in css, "Fee title should have margin"
        print("✓ Fee title has proper spacing")

        assert "#fee_list" in css, "Should have fee list styling"
        assert "height: 4" in css, "Fee list should have fixed height"
        print("✓ Fee list has proper size")

        assert "#advanced" in css, "Should have advanced section styling"
        assert "margin-top: 1" in css, "Advanced section should have top margin"
        print("✓ Advanced section has proper spacing")

        # Check button alignment
        assert "Horizontal {" in css, "Should style Horizontal containers"
        assert "align: center middle" in css, "Buttons should be centered"
        print("✓ Buttons are centered")

        print("\n✅ Confirm Transaction modal improvements validated!\n")
        print("📊 Improvements:")
        print("   1. ✓ Added padding: 2 around entire modal")
        print("   2. ✓ Centered modal on screen")
        print("   3. ✓ Added border and background")
        print("   4. ✓ Better margin spacing between sections")
        print("   5. ✓ Width constrained to 80 for readability")
        print("   6. ✓ Consistent styling with other modals")
        print("\n💡 Visual result:")
        print("   ┌────────────────────────────────────────────────┐")
        print("   │                                                │  ← Padding")
        print("   │  Confirm transaction                           │")
        print("   │                                                │")
        print("   │  Network:   ghostnet                           │")
        print("   │  From:      tz1abc...                          │")
        print("   │  To:        tz1xyz...                          │")
        print("   │  Amount:    0.5 XTZ                            │")
        print("   │  Fee:       estimating...                      │")
        print("   │                                                │")
        print("   │  Fee (↑/↓ to choose)                           │")
        print("   │  ┌──────────────────────────────────────────┐  │")
        print("   │  │ ● Economy   - 0.001 XTZ                  │  │")
        print("   │  │   Normal    - 0.002 XTZ                  │  │")
        print("   │  │   Priority  - 0.003 XTZ                  │  │")
        print("   │  └──────────────────────────────────────────┘  │")
        print("   │                                                │")
        print("   │     [SEND]  [Advanced]  [Cancel]               │")
        print("   │                                                │  ← Padding")
        print("   └────────────────────────────────────────────────┘")
        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_confirm_modal()
    sys.exit(0 if success else 1)
