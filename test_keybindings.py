#!/usr/bin/env python3
"""Test script to verify new keybindings are working."""

import sys
from pathlib import Path

print("\n" + "=" * 70)
print("🧪 TEST DE KEYBINDINGS - NUEVAS FUNCIONES")
print("=" * 70 + "\n")

# Import app
try:
    from app import WalletApp
    print("✅ Import de WalletApp exitoso\n")
except Exception as e:
    print(f"❌ Error importando WalletApp: {e}")
    sys.exit(1)

# Check bindings
print("🎹 VERIFICANDO BINDINGS:")
print("-" * 70)

try:
    bindings = WalletApp.BINDINGS

    # Map of key -> expected action
    expected_bindings = {
        "delete": "delete_wallet",
        "b": "backup",
        "a": "show_address",
        "e": "export_history",
        "ctrl+r": "toggle_auto_refresh"
    }

    # Check each binding
    binding_map = {b.key: b.action for b in bindings}

    for key, expected_action in expected_bindings.items():
        if key in binding_map:
            actual_action = binding_map[key]
            if actual_action == expected_action:
                print(f"  ✅ '{key}' -> {actual_action}")
            else:
                print(f"  ❌ '{key}' -> {actual_action} (esperado: {expected_action})")
        else:
            print(f"  ❌ '{key}' NO ENCONTRADA en bindings")

except Exception as e:
    print(f"  ❌ Error: {e}")

# Check action methods
print("\n⚙️  VERIFICANDO ACTION METHODS:")
print("-" * 70)

action_methods = [
    "action_backup",
    "action_delete_wallet",
    "action_show_address",
    "action_export_history",
    "action_toggle_auto_refresh"
]

for method in action_methods:
    if hasattr(WalletApp, method):
        func = getattr(WalletApp, method)
        # Check if it's callable
        if callable(func):
            print(f"  ✅ WalletApp.{method}() - callable")
        else:
            print(f"  ⚠️  WalletApp.{method}() - exists but not callable")
    else:
        print(f"  ❌ WalletApp.{method}() - NOT FOUND")

# Test backup functionality (without GUI)
print("\n💾 TEST DE FUNCIONALIDAD (sin GUI):")
print("-" * 70)

# Test backup can create directory
try:
    backup_dir = Path("data/backups")
    backup_dir.mkdir(parents=True, exist_ok=True)
    print(f"  ✅ Directorio data/backups/ se puede crear")
except Exception as e:
    print(f"  ❌ Error creando directorio: {e}")

# Test export can create directory
try:
    export_dir = Path("data/exports")
    export_dir.mkdir(parents=True, exist_ok=True)
    print(f"  ✅ Directorio data/exports/ se puede crear")
except Exception as e:
    print(f"  ❌ Error creando directorio: {e}")

print("\n" + "=" * 70)
print("📋 INSTRUCCIONES PARA PROBAR EN LA APP:")
print("=" * 70)
print("""
Si todos los checks anteriores son ✅, las funciones ESTÁN en el código.

Para probarlas en la app:

1. ASEGÚRATE DE TENER UNA WALLET SELECCIONADA
   - Usa las flechas o mouse para seleccionar una wallet
   - La wallet seleccionada se ve resaltada

2. PRUEBA CADA TECLA:

   Tecla 'b' (Backup):
   - Presiona: b
   - Busca en la barra de estado (abajo): "✅ Backup created..."
   - Verifica: ls data/backups/

   Tecla 'a' (Show Address):
   - Presiona: a
   - Debe aparecer un modal con la dirección completa

   Tecla 'e' (Export CSV):
   - Presiona: e
   - Busca mensaje: "✅ Exported X transaction(s)..." o "ℹ️ No transaction history"
   - Verifica: ls data/exports/

   Tecla 'Delete' (Eliminar Wallet):
   - Presiona: Delete (o Supr)
   - Debe aparecer modal de confirmación amarillo/rojo
   - Puedes cancelar con ESC o "No"

   Teclas 'Ctrl+R' (Auto-refresh):
   - Presiona: Ctrl+R
   - Busca mensaje: "✅ Auto-refresh enabled" o "🛑 Auto-refresh disabled"

3. DÓNDE MIRAR LOS MENSAJES:
   - Línea de STATUS (parte inferior de la pantalla)
   - Modales que aparecen en el centro

4. SI NO FUNCIONA:
   - Verifica que la wallet esté SELECCIONADA (resaltada)
   - Cierra la app completamente (q o Ctrl+C)
   - Ejecuta: python3 app.py
   - Intenta de nuevo

5. VER LOGS:
   - En otra terminal: tail -f logs/wallet.log
   - Presiona las teclas y mira si aparecen logs
""")
print("=" * 70 + "\n")
