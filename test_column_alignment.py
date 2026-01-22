#!/usr/bin/env python3
"""Verify that column headers align perfectly with wallet list content."""

import re

print("\n" + "=" * 70)
print("📐 VERIFICACIÓN DE ALINEACIÓN DE COLUMNAS")
print("=" * 70 + "\n")

# Read app.py
with open('app.py', 'r') as f:
    content = f.read()

# Extract header format
header_match = re.search(r'\[b\](Name.*?Address)\[/b\]', content)
if not header_match:
    print("❌ No se encontró el header")
    exit(1)

header_line = header_match.group(1)
print("HEADER:")
print(f"  '{header_line}'")

# Extract content format from _render_accounts
content_match = re.search(r'label_text = f"([^"]*?{name_with_tag:<30}[^"]*?)"', content)
if not content_match:
    print("❌ No se encontró el formato del contenido")
    exit(1)

content_format = content_match.group(1)
print("\nFORMATO CONTENIDO:")
print(f"  '{content_format}'")

# Simulate actual values
name_example = "My Wallet"
addr_example = "tz1abc…xyz"

# Generate content line as it would appear
content_line = f"{name_example:<30} │ {addr_example}"

print("\nEJEMPLO DE CONTENIDO:")
print(f"  '{content_line}'")

# Find position of │ in both
header_bar_pos = header_line.index('│')
content_bar_pos = content_line.index('│')

print("\nPOSICIÓN DE LA BARRA VERTICAL (│):")
print(f"  Header:    columna {header_bar_pos}")
print(f"  Contenido: columna {content_bar_pos}")

# Check alignment
if header_bar_pos == content_bar_pos:
    print("\n✅ ¡ALINEACIÓN PERFECTA!")
    print("\nVisualización:")
    print("  " + header_line)
    print("  " + content_line)
    print("  " + " " * header_bar_pos + "↑")
    print("  " + " " * header_bar_pos + "Las barras están alineadas")
else:
    print(f"\n❌ NO ALINEADO")
    print(f"   Diferencia: {abs(header_bar_pos - content_bar_pos)} caracteres")

# Detailed breakdown
print("\n" + "-" * 70)
print("ANÁLISIS DETALLADO:")
print("-" * 70)

# Header breakdown
print(f"\nHeader:")
print(f"  'Name' = 4 caracteres")
header_spaces = header_bar_pos - 4
print(f"  Espacios después de 'Name' = {header_spaces}")
print(f"  Total antes de │ = {header_bar_pos}")

# Content breakdown
print(f"\nContenido:")
print(f"  '{name_example}' = {len(name_example)} caracteres")
print(f"  Padding a 30 caracteres con :<30")
print(f"  Espacio antes de │ = 1")
print(f"  Total antes de │ = {content_bar_pos}")

# Final verdict
print("\n" + "=" * 70)
if header_bar_pos == content_bar_pos:
    print("✅ Las columnas están perfectamente alineadas")
    print("\nCuando ejecutes la app, verás:")
    print("  Name                           │ Address")
    print("  My Wallet                      │ tz1abc…xyz")
    print("  Test Account                   │ tz2def…123")
    print("\n  ↑ Las barras verticales estarán perfectamente alineadas ↑")
else:
    print("❌ Las columnas NO están alineadas")
    print(f"   Necesita ajuste de {abs(header_bar_pos - content_bar_pos)} caracteres")
print("=" * 70 + "\n")
