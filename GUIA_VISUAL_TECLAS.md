# 👀 GUÍA VISUAL - Dónde Mirar las Nuevas Teclas

## 🎯 PROBLEMA IDENTIFICADO

Las nuevas teclas **SÍ están funcionando**, pero son **"hidden"** (ocultas).
NO aparecen en el footer, pero **SÍ funcionan cuando las presionas**.

---

## 📺 LAYOUT DE LA PANTALLA

```
┌────────────────────────────────────────────────────────────────┐
│                        LOGO ASCII                               │
│                                                                 │
├────────────────────┬───────────────────────────────────────────┤
│  ACCOUNTS:         │  Wallet Details                           │
│  ┌──────────────┐  │  ┌─────────────────────────────────────┐ │
│  │ Test         │  │  │ Balance: 1,234.567 XTZ              │ │
│  │ My Wallet    │  │  │ Staking: 100 XTZ                    │ │ <- AQUÍ ves formato
│  └──────────────┘  │  │ Network: ghostnet                   │ │
│                    │  └─────────────────────────────────────┘ │
│  [Import Wallet]   │                                           │
├────────────────────┴───────────────────────────────────────────┤
│  Recent Transactions                                           │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │    5 min ago  OUT  -1,234.56 XTZ  ↔  tz1abc...          │ │ <- AQUÍ ves tiempo relativo
│  │   2 hours ago  IN  +500.00 XTZ  ↔  tz2def...            │ │
│  └──────────────────────────────────────────────────────────┘ │
├────────────────────────────────────────────────────────────────┤
│ ⚡ Status: Ready                                               │ <- AQUÍ aparecen mensajes
└────────────────────────────────────────────────────────────────┘
│ i Import | r Refresh | s Send | x Receive | n Network | q Quit│ <- Footer (teclas visibles)
└────────────────────────────────────────────────────────────────┘
```

---

## 🎹 CÓMO PROBAR CADA TECLA

### 1. TECLA 'b' (BACKUP)

**Pasos**:
```bash
1. Ejecuta: python3 app.py
2. Presiona: b (solo 'b', minúscula)
3. Mira la BARRA DE ESTADO (línea inferior, donde dice "⚡ Status")
4. Deberías ver: "✅ Backup created: wallet_backup_XXXXXXXX.json (X.X KB)"
```

**Verificación**:
```bash
# En otra terminal:
ls data/backups/
```

**Si no lo ves**: El mensaje dura ~3 segundos. Presiona 'b' de nuevo y mira RÁPIDO la barra de estado.

---

### 2. TECLA 'a' (SHOW ADDRESS)

**Pasos**:
```bash
1. Ejecuta: python3 app.py
2. SELECCIONA UNA WALLET (flechas arriba/abajo o click)
3. Presiona: a
4. Debe aparecer un MODAL en el centro de la pantalla
```

**El modal se ve así**:
```
┌─ Wallet Address Details ─────────────────────┐
│                                               │
│  Wallet name: My Wallet                      │
│                                               │
│  ┌─────────────────────────────────────────┐ │
│  │ tz1iyEws6cNvKTy42qE6SfKMPfwqUWL8BdmL  │ │
│  └─────────────────────────────────────────┘ │
│                                               │
│      [Copy to Clipboard]  [Close]            │
└───────────────────────────────────────────────┘
```

**Si no aparece**: Asegúrate de tener una wallet SELECCIONADA (resaltada en azul).

---

### 3. TECLA 'e' (EXPORT CSV)

**Pasos**:
```bash
1. Ejecuta: python3 app.py
2. SELECCIONA UNA WALLET que tenga transacciones
3. Presiona: e
4. Mira la BARRA DE ESTADO
5. Verás: "✅ Exported X transaction(s) to ..." o "ℹ️ No transaction history"
```

**Verificación**:
```bash
# En otra terminal:
ls data/exports/
```

---

### 4. TECLA 'Delete' (ELIMINAR WALLET)

**Pasos**:
```bash
1. Ejecuta: python3 app.py
2. SELECCIONA UNA WALLET
3. Presiona: Delete (o Supr)
4. Debe aparecer MODAL DE CONFIRMACIÓN (fondo amarillo/rojo)
```

**El modal se ve así**:
```
┌─ Delete Wallet ──────────────────────────────┐
│                                               │
│  Are you sure you want to delete wallet      │
│  'My Wallet'?                                │
│                                               │
│  Address: tz1abc...xyz                        │
│                                               │
│  ⚠️ This action cannot be undone!            │
│  (The wallet will only be removed from       │
│   this app, not from the blockchain)         │
│                                               │
│      [Yes]  [No]                             │
└───────────────────────────────────────────────┘
```

