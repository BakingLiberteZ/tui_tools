# 🥐 Bakery Messages Library

Sistema de mensajes dinámicos con tema de panadería para TUI Tezos Wallet.

## 📚 Filosofía de Diseño

La wallet usa metáforas consistentes de panadería para hacer la experiencia más divertida y memorable:

### 🔥 **OVEN (Horno)** = Procesando/Cocinando
Usar para operaciones **en curso**, cosas que se están **procesando**:
- Transacciones (preparando, amasando, horneando)
- Verificación de capacidades RPC (¿puede procesar transacciones?)
- Bakers esperando procesar

### 🪟 **DISPLAY/SHELF (Vitrina/Estante)** = Ya Listo/Terminado
Usar para datos **completados**, cosas **listas para mostrar**:
- Historial de transacciones (pastries ya horneados)
- Balance actual (pastries en vitrina)
- Refresh de información (limpiar/actualizar la vitrina)

---

## 📁 Estructura del Archivo

```python
# bakery_messages.py

# Categorías de mensajes (listas de strings):
RPC_OVEN_HOT = [...]          # RPC puede procesar + simular
RPC_OVEN_WARM = [...]         # RPC puede procesar pero no simular
RPC_DISPLAY_ONLY = [...]      # RPC solo lectura
RPC_CHECKING = [...]          # Verificando RPC

TX_PREPARING = [...]          # Preparando transacción
TX_KNEADING = [...]           # Amasando (preparación avanzada)
TX_INTO_OVEN = [...]          # Enviando transacción
TX_BAKING = [...]             # En proceso de confirmación
TX_DONE = [...]               # Transacción completada

REFRESH_CHECKING = [...]      # Cargando historial/balance
REFRESH_SUCCESS = [...]       # Refresh completado

SPINNER_MESSAGES = [...]      # Mensajes de loading genéricos

IMPORT_SECRET_KEY = [...]     # Import con clave privada
IMPORT_WATCH_ONLY = [...]     # Import watch-only
IMPORT_FROM_BACKUP = [...]    # Import desde backup
IMPORT_CANCELLED = [...]      # Import cancelado

BACKUP_SUCCESS = [...]        # Backup exitoso
DELETE_SUCCESS = [...]        # Wallet eliminado
```

---

## 🔧 Uso

### Función Principal: `get_message()`

```python
from bakery_messages import get_message

# Sin parámetros
msg = get_message("rpc_hot")
# Devuelve un mensaje aleatorio de RPC_OVEN_HOT

# Con parámetros (para interpolación)
msg = get_message("import_secret", name="My Wallet")
# Devuelve: "🎉 New pastry 'My Wallet' fresh from the oven! ..."

# Contextos disponibles:
contexts = [
    "rpc_hot", "rpc_warm", "rpc_display", "rpc_checking",
    "tx_preparing", "tx_kneading", "tx_into_oven", "tx_baking", "tx_done",
    "refresh_checking", "refresh_success",
    "spinner",
    "import_secret", "import_watch", "import_backup", "import_cancel",
    "backup_success", "delete_success"
]
```

### Ejemplos de Integración

```python
# En app.py:

# RPC check
if can_send and can_sim:
    msg = get_message("rpc_hot")
elif can_send:
    msg = get_message("rpc_warm")
else:
    msg = get_message("rpc_display")

# Transacción
self._set_status(get_message("tx_preparing"))
# ... luego ...
self._set_status(get_message("tx_baking"))
# ... finalmente ...
self._set_status(get_message("tx_done"))

# Refresh
self._set_status(get_message("refresh_checking"))
# ... después de cargar ...
self._set_status(get_message("refresh_success"))

# Import con nombre
success_msg = get_message("import_secret", name=wallet_name)
self._set_status(f"✓ {success_msg}")
```

---

## ➕ Cómo Agregar Nuevos Mensajes

### 1. Agregar a una lista existente

```python
# En bakery_messages.py

RPC_OVEN_HOT = [
    "🔥 RPC oven is hot and ready! ...",
    "🔥 Oven preheated to perfection! ...",
    # ✨ AGREGAR AQUÍ TU NUEVO MENSAJE:
    "🔥 Tu nuevo mensaje divertido aquí! 🥐",
]
```

### 2. Crear una nueva categoría

```python
# En bakery_messages.py

# Nueva lista
NETWORK_SWITCH = [
    "🌐 Switching networks! Changing ovens! 🔥",
    "🔄 New network, new bakery! 🥖",
    "🌍 Network swap! Different flour! 🌾",
]

# Agregar al diccionario en get_message()
messages_map = {
    # ... existing ...
    "network_switch": NETWORK_SWITCH,  # ← NUEVO
}
```

### 3. Agregar tipo al Literal (para type hints)

```python
MessageContext = Literal[
    "rpc_hot", "rpc_warm", # ... etc
    "network_switch",  # ← NUEVO
]
```

