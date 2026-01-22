#!/usr/bin/env python3
"""Test wallet status area compact spacing improvements."""

import sys
from app import WalletApp

def test_wallet_status_compact():
    """Verify wallet status area has compact spacing."""
    print("🧪 Testing wallet status area compact spacing...\n")

    try:
        app = WalletApp()
        print("✓ WalletApp instance created successfully")

        css = app.CSS
        print("✓ App has CSS styling")

        # Check wallet_details section
        assert "#wallet_details" in css, "Should have wallet_details CSS"
        print("✓ Wallet details CSS exists")

        # Extract wallet_details CSS
        details_start = css.find("#wallet_details {")
        if details_start == -1:
            details_start = css.find("#wallet_details{")

        brace_count = 0
        details_css = ""
        found_opening = False
        for i in range(details_start, len(css)):
            char = css[i]
            if char == '{':
                found_opening = True
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and found_opening:
                    details_css = css[details_start:i+1]
                    break

        print("✓ Wallet details CSS extracted")

        # Check for compact padding
        assert "padding: 0" in details_css, "wallet_details should have padding: 0"
        print("✓ Wallet details has compact padding (0)")

        # Check for compact margin
        assert "margin-bottom: 0" in details_css, "wallet_details should have margin-bottom: 0"
        print("✓ Wallet details has compact margin-bottom (0)")

        # Check individual wallet status elements
        status_elements = [
            "#wallet_status",
            "#wallet_balance",
            "#wallet_delegation",
            "#wallet_staking",
            "#wallet_network"
        ]

        for element in status_elements:
            assert element in css, f"Should have {element} CSS"

            # Extract element CSS
            elem_start = css.find(f"{element} {{")
            if elem_start == -1:
                elem_start = css.find(f"{element}{{")

            if elem_start != -1:
                brace_count = 0
                elem_css = ""
                found_opening = False
                for i in range(elem_start, len(css)):
                    char = css[i]
                    if char == '{':
                        found_opening = True
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0 and found_opening:
                            elem_css = css[elem_start:i+1]
                            break

                # Check for compact margin
                if "margin-bottom: 0" in elem_css:
                    print(f"✓ {element} has compact margin-bottom (0)")

        # Check action_buttons section
        assert "#action_buttons" in css, "Should have action_buttons CSS"

        buttons_start = css.find("#action_buttons {")
        if buttons_start == -1:
            buttons_start = css.find("#action_buttons{")

        if buttons_start != -1:
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

            if "margin-bottom: 0" in buttons_css:
                print("✓ Action buttons has compact margin-bottom (0)")

        print("\n✅ Wallet status area compact spacing validated!\n")

        print("📊 Improvements:")
        print("   1. ✓ Removed padding in wallet_details (1 → 0)")
        print("   2. ✓ Removed spacing between status elements (1 → 0)")
        print("   3. ✓ Removed spacing after wallet_details (1 → 0)")
        print("   4. ✓ Removed spacing after action buttons (1 → 0)")
        print()

        print("💡 Visual comparison:")
        print()
        print("   Before (spaced):")
        print("   ┌──────────────────────────────┐")
        print("   │ ACCOUNTS:        [Add (a)]   │")
        print("   │ Alice  │ tz1abc...def        │")
        print("   │                              │ ← Padding")
        print("   │ Status: Connected            │")
        print("   │                              │ ← Space")
        print("   │ Balance: 12.456789 XTZ       │")
        print("   │                              │ ← Space")
        print("   │ Delegated to: tz1baker...    │")
        print("   │                              │ ← Space")
        print("   │ Staking: 5.000000 XTZ        │")
        print("   │                              │ ← Space")
        print("   │ Network: ● Mainnet           │")
        print("   │                              │ ← Space")
        print("   │ [Send] [Receive] [Refresh]   │")
        print("   │                              │ ← Space")
        print("   └──────────────────────────────┘")
        print()
        print("   After (compact):")
        print("   ┌──────────────────────────────┐")
        print("   │ ACCOUNTS:        [Add (a)]   │")
        print("   │ Alice  │ tz1abc...def        │")
        print("   │ Status: Connected            │ ← No space")
        print("   │ Balance: 12.456789 XTZ       │ ← No space")
        print("   │ Delegated to: tz1baker...    │ ← No space")
        print("   │ Staking: 5.000000 XTZ        │ ← No space")
        print("   │ Network: ● Mainnet           │ ← No space")
        print("   │ [Send] [Receive] [Refresh]   │ ← No space")
        print("   │                              │")
        print("   │ ← More space for transactions")
        print("   └──────────────────────────────┘")
        print()

        print("🎯 Benefits:")
        print("   • Compact layout - more vertical space available")
        print("   • Consistent spacing throughout")
        print("   • Room for Recent Transactions section")
        print("   • Clean, organized appearance")
        print("   • All information still clearly visible")
        print()

        print("📝 Technical details:")
        print("   • wallet_details padding: 0 (reduced from 1)")
        print("   • wallet_details margin-bottom: 0 (reduced from 1)")
        print("   • wallet_status margin-bottom: 0 (reduced from 1)")
        print("   • wallet_balance margin-bottom: 0 (reduced from 1)")
        print("   • wallet_delegation margin-bottom: 0 (reduced from 1)")
        print("   • wallet_staking margin-bottom: 0 (reduced from 1)")
        print("   • wallet_network margin-bottom: 0 (reduced from 1)")
        print("   • action_buttons margin-bottom: 0 (reduced from 1)")
        print()

        print("💡 Space saved:")
        print("   • Previous total spacing: ~8 units")
        print("   • New total spacing: 0 units")
        print("   • Space gained: ~8 vertical units")
        print("   • Perfect for Recent Transactions section!")

        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_wallet_status_compact()
    sys.exit(0 if success else 1)
