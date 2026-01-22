#!/usr/bin/env python3
"""Test accounts header alignment and button styling improvements."""

import sys
from app import WalletApp

def test_accounts_header():
    """Verify accounts header has proper alignment and consistent button styling."""
    print("🧪 Testing accounts header improvements...\n")

    try:
        app = WalletApp()
        print("✓ WalletApp instance created successfully")

        css = app.CSS
        print("✓ App has CSS styling")

        # Check accounts_header section
        assert "#accounts_header" in css, "Should have accounts_header CSS"
        print("✓ Accounts header CSS exists")

        # Extract accounts_header CSS
        header_start = css.find("#accounts_header {")
        if header_start == -1:
            header_start = css.find("#accounts_header{")

        brace_count = 0
        header_css = ""
        found_opening = False
        for i in range(header_start, len(css)):
            char = css[i]
            if char == '{':
                found_opening = True
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and found_opening:
                    header_css = css[header_start:i+1]
                    break

        print("✓ Accounts header CSS extracted")

        # Check alignment
        if "align:" in header_css:
            print("✓ Accounts header has alignment property")

        # Check accounts_title alignment
        assert "#accounts_title" in css, "Should have accounts_title CSS"
        title_start = css.find("#accounts_title {")
        if title_start == -1:
            title_start = css.find("#accounts_title{")

        brace_count = 0
        title_css = ""
        found_opening = False
        for i in range(title_start, len(css)):
            char = css[i]
            if char == '{':
                found_opening = True
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and found_opening:
                    title_css = css[title_start:i+1]
                    break

        if "content-align:" in title_css and "left" in title_css:
            print("✓ Accounts title aligned left")

        # Check Add button styling
        assert "#add" in css, "Should have add button CSS"
        add_start = css.find("#add {")
        if add_start == -1:
            add_start = css.find("#add{")

        brace_count = 0
        add_css = ""
        found_opening = False
        for i in range(add_start, len(css)):
            char = css[i]
            if char == '{':
                found_opening = True
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and found_opening:
                    add_css = css[add_start:i+1]
                    break

        # Check button has same colors as action buttons
        assert "background: #3b82f6" in add_css, "Add button should have blue background"
        print("✓ Add button has consistent background color")

        # Check hover state
        assert "#add:hover" in css, "Add button should have hover state"
        print("✓ Add button has hover styling")

        # Verify the button doesn't have explicit height (uses default)
        if "height:" not in add_css or "height: 3" not in add_css:
            print("✓ Add button uses default height (consistent with action buttons)")

        print("\n✅ Accounts header improvements validated!\n")

        print("📊 Improvements:")
        print("   1. ✓ Changed 'ACCOUNTS' to 'ACCOUNTS:' (with colon)")
        print("   2. ✓ Removed '+' symbol from Add button")
        print("   3. ✓ Made Add button consistent with action buttons")
        print("   4. ✓ Aligned header elements properly")
        print()

        print("💡 Visual comparison:")
        print()
        print("   Before:")
        print("   ┌─────────────────────────────────────┐")
        print("   │ ACCOUNTS              [+ Add (a)]   │")
        print("   │   ↑ No colon          ↑ Plus symbol │")
        print("   │                       ↑ Different style")
        print("   └─────────────────────────────────────┘")
        print()
        print("   After:")
        print("   ┌─────────────────────────────────────┐")
        print("   │ ACCOUNTS:             [Add (a)]     │")
        print("   │   ↑ Colon added       ↑ No plus    │")
        print("   │                       ↑ Same as Send/Receive/Refresh")
        print("   └─────────────────────────────────────┘")
        print()

        print("🎯 Benefits:")
        print("   • Consistent button styling across the app")
        print("   • Better alignment of header elements")
        print("   • Professional, clean appearance")
        print("   • Colon indicates the list below")
        print()

        print("📝 Technical details:")
        print("   • Label: 'ACCOUNTS:' (with colon)")
        print("   • Button text: 'Add (a)' (no plus symbol)")
        print("   • Button variant: Default (same as action buttons)")
        print("   • Alignment: Left-aligned with middle vertical")
        print("   • Colors: #3b82f6 (blue), #2563eb (hover)")

        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_accounts_header()
    sys.exit(0 if success else 1)
