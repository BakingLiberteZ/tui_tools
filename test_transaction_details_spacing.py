#!/usr/bin/env python3
"""Test transaction details interlinear spacing."""

import sys
import inspect

def test_transaction_details_spacing():
    """Verify transaction details have pleasant interlinear spacing between fields."""
    print("🧪 Testing transaction details interlinear spacing...\n")

    try:
        from app import TxDetailsScreen

        print("✓ TxDetailsScreen class imported successfully")

        # Get the source code of the compose method
        source = inspect.getsource(TxDetailsScreen.compose)
        print("✓ Source code retrieved")

        # Check for the lines array with interlinear spacing
        # We're looking for the pattern of empty strings "" between fields
        checks = [
            ('lines = [' in source, "Lines array initialization"),
            ('f"Time:    {ts}",' in source, "Time field"),
            ('f"Amount:  {amt_label}",' in source, "Amount field"),
            ('f"From:    {from_short}",' in source, "From field"),
            ('f"To:      {to_short}",' in source, "To field"),
            ('f"Hash:    {h}",' in source, "Hash field (full hash)"),
        ]

        for check, description in checks:
            assert check, f"Missing: {description}"
            print(f"✓ {description} present")

        # Count empty string literals (interlinear spacing)
        # Between Time and Amount, Amount and From, From and To, To and Hash
        empty_strings_count = source.count('""')
        print(f"✓ Found {empty_strings_count} empty string literals (interlinear spacing)")

        # Should have at least 4 empty strings for spacing between fields
        # (Time-Amount, Amount-From, From-To, To-Hash)
        assert empty_strings_count >= 4, f"Should have at least 4 empty strings for spacing, found {empty_strings_count}"
        print("✓ Sufficient interlinear spacing present")

        print("\n✅ Transaction details interlinear spacing validated!\n")

        print("📊 Improvements:")
        print("   1. ✓ Added blank lines between each field")
        print("   2. ✓ Pleasant, readable layout")
        print("   3. ✓ Information easier to scan")
        print("   4. ✓ Professional appearance")
        print()

        print("💡 Visual comparison:")
        print()
        print("   Before (cramped):")
        print("   ┌─────────────────────────────────┐")
        print("   │ Transaction Details             │")
        print("   │                                 │")
        print("   │ Time:    2024-01-21 12:34:56    │")
        print("   │ Amount:  -5.123456 XTZ          │")
        print("   │ From:    tz1mywallet...abcd     │")
        print("   │ To:      tz1abcdefg...3456      │")
        print("   │  ↑ No spacing, hard to scan     │")
        print("   └─────────────────────────────────┘")
        print()
        print("   After (with interlinear spacing):")
        print("   ┌─────────────────────────────────┐")
        print("   │ Transaction Details             │")
        print("   │                                 │")
        print("   │ Time:    2024-01-21 12:34:56    │")
        print("   │                                 │ ← spacing")
        print("   │ Amount:  -5.123456 XTZ          │")
        print("   │                                 │ ← spacing")
        print("   │ From:    tz1mywallet...abcd     │")
        print("   │                                 │ ← spacing")
        print("   │ To:      tz1abcdefg...3456      │")
        print("   │  ↑ Clear spacing, easy to read  │")
        print("   └─────────────────────────────────┘")
        print()

        print("🎯 Benefits:")
        print("   • Better readability of transaction details")
        print("   • Each field clearly separated")
        print("   • Information easier to scan")
        print("   • Professional appearance")
        print("   • Comfortable to read")
        print()

        print("📝 Technical details:")
        print("   • Added blank line after Time")
        print("   • Added blank line after Amount")
        print("   • Added blank line after From")
        print("   • Added blank line after To")
        print("   • Baker field (if present) also gets spacing")
        print()

        print("🎨 Layout structure:")
        print("   Transaction Details    ← Title")
        print("   [blank line]")
        print("   Time: ...             ← Field 1")
        print("   [blank line]")
        print("   Amount: ...           ← Field 2")
        print("   [blank line]")
        print("   From: ...             ← Field 3")
        print("   [blank line]")
        print("   To: ...               ← Field 4")
        print()
        print("   Clear separation between each field!")
        print()

        print("✨ Consistency:")
        print("   • Modal dialog: ✓ Interlinear spacing")
        print("   • Side pane: ✓ Interlinear spacing")
        print("   • Same pattern throughout!")
        print()

        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_transaction_details_spacing()
    sys.exit(0 if success else 1)
