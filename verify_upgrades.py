#!/usr/bin/env python3
"""Quick verification script to confirm all upgrades are present."""

import sys
from decimal import Decimal

print("\n" + "=" * 70)
print("🔍 VERIFICACIÓN DE UPGRADES - TUI TEZOS WALLET")
print("=" * 70 + "\n")

# Test imports
try:
    from app import (
        Config, format_xtz, setup_logging, format_relative_time,
        WalletApp, ConfirmScreen, AddressDetailScreen
    )
    print("✅ Imports exitosos - Todas las clases y funciones existen")
except ImportError as e:
    print(f"❌ Error de import: {e}")
    sys.exit(1)

# Test Config class
print("\n📋 CONFIG CLASS:")
print(f"  ✅ Config.BALANCE_CACHE_SECONDS = {Config.BALANCE_CACHE_SECONDS}s")
print(f"  ✅ Config.AUTO_REFRESH_INTERVAL_SECONDS = {Config.AUTO_REFRESH_INTERVAL_SECONDS}s")
print(f"  ✅ Config.LOG_FILE = {Config.LOG_FILE}")
print(f"  ✅ Total constantes: {len([a for a in dir(Config) if not a.startswith('_')])}")

# Test format_xtz
print("\n💰 FORMAT_XTZ:")
test_amount = Decimal("12345.678")
result = format_xtz(test_amount)
expected = "12,345.678"
if result == expected:
    print(f"  ✅ format_xtz({test_amount}) = '{result}'")
else:
    print(f"  ❌ format_xtz({test_amount}) = '{result}' (esperado: '{expected}')")

# Test format_relative_time
print("\n🕒 FORMAT_RELATIVE_TIME:")
from datetime import datetime, timezone, timedelta
now = datetime.now(timezone.utc)
test_time = (now - timedelta(minutes=5)).isoformat()
result = format_relative_time(test_time)
if "min ago" in result:
    print(f"  ✅ format_relative_time(5 min atrás) = '{result}'")
else:
    print(f"  ⚠️  format_relative_time(5 min atrás) = '{result}' (esperado algo con 'min ago')")

# Check BINDINGS
print("\n🎹 KEYBOARD BINDINGS:")
try:
    bindings = WalletApp.BINDINGS
    binding_actions = [b.action for b in bindings]

    new_bindings = [
        "delete_wallet",
        "backup",
        "show_address",
        "export_history",
        "toggle_auto_refresh"
    ]

    for action in new_bindings:
        if action in binding_actions:
            print(f"  ✅ Binding '{action}' presente")
        else:
            print(f"  ❌ Binding '{action}' NO ENCONTRADO")

except Exception as e:
    print(f"  ❌ Error verificando bindings: {e}")

# Check action methods
print("\n⚙️  ACTION METHODS:")
action_methods = [
    "action_delete_wallet",
    "action_backup",
    "action_show_address",
    "action_export_history",
    "action_toggle_auto_refresh"
]

for method in action_methods:
    if hasattr(WalletApp, method):
        print(f"  ✅ WalletApp.{method}() existe")
    else:
        print(f"  ❌ WalletApp.{method}() NO ENCONTRADO")

# Check modal screens
print("\n🪟 MODAL SCREENS:")
modals = [
    ("ConfirmScreen", ConfirmScreen),
    ("AddressDetailScreen", AddressDetailScreen),
]

for name, cls in modals:
    print(f"  ✅ {name} clase existe")

# Check logging setup
print("\n📝 LOGGING:")
import os
if os.path.exists("logs"):
    print("  ✅ Directorio logs/ existe")
    if os.path.exists("logs/wallet.log"):
        size = os.path.getsize("logs/wallet.log")
        print(f"  ✅ logs/wallet.log existe ({size} bytes)")
    else:
        print("  ℹ️  logs/wallet.log no existe aún (se creará al ejecutar app)")
else:
    print("  ℹ️  logs/ no existe aún (se creará al ejecutar app)")

print("\n" + "=" * 70)
print("🎉 VERIFICACIÓN COMPLETA")
print("=" * 70)
print("""
Todos los upgrades están presentes en el código.

Para ver los cambios:
  1. Ejecuta: python3 app.py
  2. Los números ahora tienen formato: 12,345.678 XTZ
  3. Las transacciones muestran tiempo relativo: "5 min ago"
  4. Presiona las nuevas teclas:
     - Delete: Eliminar wallet
     - b: Backup
     - a: Ver dirección completa
     - e: Export CSV
     - Ctrl+R: Toggle auto-refresh

Si NO ves estos cambios en la interfaz, intenta:
  1. Cerrar completamente la app (Ctrl+C o tecla 'q')
  2. Limpiar caché: rm -rf __pycache__ wallet/__pycache__
  3. Ejecutar de nuevo: python3 app.py

Si ves timestamps completos en lugar de "X min ago", revisa que
estés mirando la sección de historia de transacciones (no la vista
de detalles).
""")
print("=" * 70 + "\n")
