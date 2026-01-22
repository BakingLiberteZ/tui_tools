#!/usr/bin/env python3
"""Verify that all modal sizes have been optimized correctly."""

import sys
import re

print("\n" + "=" * 70)
print("📐 VERIFICACIÓN DE TAMAÑOS DE MODALES")
print("=" * 70 + "\n")

# Test 1: Import classes
try:
    from app import (
        WalletApp, ConfirmScreen, PromptScreen, NetworkPickerScreen,
        ReceiveScreen, AddressDetailScreen, WalletSelectorScreen
    )
    print("✅ Import exitoso de todas las clases de modales\n")
except Exception as e:
    print(f"❌ Error al importar: {e}")
    sys.exit(1)

# Test 2: Check modal sizes
print("📊 TAMAÑOS DE MODALES:")
print("-" * 70)

expected_sizes = {
    "PromptScreen": 50,
    "ConfirmScreen": 55,
    "NetworkPickerScreen": 60,
    "ReceiveScreen": 65,
    "AddressDetailScreen": 80,
    "WalletSelectorScreen": 70,
}

all_sizes_correct = True

for modal_name, expected_width in expected_sizes.items():
    try:
        modal_class = eval(modal_name)
        css = modal_class.CSS

        # Extract width from CSS using regex
        width_match = re.search(r'width:\s*(\d+)', css)

        if width_match:
            actual_width = int(width_match.group(1))
            status = "✅" if actual_width == expected_width else "❌"

            if actual_width == expected_width:
                print(f"  {status} {modal_name:<25} width: {actual_width} (correcto)")
            else:
                print(f"  {status} {modal_name:<25} width: {actual_width} (esperado: {expected_width})")
                all_sizes_correct = False
        else:
            print(f"  ❌ {modal_name:<25} No se encontró 'width' en CSS")
            all_sizes_correct = False

    except Exception as e:
        print(f"  ❌ {modal_name:<25} Error: {e}")
        all_sizes_correct = False

# Test 3: Verify changes were applied
print("\n📝 CAMBIOS APLICADOS:")
print("-" * 70)

changes = [
    ("PromptScreen", "60 → 50", "Inputs simples más compactos"),
    ("ConfirmScreen", "60 → 55", "Confirmaciones más compactas"),
    ("NetworkPickerScreen", "70 → 60", "Selector de red más compacto"),
    ("ReceiveScreen", "70 → 65", "Pantalla de recibir optimizada"),
]

for modal_name, change, description in changes:
    modal_class = eval(modal_name)
    css = modal_class.CSS
    width_match = re.search(r'width:\s*(\d+)', css)

    if width_match:
        actual_width = int(width_match.group(1))
        # Check if it matches the "después" value
        after_width = int(change.split("→")[1].strip())

        if actual_width == after_width:
            print(f"  ✅ {modal_name:<25} {change:<15} {description}")
        else:
            print(f"  ❌ {modal_name:<25} {change:<15} NO aplicado (actual: {actual_width})")
    else:
        print(f"  ❌ {modal_name:<25} {change:<15} No se pudo verificar")

# Test 4: Check that large modals remained unchanged
print("\n🔍 MODALES QUE NO CAMBIARON (OK):")
print("-" * 70)

unchanged_modals = [
    ("AddressDetailScreen", 80, "Necesita mostrar dirección completa"),
    ("WalletSelectorScreen", 70, "Lista de wallets necesita espacio"),
]

for modal_name, expected_width, reason in unchanged_modals:
    try:
        modal_class = eval(modal_name)
        css = modal_class.CSS
        width_match = re.search(r'width:\s*(\d+)', css)

        if width_match:
            actual_width = int(width_match.group(1))
            if actual_width == expected_width:
                print(f"  ✅ {modal_name:<25} width: {actual_width} ({reason})")
            else:
                print(f"  ⚠️  {modal_name:<25} width: {actual_width} (esperado: {expected_width})")
        else:
            print(f"  ❌ {modal_name:<25} No se encontró 'width' en CSS")

    except Exception as e:
        print(f"  ❌ {modal_name:<25} Error: {e}")

# Summary
print("\n" + "=" * 70)
print("📊 RESUMEN")
print("=" * 70)

if all_sizes_correct:
    print("\n🎉 TODAS LAS OPTIMIZACIONES APLICADAS CORRECTAMENTE!")
    print("\nCambios realizados:")
    print("  • PromptScreen:        60 → 50 (-10)")
    print("  • ConfirmScreen:       60 → 55 (-5)")
    print("  • NetworkPickerScreen: 70 → 60 (-10)")
    print("  • ReceiveScreen:       70 → 65 (-5)")
    print("\nBeneficios:")
    print("  ✅ Modales más proporcionados al contenido")
    print("  ✅ Mejor uso del espacio de pantalla")
    print("  ✅ Interfaz más limpia y profesional")
    print("  ✅ Inputs no se ven 'perdidos' en modales grandes")
    print("\nPruébalo:")
    print("  python3 app.py")
    print("\nPresiona:")
    print("  • 's' → Enter amount (modal más compacto)")
    print("  • 'i' → Import wallet → Enter passphrase (modal más compacto)")
    print("  • 'Delete' → Confirmation (modal más compacto)")
    print("  • 'n' → Network selector (modal más compacto)")
    print("  • 'x' → Receive (modal más compacto)")
else:
    print("\n⚠️  Algunos tamaños no coinciden con lo esperado")

print("\n" + "=" * 70 + "\n")
