# 🚨 Empty Wallet Messages Library

Sistema de mensajes motivacionales y divertidos para cuando el usuario abre la app sin ninguna wallet importada.

---

## 📚 Filosofía de Diseño

La wallet usa mensajes **divertidos, irónicos y urgentes** para motivar al usuario a importar su primera wallet. Los mensajes buscan crear una sensación de "algo falta aquí" de manera humorística, sin ser agresivos ni molestos.

### 🚨 **EMPTY** = Sin Wallets Importadas

Para usuarios que acaban de abrir la app sin wallets configuradas:
- Mensajes divertidos y dramáticos
- Tono irónico pero amigable
- Referencias al bakery siendo vacío
- Llamado claro a la acción: "Press 'i' to import!"
- Color: **🟡 Amarillo / 🔴 Rojo** (urgencia pero amigable)
- Objetivo: **Motivar a importar la primera wallet de manera divertida**

---

## 📁 Estructura del Archivo

```python
# empty_wallet_messages.py

# Lista de mensajes para cuando no hay wallets
EMPTY_WALLET_MESSAGES = [...]  # 30 mensajes motivacionales
```

---

## 🔧 Uso

### Función Principal: `get_empty_wallet_message()`

```python
from empty_wallet_messages import get_empty_wallet_message

# Obtener un mensaje aleatorio
msg = get_empty_wallet_message()
# Devuelve: "🚨 Import a wallet for god sake! This bakery needs customers!"
```

### Ejemplo de Integración en app.py

```python
from empty_wallet_messages import get_empty_wallet_message

# Seleccionar mensaje una sola vez al inicializar la app
self._empty_wallet_message: str = get_empty_wallet_message()

# Mostrar en la lista de accounts cuando está vacía
if not self.accounts:
    lv.append(ListItem(Label(f"[yellow]{self._empty_wallet_message}[/yellow]", markup=True)))

# Mostrar en el panel de información de wallet
if not self.selected:
    self.query_one("#wallet_status", Static).update("Wallet: [red]🚨 NONE! Import one![/red]")
    self.query_one("#wallet_balance", Static).update(f"[yellow]{self._empty_wallet_message}[/yellow]")
    self.query_one("#wallet_delegation", Static).update("[dim]🏜️ This bakery is empty...[/dim]")
    self.query_one("#wallet_staking", Static).update("[red]😭 Press 'i' to import a wallet NOW![/red]")
```

---

## 📊 Estadísticas Actuales

| Categoría | Cantidad | Ejemplo | Color |
|-----------|----------|---------|-------|
| **EMPTY** (Sin wallets) | 30 | "🚨 Import a wallet for god sake! This bakery needs customers!" | 🟡🔴 Amarillo/Rojo |

---

## ➕ Cómo Agregar Nuevos Mensajes

### 1. Agregar a la lista

```python
# En empty_wallet_messages.py

EMPTY_WALLET_MESSAGES = [
    "🚨 Import a wallet for god sake! This bakery needs customers!",
    "😭 It's SO empty in here! Press 'i' to import and fill this void!",
    # ✨ AGREGAR AQUÍ TU NUEVO MENSAJE:
    "🎪 The circus needs performers! Import a wallet (press 'i')!",
]
```

### 2. Mantener el tono apropiado

**EMPTY (Divertido, irónico, urgente):**
```python
✅ "🚨 Import a wallet for god sake! This bakery needs customers!"
✅ "😭 It's SO empty in here! Press 'i' to import and fill this void!"
✅ "🤡 Running a wallet app with no wallets? That's some clown energy!"
❌ "You should import a wallet." (demasiado formal, aburrido)
❌ "IMPORT NOW OR ELSE!!!" (demasiado agresivo)
```

---

## 🎨 Guías de Estilo

### ✅ Buenos mensajes:

1. **Tienen humor e ironía**
   ```python
   ✅ "😂 You opened a wallet app... with NO wallets. Bold move!"
   ❌ "No wallets found. Please import one."
   ```

2. **Usan emojis relevantes**
   ```python
   ✅ "🏜️ Tumbleweed rolling by... Import a wallet, please! Press 'i'!"
   ❌ "Tumbleweed rolling by... Import a wallet, please! Press 'i'!" (sin emoji)
   ```

3. **Incluyen llamado claro a la acción**
   ```python
   ✅ "🚫 ERROR 404: Wallets not found. Press 'i' to fix this tragedy!"
   ❌ "ERROR 404: Wallets not found." (sin CTA)
   ```

4. **Son cortos y directos**
   ```python
   ✅ "🦗 *Cricket sounds* ... Import a wallet? Maybe? Press 'i'?"
   ❌ "Currently, the application has detected that you have not yet configured any wallets in the system. To begin using the application's features, you should consider importing a wallet by pressing the 'i' key..."
   ```

5. **Mantienen tono de bakery vacío**
   ```python
   ✅ "🏚️ Empty shelves, empty dreams. Import a wallet to start baking!"
   ✅ "📦 This box is EMPTY! Time to unpack some wallets! Press 'i'!"
   ✅ "🎭 The show can't start without actors! Import a wallet (press 'i')!"
   ```

---

## 🧪 Testing

```bash
# Test el módulo directamente
python3 empty_wallet_messages.py

# Output esperado:
🚨 Empty Wallet Messages Library Test

SAMPLE MESSAGES (5 random):
  1. [mensaje aleatorio 1]
  2. [mensaje aleatorio 2]
  3. [mensaje aleatorio 3]
  4. [mensaje aleatorio 4]
  5. [mensaje aleatorio 5]

📊 Statistics:
  Total messages: 30

💡 Tip: All messages encourage pressing 'i' to import a wallet!
```

