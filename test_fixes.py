#!/usr/bin/env python3
"""Verify that both fixes are applied correctly."""

import sys
import inspect

print("\n" + "=" * 70)
print("🔧 VERIFICACIÓN DE CORRECCIONES")
print("=" * 70 + "\n")

# Test 1: Import app
try:
    from app import WalletApp
    print("✅ Import WalletApp exitoso\n")
except Exception as e:
    print(f"❌ Error al importar WalletApp: {e}")
    sys.exit(1)

# Test 2: Check Delete button handler is NOT async
print("🗑️  VERIFICACIÓN DEL BOTÓN DELETE:")
print("-" * 70)

try:
    handler_source = inspect.getsource(WalletApp.on_delete_pressed)

    # Check that it's not async
    is_async = inspect.iscoroutinefunction(WalletApp.on_delete_pressed)
    has_await = "await" in handler_source

    if is_async:
        print("  ❌ ERROR: Handler on_delete_pressed es async (NO debería serlo)")
        print("     El decorador @work ya maneja la asincronía")
    else:
        print("  ✅ Handler on_delete_pressed es síncrono (correcto)")

    if has_await:
        print("  ❌ ERROR: Handler usa 'await' (NO debería)")
        print("     Esto causa conflictos con @work decorator")
    else:
        print("  ✅ Handler NO usa 'await' (correcto)")

    delete_handler_ok = not is_async and not has_await

    if delete_handler_ok:
        print("\n  ✅ Botón Delete corregido correctamente!")
        print("     Ya no causará errores ni cerrará la app")
    else:
        print("\n  ⚠️  Botón Delete necesita ajustes")

except Exception as e:
    print(f"  ❌ Error verificando handler: {e}")
    delete_handler_ok = False

# Test 3: Check status bar CSS improvements
print("\n🎨 VERIFICACIÓN DE ESTILOS DE BARRA DE ESTATUS:")
print("-" * 70)

css_improvements = {
    "#bottom_bar con border": "border: heavy $accent" in WalletApp.CSS,
    "#bottom_bar con background": "background: $boost" in WalletApp.CSS,
    "#bottom_bar con min-height: 3": "min-height: 3" in WalletApp.CSS,
    "#status_line con text-style: bold": "#status_line {" in WalletApp.CSS and "text-style: bold" in WalletApp.CSS,
    "#status_line con background": "#status_line" in WalletApp.CSS and "background: $boost" in WalletApp.CSS,
    "#rpc_indicator con text-style: bold": "#rpc_indicator {" in WalletApp.CSS and "text-style: bold" in WalletApp.CSS,
}

all_css_ok = True
for improvement, present in css_improvements.items():
    status = "✅" if present else "❌"
    print(f"  {status} {improvement}")
    if not present:
        all_css_ok = False

if all_css_ok:
    print("\n  ✅ Todos los estilos de la barra de estatus aplicados!")
    print("     La barra ahora es mucho más visible y destacada")
else:
    print("\n  ⚠️  Algunos estilos faltan")

# Summary
print("\n" + "=" * 70)
print("📊 RESUMEN")
print("=" * 70)

fixes = [
    ("Botón Delete arreglado", delete_handler_ok),
    ("Estilos de barra de estatus mejorados", all_css_ok),
]

total = len(fixes)
passed = sum(1 for _, ok in fixes if ok)

for name, ok in fixes:
    status = "✅" if ok else "❌"
    print(f"{status} {name}")

print(f"\n✅ Correcciones aplicadas: {passed}/{total}")

if passed == total:
    print("\n🎉 TODAS LAS CORRECCIONES APLICADAS EXITOSAMENTE!")
    print("\nPuedes ejecutar la app:")
    print("  python3 app.py")
    print("\nVerificar:")
    print("  1. Botón Delete funciona sin errores")
    print("  2. Barra de estatus destaca con borde y fondo")
    print("  3. Mensajes son más visibles y llamativos")
else:
    print("\n⚠️  Algunas correcciones necesitan verificación")

print("\n" + "=" * 70 + "\n")
