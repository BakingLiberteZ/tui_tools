#!/usr/bin/env python3
"""Verify that modal border colors match their corresponding button colors."""

import sys
import re

print("\n" + "=" * 70)
print("🎨 VERIFICACIÓN DE COLORES: Botones y Modales")
print("=" * 70 + "\n")

# Test 1: Import classes
try:
    from app import (
        WalletApp, ConfirmScreen, PromptScreen,
        BackupWalletSelectorScreen, ExportWalletSelectorScreen
    )
    print("✅ Import exitoso de todas las clases\n")
except Exception as e:
    print(f"❌ Error al importar: {e}")
    sys.exit(1)

# Color mappings
BUTTON_COLORS = {
    "Import": "#3b82f6",   # Azul
    "Backup": "#10b981",   # Verde
    "Export": "#8b5cf6",   # Morado
    "Delete": "#ef4444",   # Rojo
}

MODAL_CLASSES = {
    "Import": PromptScreen,
    "Backup": BackupWalletSelectorScreen,
    "Export": ExportWalletSelectorScreen,
    "Delete": ConfirmScreen,
}

# Test 2: Verify button colors in CSS
print("🔘 COLORES DE BOTONES:")
print("-" * 70)

button_ids = {
    "Import": "#add",
    "Backup": "#backup",
    "Export": "#export",
    "Delete": "#delete",
}

css = WalletApp.CSS
all_button_colors_ok = True

for action, expected_color in BUTTON_COLORS.items():
    button_id = button_ids[action]
    # Find button CSS block
    pattern = f"{button_id}\\s*{{[^}}]*background:\\s*({expected_color})[^}}]*}}"
    match = re.search(pattern, css, re.DOTALL)

    if match:
        print(f"  ✅ Botón {action:<10} color: {expected_color} (correcto)")
    else:
        print(f"  ❌ Botón {action:<10} color no coincide o no encontrado")
        all_button_colors_ok = False

# Test 3: Verify modal border colors
print("\n🪟 COLORES DE BORDES DE MODALES:")
print("-" * 70)

all_modal_colors_ok = True

for action, modal_class in MODAL_CLASSES.items():
    expected_color = BUTTON_COLORS[action]
    modal_css = modal_class.CSS

    # Look for border with the expected color
    border_pattern = f"border:\\s*\\w+\\s*({expected_color})"
    match = re.search(border_pattern, modal_css)

    if match:
        print(f"  ✅ Modal {action:<10} borde: {expected_color} (correcto)")
    else:
        print(f"  ❌ Modal {action:<10} borde NO coincide con {expected_color}")
        all_modal_colors_ok = False

# Test 4: Verify button-modal alignment
print("\n🔗 ALINEACIÓN BOTÓN ↔ MODAL:")
print("-" * 70)

all_alignments_ok = True

for action in BUTTON_COLORS.keys():
    button_color = BUTTON_COLORS[action]
    modal_class = MODAL_CLASSES[action]
    modal_css = modal_class.CSS

    # Check if modal border has the same color as button
    if button_color in modal_css:
        print(f"  ✅ {action:<10} Botón ({button_color}) ↔ Modal ({button_color})")
    else:
        print(f"  ❌ {action:<10} Botón ({button_color}) ✗ Modal (color diferente)")
        all_alignments_ok = False

# Test 5: Verify border style is "heavy"
print("\n📏 ESTILO DE BORDES (debe ser 'heavy'):")
print("-" * 70)

all_heavy = True

for action, modal_class in MODAL_CLASSES.items():
    modal_css = modal_class.CSS

    if "border: heavy" in modal_css:
        print(f"  ✅ Modal {action:<10} usa 'heavy' (prominente)")
    else:
        print(f"  ⚠️  Modal {action:<10} NO usa 'heavy' (menos prominente)")
        all_heavy = False

# Test 6: Check that new classes exist and inherit correctly
print("\n🏗️  ARQUITECTURA DE CLASES:")
print("-" * 70)

try:
    from app import WalletSelectorScreen

    # Check BackupWalletSelectorScreen
    if issubclass(BackupWalletSelectorScreen, WalletSelectorScreen):
        print("  ✅ BackupWalletSelectorScreen hereda de WalletSelectorScreen")
    else:
        print("  ❌ BackupWalletSelectorScreen NO hereda correctamente")

    # Check ExportWalletSelectorScreen
    if issubclass(ExportWalletSelectorScreen, WalletSelectorScreen):
        print("  ✅ ExportWalletSelectorScreen hereda de WalletSelectorScreen")
    else:
        print("  ❌ ExportWalletSelectorScreen NO hereda correctamente")

    inheritance_ok = True
except Exception as e:
    print(f"  ❌ Error verificando herencia: {e}")
    inheritance_ok = False

# Summary
print("\n" + "=" * 70)
print("📊 RESUMEN")
print("=" * 70)

tests = [
    ("Colores de botones correctos", all_button_colors_ok),
    ("Colores de bordes de modales correctos", all_modal_colors_ok),
    ("Alineación botón-modal correcta", all_alignments_ok),
    ("Bordes usan estilo 'heavy'", all_heavy),
    ("Herencia de clases correcta", inheritance_ok),
]

total = len(tests)
passed = sum(1 for _, ok in tests if ok)

for name, ok in tests:
    status = "✅" if ok else "❌"
    print(f"{status} {name}")

print(f"\n✅ Tests pasados: {passed}/{total}")

if passed == total:
    print("\n🎉 TODOS LOS COLORES ESTÁN ALINEADOS CORRECTAMENTE!")
    print("\nEsquema de colores:")
    print("  🔵 Import  (Azul)   #3b82f6  →  Modal con borde azul")
    print("  🟢 Backup  (Verde)  #10b981  →  Modal con borde verde")
    print("  🟣 Export  (Morado) #8b5cf6  →  Modal con borde morado")
    print("  🔴 Delete  (Rojo)   #ef4444  →  Modal con borde rojo")
    print("\nPruébalo en la app:")
    print("  python3 app.py")
    print("\nClick en cada botón y verifica que el borde del modal coincida:")
    print("  • [Import (i)]  → Modal azul")
    print("  • [Backup (b)]  → Modal verde")
    print("  • [Export (e)]  → Modal morado")
    print("  • [Delete (Del)] → Modal rojo")
    print("\n¡Coherencia visual perfecta! 🎨")
else:
    print("\n⚠️  Algunos colores no están alineados correctamente")

print("\n" + "=" * 70 + "\n")
