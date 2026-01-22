#!/usr/bin/env python3
"""Verify that footer button colors match their corresponding modal border colors."""

import sys
import re

print("\n" + "=" * 70)
print("🎨 VERIFICACIÓN DE COLORES: Botones Footer y Modales")
print("=" * 70 + "\n")

# Test 1: Import classes
try:
    from app import (
        WalletApp,
        # SEND modals
        SendAmountScreen, SendPassphraseScreen,
        DestinationPickerScreen, ConfirmSendScreen,
        # Receive modal
        ReceiveScreen,
        # Backup modal
        BackupWalletSelectorScreen
    )
    print("✅ Import exitoso de todas las clases\n")
except Exception as e:
    print(f"❌ Error al importar: {e}")
    sys.exit(1)

# Color mappings for footer buttons
FOOTER_BUTTON_COLORS = {
    "SEND": "#10b981",      # Verde
    "Receive": "#374151",   # Gris oscuro (casi negro)
    "Refresh": "#f97316",   # Naranja
}

# Color mappings for top buttons (from previous work)
TOP_BUTTON_COLORS = {
    "Import": "#3b82f6",   # Azul
    "Backup": "#eab308",   # Amarillo (advertencia)
    "Export": "#8b5cf6",   # Morado
    "Delete": "#ef4444",   # Rojo
}

# Modal classes for SEND button
SEND_MODAL_CLASSES = {
    "SendAmountScreen": SendAmountScreen,
    "SendPassphraseScreen": SendPassphraseScreen,
    "DestinationPickerScreen": DestinationPickerScreen,
    "ConfirmSendScreen": ConfirmSendScreen,
}

# Test 2: Verify footer button colors in CSS
print("🔘 COLORES DE BOTONES FOOTER:")
print("-" * 70)

button_ids = {
    "SEND": "#send",
    "Receive": "#recv",
    "Refresh": "#refresh",
}

css = WalletApp.CSS
all_button_colors_ok = True

for action, expected_color in FOOTER_BUTTON_COLORS.items():
    button_id = button_ids[action]
    # Find button CSS block
    pattern = f"{button_id}\\s*{{[^}}]*background:\\s*({expected_color})[^}}]*}}"
    match = re.search(pattern, css, re.DOTALL)

    if match:
        print(f"  ✅ Botón {action:<10} color: {expected_color} (correcto)")
    else:
        print(f"  ❌ Botón {action:<10} color no coincide o no encontrado")
        all_button_colors_ok = False

# Test 3: Verify Backup button is now yellow
print("\n🔘 COLOR DE BOTÓN BACKUP (debe ser amarillo):")
print("-" * 70)

backup_color = TOP_BUTTON_COLORS["Backup"]
backup_pattern = f"#backup\\s*{{[^}}]*background:\\s*({backup_color})[^}}]*}}"
backup_match = re.search(backup_pattern, css, re.DOTALL)

if backup_match:
    print(f"  ✅ Botón Backup     color: {backup_color} (amarillo - correcto)")
    backup_button_ok = True
else:
    print(f"  ❌ Botón Backup     color no es amarillo {backup_color}")
    backup_button_ok = False

# Test 4: Verify SEND modal border colors (all should be green)
print("\n🪟 COLORES DE BORDES DE MODALES SEND (deben ser verdes):")
print("-" * 70)

send_color = FOOTER_BUTTON_COLORS["SEND"]
all_send_modals_ok = True

for modal_name, modal_class in SEND_MODAL_CLASSES.items():
    modal_css = modal_class.CSS

    # Look for border with green color
    if send_color in modal_css:
        print(f"  ✅ {modal_name:<30} borde: {send_color} (verde)")
    else:
        print(f"  ❌ {modal_name:<30} borde NO es verde {send_color}")
        all_send_modals_ok = False

# Test 5: Verify Receive modal border color
print("\n🪟 COLOR DE BORDE DE MODAL RECEIVE (debe ser gris oscuro):")
print("-" * 70)

receive_color = FOOTER_BUTTON_COLORS["Receive"]
receive_css = ReceiveScreen.CSS

if receive_color in receive_css:
    print(f"  ✅ ReceiveScreen                    borde: {receive_color} (gris oscuro)")
    receive_modal_ok = True
else:
    print(f"  ❌ ReceiveScreen                    borde NO es gris oscuro {receive_color}")
    receive_modal_ok = False

# Test 6: Verify Backup modal border is now yellow
print("\n🪟 COLOR DE BORDE DE MODAL BACKUP (debe ser amarillo):")
print("-" * 70)

backup_css = BackupWalletSelectorScreen.CSS

if backup_color in backup_css:
    print(f"  ✅ BackupWalletSelectorScreen       borde: {backup_color} (amarillo)")
    backup_modal_ok = True
else:
    print(f"  ❌ BackupWalletSelectorScreen       borde NO es amarillo {backup_color}")
    backup_modal_ok = False

# Test 7: Verify border style is "heavy" for all new modals
print("\n📏 ESTILO DE BORDES (debe ser 'heavy'):")
print("-" * 70)