---

## 🎨 Guías de Estilo

### ✅ Buenos mensajes:

1. **Cortos y divertidos** (no muy largos)
   ```python
   ✅ "🔥 Oven's fired up! Bakers ready! 👨‍🍳"
   ❌ "🔥 The oven has been successfully fired up and all the bakers are now standing by their stations ready to begin processing your transactions with great enthusiasm..."
   ```

2. **Temáticamente consistentes**
   ```python
   ✅ "🥖 Kneading the dough..."  # (para TX en proceso)
   ❌ "🚀 Launching rockets..."    # (no es tema de panadería)
   ```

3. **Incluyen emojis relevantes**
   ```python
   ✅ "🍞 Fresh bread on display! 🪟"
   ❌ "Fresh bread on display"  # (sin emojis es aburrido)
   ```

4. **Mantienen la metáfora correcta**
   ```python
   # Para refresh (datos terminados):
   ✅ "🪟 Display shelf refreshed!"      # CORRECTO (vitrina)
   ❌ "🔥 Oven refreshed!"               # INCORRECTO (oven = procesando)

   # Para transacción (procesando):
   ✅ "🔥 Into the oven!"                # CORRECTO (cocinando)
   ❌ "🪟 Into the display!"             # INCORRECTO (display = terminado)
   ```

5. **Personalidad y tono divertido**
   ```python
   ✅ "🔥 Bakers waiting to process any pastry you throw at 'em, baby! 🥐"
   ❌ "RPC is functional and ready to process transactions."
   ```

---

## 🧪 Testing

```bash
# Test el módulo directamente
python3 bakery_messages.py

# Output esperado:
🥖 Bakery Messages Library Test

rpc_hot:
  🔥 [mensaje aleatorio de RPC_OVEN_HOT]

tx_baking:
  ⏰ [mensaje aleatorio de TX_BAKING]

# etc...
```

---

## 📊 Estadísticas Actuales

| Categoría | Cantidad | Ejemplo |
|-----------|----------|---------|
| RPC Hot | 10 | "🔥 Oven blazing! Bakers ready! 🥖🔥" |
| RPC Warm | 7 | "⚡ Warm oven, no preview! 🥖" |
| RPC Display | 7 | "🪟 Glass case mode! Look, don't touch! 🥐" |
| RPC Checking | 7 | "🔍 Checking oven temperature…" |
| TX Preparing | 7 | "🥖 Preparing your dough…" |
| TX Kneading | 7 | "💪 Kneading with love…" |
| TX Into Oven | 7 | "🔥 Sliding into the oven…" |
| TX Baking | 8 | "⏰ Baking in progress…" |
| TX Done | 8 | "✨ Baked to perfection! 🥐" |
| Refresh Check | 8 | "🪟 Checking the display shelf…" |
| Refresh Success | 8 | "✨ Display shelf refreshed! 🥐" |
| Spinner | 35 | "Rolling croissants... 🥐" |
| Import Secret | 7 | "🎉 New pastry fresh from oven! 🥐" |
| Import Watch | 6 | "👁️ Display pastry in showcase! 🪟" |
| Import Backup | 6 | "📦 Vintage pastry restored! ✨" |
| Import Cancel | 5 | "↩️ No dough, no bread! 🍞" |
| Backup Success | 6 | "✓ 📦 Recipe saved! 🥖" |
| Delete Success | 7 | "✓ 🔥 Burned like toast! 🍞💨" |
| **TOTAL** | **150+** | 150+ mensajes únicos! |

---

## 🎯 Roadmap Futuro

### Ideas para nuevas categorías:

- [ ] **Network Switch**: Mensajes para cambiar de Mainnet ↔ Ghostnet
- [ ] **Delegation**: Mensajes para delegar a un baker
- [ ] **Staking**: Mensajes para operaciones de staking
- [ ] **Error Recovery**: Mensajes divertidos para errores recuperables
- [ ] **Idle Messages**: Mensajes cuando no hay actividad
- [ ] **Achievement Messages**: Celebraciones por hitos (primera tx, 100 XTZ, etc.)

### Mejoras técnicas:

- [ ] Soporte para mensajes multi-línea
- [ ] Mensajes con variables dinámicas más complejas
- [ ] Prioridades de mensajes (algunos más frecuentes que otros)
- [ ] Mensajes estacionales (Halloween, Navidad, etc.)

---

## 🤝 Contribuir

¿Tienes ideas para mensajes divertidos? ¡Agrégalos!

1. Mantén el tema de panadería
2. Usa la metáfora correcta (oven vs display)
3. Incluye emojis relevantes
4. Mantén el tono divertido pero profesional
5. Prueba que funcione: `python3 bakery_messages.py`

---

**Mantenido por**: TUI Tezos Wallet Team
**Última actualización**: 2026-01-21
**Versión**: 1.3.0

🥐 Happy Baking!
