# 👀 DÓNDE VER LOS CAMBIOS - Guía Visual

## ✅ CONFIRMADO: Todos los cambios están en app.py

El script `verify_upgrades.py` confirma que **todos los 14 upgrades están implementados**.

---

## 🔍 CÓMO VERIFICAR QUE FUNCIONAN

### 1. 💰 Números Formateados (MÁS VISIBLE)

**Dónde mirar**: Panel superior derecho, donde dice "Balance:"

```
ANTES:  Balance: 1234.567000 XTZ
AHORA:  Balance: 1,234.567 XTZ
```

También en:
- Staking: `Staking: 500 XTZ` (sin zeros al final)
- Historial de transacciones: `+12,345.678 XTZ`
- Pantalla de confirmación de envío

**Cómo probarlo**:
1. Ejecuta: `python3 app.py`
2. Selecciona una wallet (flechas arriba/abajo o click)
3. Mira el panel "Balance:" en la parte superior

---

### 2. 🕒 Tiempo Relativo en Historial

**Dónde mirar**: Lista de transacciones (panel inferior izquierdo)

```
ANTES:  2026-01-21 16:04  OUT  -1.5 XTZ  ↔  tz1abc...
AHORA:       5 min ago  OUT  -1.5 XTZ  ↔  tz1abc...
```

**Cómo probarlo**:
1. Selecciona una wallet que tenga transacciones
2. Mira la primera columna del historial
3. Deberías ver "X min ago", "X hr ago", etc.

⚠️ **NOTA**: El tiempo relativo está en el HISTORIAL (lista), no en el panel de detalles

---

### 3. 🎹 Nuevas Teclas

**Cómo probar cada una**:

#### Delete - Eliminar Wallet
```bash
1. Selecciona una wallet
2. Presiona: Delete (Supr)
3. Aparece modal de confirmación
4. Puedes cancelar con "No" o ESC
```

#### b - Backup
```bash
1. Presiona: b
2. Mensaje en status bar: "✅ Backup created: wallet_backup_*.json"
3. Verifica: ls data/backups/
```

#### a - Ver Dirección Completa
```bash
1. Selecciona una wallet
2. Presiona: a
3. Aparece modal con dirección completa
```

#### e - Export CSV
```bash
1. Selecciona una wallet con transacciones
2. Presiona: e
3. Mensaje: "✅ Exported X transaction(s)..."
4. Verifica: ls data/exports/
```

#### Ctrl+R - Auto-refresh
```bash
1. Presiona: Ctrl+R
2. Mensaje: "✅ Auto-refresh enabled (every 60s)"
3. Presiona de nuevo para desactivar
```

---

### 4. ✅ Validación de Balance

**Cómo probarlo**:
1. Presiona: s (send)
2. Ingresa dirección destino
3. Ingresa un monto MAYOR a tu balance
4. Mensaje de error: "❌ Insufficient balance. Have: X XTZ, Need: ~Y XTZ"

---

### 5. 📝 Logging

**Cómo verificarlo**:
```bash
# Ver logs en tiempo real
tail -f logs/wallet.log

# O ver el archivo completo
cat logs/wallet.log
```

Deberías ver:
```
2026-01-21 16:04:28 - root - INFO - TUI Tezos Wallet started
2026-01-21 16:04:28 - root - INFO - Loaded 2 account(s)
```

---

### 6. ⏱️ Tiempo Transcurrido en Operaciones

**Cómo verlo**:
1. Presiona: r (refresh)
2. Si tarda más de 5 segundos, verás: "⏳ Checking... (⏱️ 6s)"

---

### 7. 💾 Caché de Balance (invisible pero funciona)

**Cómo probarlo**:
1. Abre terminal y ejecuta: `tail -f logs/wallet.log`
2. En la app, presiona: r (refresh) dos veces seguidas
3. En el log verás:
   - Primera vez: "Fetching balance for..."
   - Segunda vez (dentro de 30s): "Using cached balance for..."

---

## 🚨 SI NO VES LOS CAMBIOS

### Paso 1: Limpia caché y reinicia
```bash
# Cierra la app completamente (q o Ctrl+C)
rm -rf __pycache__ wallet/__pycache__
python3 app.py
```

### Paso 2: Verifica que estés en el directorio correcto
```bash
pwd
# Debe mostrar: /home/slimbook/tui-tezos-wallet

ls app.py
# Debe existir
```

### Paso 3: Ejecuta el verificador
```bash
python3 verify_upgrades.py
```

Debe mostrar ✅ en todo.

### Paso 4: Verifica el tamaño del archivo
```bash
wc -l app.py
```

Debe mostrar aproximadamente **2800-3000 líneas** (antes tenía ~1500).

### Paso 5: Busca una función nueva
```bash
grep "def action_backup" app.py
```

Debe encontrar la función.

---

## 📸 CAPTURA DE PANTALLA DE REFERENCIA

Cuando ejecutes `python3 app.py` deberías ver:

1. **Logo ASCII** al inicio (igual que antes)
2. **Balance formateado**: `1,234.567 XTZ` (con comas)
3. **Historial con tiempo relativo**: `5 min ago` en lugar de timestamp
4. **Footer con shortcuts**: `i r s x n q` (los de siempre)

Las nuevas funciones están en **shortcuts ocultos** (no aparecen en footer pero funcionan):
- Delete, b, a, e, Ctrl+R

---

## 🆘 ÚLTIMA OPCIÓN: Verifica el archivo manualmente

```bash
# Busca la clase Config
grep -n "class Config:" app.py
# Debe mostrar: 36:class Config:

# Busca format_xtz
grep -n "def format_xtz" app.py
# Debe mostrar: 167:def format_xtz(amount: Decimal) -> str:

# Cuenta cuántas veces se usa format_xtz
grep -c "format_xtz" app.py
# Debe mostrar: 18 o más

# Busca action_backup
grep -n "def action_backup" app.py
# Debe mostrar: 2461:    def action_backup(self) -> None:
```

Si TODOS estos comandos dan resultados positivos, **los cambios están ahí**.

---

## 💡 TIPS

1. **Los cambios más visibles** son el formato de números y el tiempo relativo
2. **Si no ves tiempo relativo**, asegúrate de que tu wallet tenga transacciones recientes
3. **Los shortcuts nuevos** funcionan incluso si no aparecen en el footer
4. **El logging** funciona en background, revisa `logs/wallet.log`

---

## ✅ CHECKLIST VISUAL

Marca lo que ves:

- [ ] Balance con comas: `1,234.567 XTZ`
- [ ] Historial con "X min ago"
- [ ] Presionar 'b' crea backup
- [ ] Presionar 'a' muestra modal de dirección
- [ ] Presionar 'e' exporta CSV
- [ ] logs/wallet.log existe y tiene contenido
- [ ] data/backups/ se crea al presionar 'b'
- [ ] data/exports/ se crea al presionar 'e'

Si marcas al menos 5 de 8, **los cambios están funcionando**.

---

**¿Sigues sin ver los cambios?** Comparte:
1. La salida de: `python3 verify_upgrades.py`
2. La salida de: `wc -l app.py`
3. Una captura de lo que ves al ejecutar la app