---

## 🎯 Impacto y Objetivos

### Objetivos de UX:
1. **Guiar al usuario** hacia la acción correcta de manera divertida
2. **Crear engagement** desde el primer momento con humor
3. **Evitar intimidación** - los mensajes son graciosos, no amenazantes
4. **Claridad** - siempre dicen "Press 'i' to import"

### Métricas de éxito:
- ✅ Mensaje visible inmediatamente al abrir app sin wallets
- ✅ Mensaje seleccionado una sola vez (consistente durante la sesión)
- ✅ Tono apropiado: divertido pero claro
- ✅ Usuarios sonríen y saben qué hacer (feedback cualitativo)

### Por qué funciona:
- 😄 **Humor**: Hace la experiencia memorable desde el inicio
- 🎯 **CTA claro**: Siempre indica "Press 'i'"
- 🎭 **Personalidad**: La app tiene carácter desde el primer momento
- 🏜️ **Metáfora visual**: "Bakery vacío" refuerza el tema general
- 🎨 **Colores llamativos**: Amarillo/rojo llaman la atención sin ser molestos

---

## 🆚 Diferencias con Staking Messages

| Aspecto | Staking Messages | Empty Wallet Messages |
|---------|------------------|----------------------|
| **Cuándo se muestra** | Cuando hay wallet seleccionada | Cuando NO hay wallets |
| **Propósito** | Promover staking | Promover import de wallet |
| **Frecuencia** | En cada refresh | Una vez al inicio |
| **Tono** | Variado (celebratorio/neutral/irónico) | Siempre urgente pero divertido |
| **Cantidad** | 52 mensajes en 3 categorías | 30 mensajes en 1 categoría |

---

## 🔮 Roadmap Futuro

### Ideas para expansión:

- [ ] **Mensajes de onboarding progresivo**
  - "First import! 🎉" mensaje especial al importar la primera
  - "Second wallet! 🚀" para incentivar múltiples wallets

- [ ] **Mensajes contextuales por hora**
  - "☀️ Good morning! Time to import a wallet!" (mañana)
  - "🌙 Late night crypto? Import a wallet first!" (noche)

- [ ] **Easter eggs**
  - Mensaje especial si el usuario espera mucho sin importar
  - "Still here? 🥺 Just import one wallet, I promise it's easy!"

### Mejoras técnicas:

- [ ] Mensaje diferente cada vez que se abre la app (no solo una vez)
- [ ] Historial de mensajes para no repetir el mismo
- [ ] Integración con tutorial interactivo al importar primera wallet

---

## 🤝 Contribuir

¿Tienes ideas para mensajes divertidos? ¡Agrégalos!

1. Mantén el tono: divertido, irónico, urgente pero amigable
2. Usa emojis relevantes
3. Incluye "Press 'i'" en el mensaje
4. Mantén los mensajes cortos (máx 1-2 líneas)
5. Asegúrate de que sean divertidos pero no ofensivos
6. Prueba que funcione: `python3 empty_wallet_messages.py`

---

## 🎭 Ejemplos Completos de Mensajes

### 🚨 EMPTY (Sin Wallets)

```
🚨 Import a wallet for god sake! This bakery needs customers!
😭 It's SO empty in here! Press 'i' to import and fill this void!
🏜️ Tumbleweed rolling by... Import a wallet, please! Press 'i'!
🤷 No wallets? Really? Come on, press 'i' to get started!
💀 This bakery is DEAD without wallets! Import one NOW!
😂 You opened a wallet app... with NO wallets. Bold move!
🦗 *Cricket sounds* ... Import a wallet? Maybe? Press 'i'?
🚫 ERROR 404: Wallets not found. Press 'i' to fix this tragedy!
🥺 I'm begging you... just ONE wallet? Press 'i'! Pretty please?
🤡 Running a wallet app with no wallets? That's some clown energy!
🏚️ Empty shelves, empty dreams. Import a wallet to start baking!
🌵 Desert vibes. No wallets, no life. Import one already!
📦 This box is EMPTY! Time to unpack some wallets! Press 'i'!
🎻 Playing the world's smallest violin for your empty wallet list.
👻 BOO! Just kidding, there's nothing here. Import a wallet!
🎭 The show can't start without actors! Import a wallet (press 'i')!
🔔 DING DING! Reminder: This app needs wallets! Press 'i'!
🚀 Ready to launch... but there's no fuel! Import a wallet!
🎯 Mission: Import a wallet. Status: Not started. Press 'i'!
🏁 Race starts when you import a wallet! Ready, set... press 'i'!
```

---

## 🎨 Integración Visual

### En la Lista de Accounts (vacía):
```
┌─ Wallets ───────────────────────────────────┐
│ 🚨 Import a wallet for god sake!           │ ← Mensaje aleatorio en amarillo
│    This bakery needs customers!             │
└──────────────────────────────────────────────┘
```

### En el Panel de Información (sin wallet seleccionada):
```
┌─ Wallet Information ─────────────────────────┐
│ Wallet: 🚨 NONE! Import one!                 │ ← Rojo
│ Balance: [mensaje aleatorio]                  │ ← Amarillo
│ Delegated to: 🏜️ This bakery is empty...   │ ← Dim
│ Staked Balance: 😭 Press 'i' to import NOW! │ ← Rojo
└───────────────────────────────────────────────┘
```

---

**Mantenido por**: TUI Tezos Wallet Team
**Última actualización**: 2026-01-21
**Versión**: 1.3.0

🚨 Import those wallets!
