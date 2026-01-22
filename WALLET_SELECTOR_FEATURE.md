# 🎯 Nueva Función: Selector de Wallets para Backup y Export

## ✨ Qué se Agregó

Se agregó un **modal de selección de wallets** que permite elegir específicamente qué wallet quieres respaldar o exportar, similar al funcionamiento del botón Delete.

---

## 🔄 Cambios en el Comportamiento

### ANTES:
- **Backup**: Hacía backup de TODAS las wallets en un solo archivo
- **Export**: Solo exportaba la wallet actualmente seleccionada en la lista

### AHORA:
- **Backup**: Muestra modal para elegir UNA wallet → Crea backup de solo esa wallet
- **Export**: Muestra modal para elegir UNA wallet → Exporta transacciones de solo esa wallet

---

## 🆕 Nueva Clase: WalletSelectorScreen

Modal reutilizable que muestra lista de wallets disponibles y permite seleccionar una.

**Ubicación**: Línea ~665 en app.py

**Características**:
- Lista todas las wallets disponibles
- Muestra nombre completo y dirección acortada
- Indica si es wallet "watch-only" (solo lectura)
- Navegable con teclado (flechas, Enter)
- Clickeable con mouse
- Cancelable con ESC o botón Cancel

**Ejemplo visual del modal**:
```
┌─ Select Wallet ─────────────────────────────────────┐
│ Choose a wallet:                                     │
│                                                      │
│ ┌──────────────────────────────────────────────┐   │
│ │ My Wallet                                    │   │
│ │ tz1abc…xyz                                   │   │
│ ├──────────────────────────────────────────────┤   │
│ │ Test Account                                 │   │
│ │ tz2def…123                                   │   │
│ ├──────────────────────────────────────────────┤   │
│ │ Work Wallet (watch)                          │   │
│ │ tz3ghi…456                                   │   │
│ └──────────────────────────────────────────────┘   │
│                                                      │
│           [Select]  [Cancel]                         │
└──────────────────────────────────────────────────────┘
```

---

## 💾 Backup - Nueva Funcionalidad

### Cómo Funciona Ahora:

1. **Click en botón "Backup (b)"** o presiona tecla **b**
2. **Modal aparece** con lista de todas tus wallets
3. **Selecciona una wallet** (con flechas o click)
4. **Click en "Select"** o presiona Enter
5. **Backup creado** solo de esa wallet

### Archivo de Backup Generado:

**Nombre**: `wallet_[nombre]_[timestamp].json`

**Ejemplo**: `wallet_My_Wallet_20260121_154530.json`

**Contenido del backup**:
```json
{
  "backup_timestamp": "20260121_154530",
  "backup_type": "single_wallet",
  "wallet": {
    "name": "My Wallet",
    "address": "tz1abc...xyz",
    "enc": "encrypted_private_key_data...",
    ...
  },
  "recent_destinations": [
    "tz2def...123",
    "tz3ghi...456"
  ]
}
```

**Ventajas**:
- ✅ Backup específico de una sola wallet
- ✅ Archivos más pequeños y manejables
- ✅ Fácil de restaurar wallet individual
- ✅ Nombre de archivo descriptivo

**Ubicación**: `data/backups/wallet_[nombre]_[timestamp].json`

---

## 📊 Export - Nueva Funcionalidad

### Cómo Funciona Ahora:

1. **Click en botón "Export (e)"** o presiona tecla **e**
2. **Modal aparece** con lista de todas tus wallets
3. **Selecciona una wallet** (con flechas o click)
4. **Click en "Select"** o presiona Enter
5. **Carga historial** de transacciones de esa wallet
6. **CSV exportado** con todas las transacciones

### Archivo CSV Generado:

**Nombre**: `transactions_[nombre]_[timestamp].csv`

**Ejemplo**: `transactions_My_Wallet_20260121_154530.csv`

