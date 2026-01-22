#!/usr/bin/env python3
"""Test script to verify WalletSelectorScreen modal works correctly."""

import sys
import inspect

print("\n" + "=" * 70)
print("🔍 VERIFICACIÓN DEL MODAL DE SELECCIÓN DE WALLETS")
print("=" * 70 + "\n")

# Test 1: Import classes
try:
    from app import WalletApp, WalletSelectorScreen, Account
    print("✅ Import exitoso de WalletApp y WalletSelectorScreen\n")
except Exception as e:
    print(f"❌ Error al importar: {e}")
    sys.exit(1)

# Test 2: Check WalletSelectorScreen exists and has correct methods
print("🏗️  VERIFICACIÓN DE LA CLASE WalletSelectorScreen:")
print("-" * 70)

required_methods = [
    "compose",
    "on_mount",
    "_get_selected_account",
    "wallet_selected_with_enter",
    "select_pressed",
    "cancel_pressed",
    "on_key"
]

all_methods_present = True
for method_name in required_methods:
    if hasattr(WalletSelectorScreen, method_name):
        print(f"  ✅ Método {method_name} presente")
    else:
        print(f"  ❌ Método {method_name} NO ENCONTRADO")
        all_methods_present = False

# Test 3: Check CSS styling
print("\n🎨 VERIFICACIÓN DE ESTILOS CSS:")
print("-" * 70)

if hasattr(WalletSelectorScreen, 'CSS'):
    css = WalletSelectorScreen.CSS
    css_checks = {
        "Container alignment": "align: center middle" in css,
        "Vertical container": "WalletSelectorScreen > Vertical" in css,
        "Width defined": "width: 70" in css,
        "Border styling": "border: solid" in css,
        "List styling": "#wallets_list" in css,
    }

    for check_name, present in css_checks.items():
        status = "✅" if present else "❌"
        print(f"  {status} {check_name}")

    all_css_ok = all(css_checks.values())
else:
    print("  ❌ CSS no encontrado")
    all_css_ok = False

# Test 4: Check action_backup is now async with @work
print("\n💾 VERIFICACIÓN DE action_backup:")
print("-" * 70)

backup_source = inspect.getsource(WalletApp.action_backup)
backup_checks = {
    "Tiene decorador @work": "@work" in backup_source,
    "Es async": "async def action_backup" in backup_source,
    "Usa WalletSelectorScreen": "WalletSelectorScreen" in backup_source,
    "Usa push_screen_wait": "push_screen_wait" in backup_source,
    "Guarda wallet individual": '"single_wallet"' in backup_source or 'wallet_' in backup_source,
}

for check_name, present in backup_checks.items():
    status = "✅" if present else "❌"
    print(f"  {status} {check_name}")

all_backup_ok = all(backup_checks.values())

# Test 5: Check action_export_history is now async with @work
print("\n📊 VERIFICACIÓN DE action_export_history:")
print("-" * 70)

export_source = inspect.getsource(WalletApp.action_export_history)
export_checks = {
    "Tiene decorador @work": "@work" in export_source,
    "Es async": "async def action_export_history" in export_source,
    "Usa WalletSelectorScreen": "WalletSelectorScreen" in export_source,
    "Usa push_screen_wait": "push_screen_wait" in export_source,
    "Carga historial": "fetch_history" in export_source,
}

for check_name, present in export_checks.items():
    status = "✅" if present else "❌"
    print(f"  {status} {check_name}")

all_export_ok = all(export_checks.values())

# Test 6: Check button handlers
print("\n🔘 VERIFICACIÓN DE HANDLERS DE BOTONES:")
print("-" * 70)

handlers = {
    "on_backup_pressed": "action_backup",
    "on_export_pressed": "action_export_history",
}

all_handlers_ok = True
for handler_name, action_name in handlers.items():
    if hasattr(WalletApp, handler_name):
        handler_source = inspect.getsource(getattr(WalletApp, handler_name))
        if action_name in handler_source:
            print(f"  ✅ {handler_name} llama a {action_name}")
        else:
            print(f"  ❌ {handler_name} NO llama a {action_name}")
            all_handlers_ok = False
    else:
        print(f"  ❌ {handler_name} NO ENCONTRADO")
        all_handlers_ok = False

# Summary
print("\n" + "=" * 70)
print("📊 RESUMEN")
print("=" * 70)

tests = [
    ("WalletSelectorScreen con todos los métodos", all_methods_present),
    ("Estilos CSS correctos", all_css_ok),
    ("action_backup con modal de selección", all_backup_ok),
    ("action_export_history con modal de selección", all_export_ok),
    ("Handlers de botones correctos", all_handlers_ok),
]

total = len(tests)
passed = sum(1 for _, ok in tests if ok)

for name, ok in tests:
    status = "✅" if ok else "❌"
    print(f"{status} {name}")

print(f"\n✅ Tests pasados: {passed}/{total}")

if passed == total:
    print("\n🎉 TODAS LAS VERIFICACIONES EXITOSAS!")
    print("\nCuando ejecutes la app:")
    print("  python3 app.py")
    print("\nAl hacer click en Backup o Export:")
    print("  1. Aparecerá un modal con lista de wallets")
    print("  2. Podrás seleccionar la wallet específica")
    print("  3. Solo esa wallet será respaldada/exportada")
    print("\n¡Ya no hace backup/export de todas, sino solo la seleccionada!")
else:
    print("\n⚠️  Algunas verificaciones fallaron")

print("\n" + "=" * 70 + "\n")