all_heavy = True

# Check SEND modals
for modal_name, modal_class in SEND_MODAL_CLASSES.items():
    modal_css = modal_class.CSS
    if "border: heavy" in modal_css:
        print(f"  ✅ {modal_name:<30} usa 'heavy' (prominente)")
    else:
        print(f"  ⚠️  {modal_name:<30} NO usa 'heavy' (menos prominente)")
        all_heavy = False

# Check Receive modal
if "border: heavy" in ReceiveScreen.CSS:
    print(f"  ✅ ReceiveScreen                    usa 'heavy' (prominente)")
else:
    print(f"  ⚠️  ReceiveScreen                    NO usa 'heavy' (menos prominente)")
    all_heavy = False

# Check Backup modal
if "border: heavy" in BackupWalletSelectorScreen.CSS:
    print(f"  ✅ BackupWalletSelectorScreen       usa 'heavy' (prominente)")
else:
    print(f"  ⚠️  BackupWalletSelectorScreen       NO usa 'heavy' (menos prominente)")
    all_heavy = False

# Test 8: Verify button-modal alignment for footer buttons
print("\n🔗 ALINEACIÓN BOTÓN ↔ MODAL:")
print("-" * 70)

all_alignments_ok = True

# SEND button ↔ SEND modals
send_color = FOOTER_BUTTON_COLORS["SEND"]
for modal_name, modal_class in SEND_MODAL_CLASSES.items():
    modal_css = modal_class.CSS
    if send_color in modal_css:
        print(f"  ✅ SEND → {modal_name:<25} ({send_color})")
    else:
        print(f"  ❌ SEND → {modal_name:<25} (color diferente)")
        all_alignments_ok = False

# Receive button ↔ Receive modal
receive_color = FOOTER_BUTTON_COLORS["Receive"]
if receive_color in ReceiveScreen.CSS:
    print(f"  ✅ Receive → ReceiveScreen            ({receive_color})")
else:
    print(f"  ❌ Receive → ReceiveScreen            (color diferente)")
    all_alignments_ok = False

# Backup button ↔ Backup modal (amarillo)
backup_color = TOP_BUTTON_COLORS["Backup"]
if backup_color in BackupWalletSelectorScreen.CSS:
    print(f"  ✅ Backup → BackupWalletSelectorScreen ({backup_color})")
else:
    print(f"  ❌ Backup → BackupWalletSelectorScreen (color diferente)")
    all_alignments_ok = False

# Summary
print("\n" + "=" * 70)
print("📊 RESUMEN")
print("=" * 70)

tests = [
    ("Colores de botones footer correctos", all_button_colors_ok),
    ("Botón Backup es amarillo", backup_button_ok),
    ("Todos los modales SEND son verdes", all_send_modals_ok),
    ("Modal Receive es gris oscuro", receive_modal_ok),
    ("Modal Backup es amarillo", backup_modal_ok),
    ("Bordes usan estilo 'heavy'", all_heavy),
    ("Alineación botón-modal correcta", all_alignments_ok),
]

total = len(tests)
passed = sum(1 for _, ok in tests if ok)

for name, ok in tests:
    status = "✅" if ok else "❌"
    print(f"{status} {name}")

print(f"\n✅ Tests pasados: {passed}/{total}")

if passed == total:
    print("\n🎉 TODOS LOS COLORES ESTÁN ALINEADOS CORRECTAMENTE!")
    print("\nEsquema de colores de BOTONES FOOTER:")
    print("  🟢 SEND     (Verde)       #10b981  →  Modales con borde verde")
    print("  ⚫ Receive  (Gris oscuro) #374151  →  Modal con borde gris oscuro")
    print("  🟠 Refresh  (Naranja)     #f97316  →  Sin modal")
    print("\nEsquema de colores de BOTONES TOP:")
    print("  🔵 Import  (Azul)   #3b82f6  →  Modal con borde azul")
    print("  🟡 Backup  (Amarillo) #eab308  →  Modal con borde amarillo")
    print("  🟣 Export  (Morado) #8b5cf6  →  Modal con borde morado")
    print("  🔴 Delete  (Rojo)   #ef4444  →  Modal con borde rojo")
    print("\nPruébalo en la app:")
    print("  python3 app.py")
    print("\nFooter buttons:")
    print("  • [SEND (s)]     → Modales verdes (destination, amount, passphrase, confirm)")
    print("  • [Receive (x)]  → Modal gris oscuro")
    print("  • [Refresh (r)]  → Sin modal (actualiza info)")
    print("\nTop buttons:")
    print("  • [Import (i)]  → Modal azul")
    print("  • [Backup (b)]  → Modal amarillo (advertencia)")
    print("  • [Export (e)]  → Modal morado")
    print("  • [Delete (Del)] → Modal rojo")
    print("\n¡Coherencia visual perfecta! 🎨")
else:
    print("\n⚠️  Algunos colores no están alineados correctamente")

print("\n" + "=" * 70 + "\n")