**Contenido**:
```csv
Timestamp,Direction,Amount (XTZ),Counterparty,Hash,Wallet Name,Wallet Address
2026-01-21T15:45:30Z,OUT,-1.5,tz2def...123,ophash1...,My Wallet,tz1abc...xyz
2026-01-20T10:30:00Z,IN,+500.0,tz3ghi...456,ophash2...,My Wallet,tz1abc...xyz
```

**Ventajas**:
- ✅ Ya no necesitas tener la wallet seleccionada primero
- ✅ Puedes exportar cualquier wallet sin cambiar selección
- ✅ Carga hasta 100 transacciones recientes
- ✅ Proceso más rápido y directo

**Ubicación**: `data/exports/transactions_[nombre]_[timestamp].csv`

---

## 🎮 Cómo Usar

### Opción 1: Con Botones

```
[Import (i)] [Backup (b)] [Export (e)] [Delete (Del)]
              ↑             ↑
              Click aquí    O aquí
```

### Opción 2: Con Teclado

- Presiona **b** → Modal de Backup
- Presiona **e** → Modal de Export

### Navegación en el Modal

- **↑/↓** o **Mouse**: Seleccionar wallet
- **Enter** o **Click en Select**: Confirmar
- **ESC** o **Click en Cancel**: Cancelar

---

## 🔧 Cambios Técnicos

### 1. Nueva Clase WalletSelectorScreen (línea ~665)

```python
class WalletSelectorScreen(ModalScreen[Optional["Account"]]):
    """Modal to select a wallet from available accounts."""

    # Muestra lista de wallets
    # Devuelve Account seleccionado o None si se cancela
```

**Métodos principales**:
- `compose()`: Construye la UI del modal
- `on_mount()`: Popula la lista de wallets
- `_get_selected_account()`: Obtiene wallet seleccionada
- `wallet_selected_with_enter()`: Handler para Enter
- `select_pressed()`: Handler para botón Select
- `cancel_pressed()`: Handler para botón Cancel

### 2. action_backup() Modificada (línea ~2605)

**Antes**:
```python
def action_backup(self) -> None:
    # Copiaba todo el archivo data/wallet.json
    shutil.copy2(source, backup_path)
```

**Ahora**:
```python
@work(exclusive=True)
async def action_backup(self) -> None:
    # Muestra modal de selección
    selected = await self.push_screen_wait(WalletSelectorScreen(...))

    # Crea backup de solo esa wallet
    backup_content = {
        "backup_type": "single_wallet",
        "wallet": wallet_data,
        ...
    }
```

### 3. action_export_history() Modificada (línea ~2542)

**Antes**:
```python
def action_export_history(self) -> None:
    # Usaba self.selected (wallet actualmente seleccionada)
    # Usaba self.history_items (historial ya cargado)
```

**Ahora**:
```python
@work(exclusive=True)
async def action_export_history(self) -> None:
    # Muestra modal de selección
    selected = await self.push_screen_wait(WalletSelectorScreen(...))

    # Carga historial fresh de esa wallet
    history = fetch_history(self.rpc, selected.address, limit=100)

    # Exporta a CSV
```

---

## 📋 Casos de Uso

### Caso 1: Backup de Wallet Específica

**Situación**: Tienes 5 wallets pero solo quieres respaldar tu wallet principal.

**Antes**:
- Backup incluía todas las 5 wallets
- Archivo grande con datos que no necesitas

**Ahora**:
1. Click en Backup
2. Selecciona tu wallet principal
3. Backup solo de esa wallet
4. Archivo pequeño y específico

### Caso 2: Export de Wallet Inactiva

**Situación**: Quieres exportar historial de una wallet que no tienes seleccionada.

**Antes**:
- Tenías que seleccionar la wallet primero
- Esperar a que cargue el historial
- Luego exportar

**Ahora**:
1. Click en Export
2. Selecciona cualquier wallet
3. Espera carga + export automático
4. Listo!

### Caso 3: Multiples Exports Rápidos

