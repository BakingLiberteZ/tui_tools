#!/usr/bin/env python3
"""Test script to verify UI changes are present and working."""

import sys

print("\n" + "=" * 70)
print("🎨 UI CHANGES VERIFICATION TEST")
print("=" * 70 + "\n")

# Test 1: Import app
try:
    from app import WalletApp
    print("✅ Import WalletApp successful\n")
except Exception as e:
    print(f"❌ Failed to import WalletApp: {e}")
    sys.exit(1)

# Test 2: Check BINDINGS
print("🎹 KEYBOARD BINDINGS CHECK:")
print("-" * 70)

bindings_map = {b.key: (b.action, b.show) for b in WalletApp.BINDINGS}

# These should now be visible (show=True)
newly_visible = {
    "b": "backup",
    "e": "export_history",
    "a": "show_address",
    "delete": "delete_wallet"
}

all_visible = True
for key, expected_action in newly_visible.items():
    if key not in bindings_map:
        print(f"  ❌ Key '{key}' not found in bindings")
        all_visible = False
        continue

    action, show = bindings_map[key]
    if action != expected_action:
        print(f"  ❌ Key '{key}' has wrong action: {action} (expected: {expected_action})")
        all_visible = False
        continue

    if not show:
        print(f"  ❌ Key '{key}' is HIDDEN (show=False) - should be visible!")
        all_visible = False
        continue

    print(f"  ✅ Key '{key}' -> {action} (visible in footer)")

if all_visible:
    print("\n✅ All new shortcuts are now VISIBLE in the footer!")
else:
    print("\n⚠️  Some shortcuts are still hidden")

# Test 3: Check compose method has new structure
print("\n🏗️  UI STRUCTURE CHECK:")
print("-" * 70)

import inspect
compose_source = inspect.getsource(WalletApp.compose)

checks = {
    "New buttons present": 'Button("Backup (b)"' in compose_source,
    "Export button present": 'Button("Export (e)"' in compose_source,
    "Delete button present": 'Button("Delete (Del)"' in compose_source,
    "Column header present": "accounts_columns_header" in compose_source,
    '"ACCOUNTS:" removed': 'Static("ACCOUNTS:"' not in compose_source,
}

for check_name, result in checks.items():
    status = "✅" if result else "❌"
    print(f"  {status} {check_name}")

all_checks_passed = all(checks.values())

# Test 4: Check CSS for new buttons
print("\n🎨 CSS STYLES CHECK:")
print("-" * 70)

css_checks = {
    "Backup button style": "#backup {" in WalletApp.CSS,
    "Export button style": "#export {" in WalletApp.CSS,
    "Delete button style": "#delete {" in WalletApp.CSS,
    "Column header style": "#accounts_columns_header" in WalletApp.CSS,
}

for check_name, result in css_checks.items():
    status = "✅" if result else "❌"
    print(f"  {status} {check_name}")

all_css_passed = all(css_checks.values())

# Test 5: Check button handlers
print("\n🔧 BUTTON HANDLERS CHECK:")
print("-" * 70)

handler_checks = [
    ("on_backup_pressed", "Backup button handler"),
    ("on_export_pressed", "Export button handler"),
    ("on_delete_pressed", "Delete button handler"),
]

all_handlers_present = True
for method_name, description in handler_checks:
    if hasattr(WalletApp, method_name):
        print(f"  ✅ {description} present")
    else:
        print(f"  ❌ {description} NOT FOUND")
        all_handlers_present = False

# Test 6: Check _set_busy includes new buttons
print("\n⏸️  BUSY STATE CHECK:")
print("-" * 70)

set_busy_source = inspect.getsource(WalletApp._set_busy)
busy_buttons = ["#add", "#backup", "#export", "#delete", "#refresh", "#send", "#recv"]
missing_buttons = []

for btn_id in busy_buttons:
    if btn_id in set_busy_source:
        print(f"  ✅ {btn_id} will be disabled when busy")
    else:
        print(f"  ❌ {btn_id} NOT in _set_busy")
        missing_buttons.append(btn_id)

# Summary
print("\n" + "=" * 70)
print("📊 SUMMARY")
print("=" * 70)

total_tests = 6
passed_tests = sum([
    all_visible,
    all_checks_passed,
    all_css_passed,
    all_handlers_present,
    len(missing_buttons) == 0,
    True  # Import test always passes if we get here
])

print(f"\nTests Passed: {passed_tests}/{total_tests}")

if passed_tests == total_tests:
    print("\n🎉 ALL UI CHANGES SUCCESSFULLY APPLIED!")
    print("\nYou can now:")
    print("  1. Run: python3 app.py")
    print("  2. See the new buttons at the top")
    print("  3. See column headers above the wallet list")
    print("  4. See all shortcuts in the footer")
    print("\nEverything is now visible and easy to use!")
else:
    print("\n⚠️  Some UI changes may be missing. Check the errors above.")

print("\n" + "=" * 70 + "\n")