**IMPORTANTE**: Puedes cancelar con ESC o clickeando "No".

---

### 5. TECLA 'Ctrl+R' (AUTO-REFRESH)

**Pasos**:
```bash
1. Ejecuta: python3 app.py
2. Presiona: Ctrl+R (mantén Ctrl y presiona R)
3. Mira la BARRA DE ESTADO
4. Verás: "✅ Auto-refresh enabled (every 60s)"
5. Presiona Ctrl+R de nuevo para desactivar
6. Verás: "🛑 Auto-refresh disabled"
```

---

## 🔍 DEBUGGING: Ver los Logs en Tiempo Real

Abre **dos terminales**:

**Terminal 1** (ejecuta la app):
```bash
cd /home/slimbook/tui-tezos-wallet
python3 app.py
```

**Terminal 2** (ve los logs):
```bash
cd /home/slimbook/tui-tezos-wallet
tail -f logs/wallet.log
```

Ahora presiona las teclas en Terminal 1 y observa los logs en Terminal 2:

- Presionas 'b' → verás: `INFO - Created backup: data/backups/...`
- Presionas 'a' → verás actividad de UI
- Presionas 'e' → verás: `INFO - Exported history to CSV: ...`
- Presionas Delete → verás: `INFO - Deleted wallet: ...` (si confirmas)

---

## ✅ CHECKLIST DE VERIFICACIÓN

Haz esto **EN LA APP** (python3 app.py):

**Paso 1**: Formato de números
```
[ ] Mira "Balance:" - ¿tiene comas? (ej: 1,234.567)
[ ] Mira transacciones - ¿tienen comas?
```

**Paso 2**: Tiempo relativo
```
[ ] Mira lista de transacciones (izquierda abajo)
[ ] Primera columna - ¿dice "X min ago"?
```

**Paso 3**: Tecla 'b' (backup)
```
[ ] Presiona 'b'
[ ] Mira barra de estado (abajo) - ¿apareció mensaje?
[ ] Ejecuta en terminal: ls data/backups/
[ ] ¿Hay archivos?
```

**Paso 4**: Tecla 'a' (address)
```
[ ] Selecciona una wallet
[ ] Presiona 'a'
[ ] ¿Apareció modal con dirección completa?
```

**Paso 5**: Tecla 'e' (export)
```
[ ] Selecciona wallet con transacciones
[ ] Presiona 'e'
[ ] Mira barra de estado - ¿mensaje de export?
[ ] Ejecuta: ls data/exports/
[ ] ¿Hay archivos CSV?
```

---

## 🆘 SOLUCIÓN DE PROBLEMAS

### "Presiono 'b' pero no pasa nada"

**Solución**:
1. El mensaje aparece en la BARRA DE ESTADO (abajo) y dura poco
2. Abre otra terminal y ejecuta: `tail -f logs/wallet.log`
3. Presiona 'b' de nuevo
4. Mira el log - deberías ver: "Created backup: ..."

### "No veo el modal cuando presiono 'a'"

**Solución**:
1. Asegúrate de tener una wallet SELECCIONADA (debe estar resaltada)
2. Si no hay wallets, presiona 'i' para importar una primero

### "La tecla 'e' dice 'No transaction history'"

**Solución**:
- Normal si la wallet no tiene transacciones
- Prueba con una wallet que tenga historial
- O presiona 's' para hacer una transacción primero

### "La tecla Delete no funciona"

**Solución**:
1. Verifica que tu teclado tenga tecla "Delete" o "Supr"
2. Algunos teclados tienen "Del" en lugar de "Delete"
3. Intenta: Fn+Backspace (en algunos laptops)

---

## 📹 DEMOSTRACIÓN RÁPIDA

Ejecuta esto para ver que TODO funciona:

```bash
# Terminal 1
cd /home/slimbook/tui-tezos-wallet

# Crea un backup (sin GUI)
python3 /tmp/test_backup_direct.py

# Verifica que se creó
ls -lh data/backups/

# Ahora ejecuta la app y prueba las teclas
python3 app.py
```

---

## ✅ CONFIRMACIÓN FINAL

Si ejecutas:
```bash
python3 test_keybindings.py
```

Y ves TODO en ✅, entonces las funciones ESTÁN AHÍ.

Solo necesitas:
1. Ejecutar la app: `python3 app.py`
2. Tener una wallet seleccionada
3. Presionar las teclas
4. Mirar la **BARRA DE ESTADO** (no el footer)

Las teclas son "ocultas" por diseño - no saturan el footer, pero funcionan perfectamente.