**Situación**: Necesitas exportar historiales de 3 wallets diferentes.

**Antes**:
- Seleccionar wallet 1 → Esperar → Exportar
- Seleccionar wallet 2 → Esperar → Exportar
- Seleccionar wallet 3 → Esperar → Exportar

**Ahora**:
- Export → Wallet 1 → Listo
- Export → Wallet 2 → Listo
- Export → Wallet 3 → Listo
(Sin cambiar selección en la lista principal!)

---

## 🧪 Cómo Probar

### Prueba Completa:

```bash
# Limpiar cache
rm -rf __pycache__ wallet/__pycache__

# Ejecutar app
python3 app.py
```

### Test de Backup:

1. Click en botón **Backup (b)** (verde)
2. ✅ Debe aparecer modal con lista de wallets
3. Selecciona una wallet con flechas o click
4. Click en **Select** o presiona Enter
5. ✅ Debe mostrar: `✅ Backup created: wallet_[nombre]_[timestamp].json`
6. Verifica: `ls data/backups/`
7. ✅ Debe existir el archivo de backup

### Test de Export:

1. Click en botón **Export (e)** (morado)
2. ✅ Debe aparecer modal con lista de wallets
3. Selecciona una wallet que tenga transacciones
4. Click en **Select** o presiona Enter
5. ✅ Debe mostrar: `⏳ Loading history for [nombre]...`
6. ✅ Luego: `✅ Exported X transaction(s) to transactions_[nombre]_[timestamp].csv`
7. Verifica: `ls data/exports/`
8. ✅ Debe existir el archivo CSV

### Test de Cancelación:

1. Click en Backup o Export
2. Modal aparece
3. Presiona **ESC** o click en **Cancel**
4. ✅ Debe mostrar: `Backup cancelled` o `Export cancelled`
5. ✅ No debe crear ningún archivo

---

## ✅ Ventajas del Nuevo Sistema

| Aspecto | Antes | Ahora |
|---------|-------|-------|
| **Backup** | Todo o nada | Wallet específica |
| **Tamaño archivo** | Grande | Pequeño y manejable |
| **Export** | Solo wallet seleccionada | Cualquier wallet |
| **Flujo de trabajo** | Cambiar selección → Export | Direct: Export → Elegir |
| **Flexibilidad** | Baja | Alta |
| **Experiencia** | 2 pasos | 1 paso (modal incluido) |

---

## 📝 Archivos Generados

### Estructura de Directorios:

```
data/
├── wallet.json (archivo principal - sin cambios)
├── backups/
│   ├── wallet_My_Wallet_20260121_154530.json
│   ├── wallet_Test_Account_20260121_155000.json
│   └── wallet_Work_Wallet_20260121_160000.json
└── exports/
    ├── transactions_My_Wallet_20260121_154530.csv
    ├── transactions_Test_Account_20260121_155500.csv
    └── transactions_Work_Wallet_20260121_161000.csv
```

---

## 🎉 Resultado Final

**Consistencia**: Ahora los 3 botones principales (Delete, Backup, Export) funcionan igual:
1. Click en botón
2. Modal de selección aparece
3. Eliges wallet específica
4. Acción se ejecuta solo en esa wallet

**Intuitividad**: El flujo es predecible y consistente en toda la aplicación.

**Control**: El usuario tiene control granular sobre qué wallet respaldar o exportar.

---

## 🐛 Solución de Problemas

### Modal no aparece
- Verifica que tengas wallets configuradas
- Revisa logs: `tail -f logs/wallet.log`

### "No wallets available"
- Importa una wallet primero con botón Import

### Export dice "No transaction history"
- Normal si la wallet no tiene transacciones
- Prueba con otra wallet

### Backup falla
- Verifica permisos del directorio `data/backups/`
- Revisa espacio en disco

---

¡Todo listo! Ahora tienes control total sobre backups y exports de wallets individuales. 🎯
