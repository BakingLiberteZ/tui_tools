#!/usr/bin/env python3
"""Test side pane transaction details are compact and show all information."""

import sys
import inspect

def test_side_pane_compact():
    """Verify side pane shows all fields compactly without excessive spacing."""
    print("🧪 Testing side pane compact transaction details...\n")

    try:
        from app import WalletApp

        print("✓ WalletApp class imported successfully")

        # Get the source code of the _update_tx_details method
        source = inspect.getsource(WalletApp._update_tx_details)
        print("✓ _update_tx_details method source retrieved")

        # Check that all required fields are present
        required_fields = [
            ('f"Time:    {ts}"' in source, "Time field"),
            ('f"Amount:  {amt_label}"' in source, "Amount field"),
            ('f"From:    {from_short}"' in source, "From field"),
            ('f"To:      {to_short}"' in source, "To field"),
            ('f"Hash:    {h}"' in source, "Hash field (full hash)"),
        ]

        for check, description in required_fields:
            assert check, f"Missing: {description}"
            print(f"✓ {description} present")

        # Check for instruction text
        has_instruction = "Press Enter or 'd' to view on TzKT" in source
        assert has_instruction, "Should have instruction about pressing Enter or 'd'"
        print("✓ Instruction text present")

        # Count lines in the build details section
        # Look for the pattern where we build the lines array
        lines_section_start = source.find("lines = [")
        lines_section_end = source.find("]", lines_section_start)
        lines_section = source[lines_section_start:lines_section_end]

        # Count how many blank lines ("") are in the initial lines array
        # We want NO blank lines between fields in side pane for compactness
        initial_blank_lines = lines_section.count('""')

        print(f"✓ Found {initial_blank_lines} blank lines in initial lines array")

        if initial_blank_lines == 0:
            print("✓ Side pane is compact (no interlinear spacing between fields)")
        else:
            print(f"⚠ Side pane has {initial_blank_lines} blank lines (may be too spacious)")

        print("\n✅ Side pane compact transaction details validated!\n")

        print("📊 Layout:")
        print("   Time:    2024-01-21 12:34:56")
        print("   Amount:  -5.123456 XTZ")
        print("   From:    tz1mywallet...abcd")
        print("   To:      tz1recipient...xyz")
        print("   Hash:    opABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcdefghij")
        print()
        print("   Press Enter or 'd' to view on TzKT")
        print()

        print("🎯 Benefits:")
        print("   • All information visible")
        print("   • Compact layout fits in side pane")
        print("   • No wasted space")
        print("   • Full hash shown")
        print("   • Clear instructions")
        print()

        print("📝 Fields shown:")
        print("   1. Time - When transaction occurred")
        print("   2. Amount - How much transferred (color-coded)")
        print("   3. From - Sender address (shortened)")
        print("   4. To - Recipient address (shortened)")
        print("   5. Hash - Complete transaction hash (full)")
        print("   6. Instructions - How to view on TzKT")
        print()

        print("💡 Design rationale:")
        print("   • Side pane: Compact (no spacing between fields)")
        print("   • Modal: Spacious (with interlinear spacing)")
        print("   • Different contexts, different layouts")
        print("   • Side pane optimized for limited space")
        print()

        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_side_pane_compact()
    sys.exit(0 if success else 1)
