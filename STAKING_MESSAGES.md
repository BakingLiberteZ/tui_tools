# 💪 Staking Messages Library

Sistema de mensajes motivacionales para promover el staking y la participación en la red Tezos.

---

## 📚 Filosofía de Diseño

La wallet usa mensajes divertidos, motivacionales y a veces irónicos para **promover el staking** y la participación activa en la seguridad de la red Tezos. Los mensajes se adaptan dinámicamente según el comportamiento del usuario.

### 💪 **CHAD** = Staking Activo
Para wallets con **staking balance > 0**:
- Mensajes super positivos y celebratorios
- Reconoce la contribución a la seguridad de la red
- Usa lenguaje tipo "What a chad!", "Gigachad energy", "Diamond hands"
- Color: **🟢 Verde** (refuerzo positivo y celebración)
- Objetivo: **Reforzar el comportamiento positivo**

### 😴 **BORING** = Solo Delegando
Para wallets **delegando pero NO staking**:
- Mensajes neutrales con un toque de sarcasmo
- Sugiere que el staking es mejor
- Usa lenguaje tipo "Ok, fine, boring", "Playing it safe, huh?"
- Color: **🟡 Amarillo** (invitación amigable a mejorar)
- Objetivo: **Incentivar a pasar de delegación a staking**

### 😂 **LAZY** = Sin Participación
Para wallets **ni delegando ni staking**:
- Mensajes divertidos, irónicos y burlones
- Enfatiza la oportunidad perdida
- Usa lenguaje tipo "Do you even Tezos?", "It's so lonely here"
- Color: **🔴 Rojo** (urgencia y llamado a la acción)
- Objetivo: **Motivar a empezar a participar en la red**

---

## 📁 Estructura del Archivo

```python
# staking_messages.py

# Categorías de mensajes (listas de strings):
STAKING_CHAD = [...]      # 15 mensajes para stakers activos
STAKING_BORING = [...]    # 15 mensajes para solo delegadores
STAKING_LAZY = [...]      # 22 mensajes para inactivos
```

---

## 🔧 Uso

### Función Principal: `get_staking_message()`

```python
from staking_messages import get_staking_message

# Contexto: "chad" (staking > 0)
msg = get_staking_message("chad")
# Devuelve: "💪 What a CHAD! Securing the network like a BOSS!"

# Contexto: "boring" (delegando pero no staking)
msg = get_staking_message("boring")
# Devuelve: "😴 Ok, fine, boring... Delegating but no skin in the game?"

# Contexto: "lazy" (ni delegando ni staking)
msg = get_staking_message("lazy")
# Devuelve: "😂 Do you even Tezos, bro? STAKE SOMETHING!"

# Contextos disponibles:
contexts = ["chad", "boring", "lazy"]
```

### Ejemplo de Integración en app.py

```python
from staking_messages import get_staking_message

# Obtener staking balance y delegation status
staking_bal = get_staking_balance(rpc, address)
delegate = get_delegation_info(rpc, address)

# Determinar contexto y mensaje
if staking_bal > 0:
    # CHAD: Está staking activamente - VERDE (refuerzo positivo)
    msg = get_staking_message("chad")
    display = f"Staked Balance: {format_xtz(staking_bal)} XTZ [green]{msg}[/green]"
elif delegate:
    # BORING: Solo delegando, no staking - AMARILLO (invitación amigable)
    msg = get_staking_message("boring")
    display = f"Staked Balance: - [yellow]{msg}[/yellow]"
else:
    # LAZY: Ni delegando ni staking - ROJO (urgencia)
    msg = get_staking_message("lazy")
    display = f"Staked Balance: - [red]{msg}[/red]"
```

---

## 📊 Estadísticas Actuales

| Categoría | Cantidad | Ejemplo | Color |
|-----------|----------|---------|-------|
| **CHAD** (Staking) | 15 | "💪 What a CHAD! Securing the network like a BOSS!" | 🟢 Verde |
| **BORING** (Solo delegando) | 15 | "😴 Ok, fine, boring... Delegating but no skin in the game?" | 🟡 Amarillo |
| **LAZY** (Inactivo) | 22 | "😂 Do you even Tezos, bro? STAKE SOMETHING!" | 🔴 Rojo |
| **TOTAL** | **52** | 52 mensajes únicos! | - |

---

## ➕ Cómo Agregar Nuevos Mensajes

### 1. Agregar a una lista existente

```python
# En staking_messages.py

STAKING_CHAD = [
    "💪 What a CHAD! Securing the network like a BOSS!",
    "🏆 Absolute legend! Staking AND securing! RESPECT!",
    # ✨ AGREGAR AQUÍ TU NUEVO MENSAJE:
    "🦸 SUPERHERO! Your stake saves the day!",
]
```

### 2. Mantener el tono apropiado

**CHAD (Positivo, celebratorio):**
```python
✅ "🌟 ELITE status! You're what makes Tezos great!"
❌ "You're staking, I guess..." (demasiado neutro)
```

**BORING (Neutro con sarcasmo suave):**
```python
✅ "😴 Ok, fine, boring... Delegating but no skin in the game?"
❌ "YOU'RE DOING IT WRONG!" (demasiado agresivo)
```

**LAZY (Irónico, divertido, burlón):**
```python
✅ "😂 Do you even Tezos, bro? STAKE SOMETHING!"
❌ "You should probably stake." (demasiado formal)
```

---

## 🎨 Guías de Estilo

### ✅ Buenos mensajes:

1. **Cortos y directos** (no novelas)
   ```python
   ✅ "💪 What a CHAD! Securing the network like a BOSS!"
   ❌ "You are currently participating in the Tezos staking mechanism which is a very important part of the network's security model..."
   ```

2. **Usan emojis relevantes**
   ```python
   ✅ "🏆 Absolute legend! RESPECT!"
   ❌ "Absolute legend! RESPECT!" (sin emoji es aburrido)
   ```

3. **Tienen personalidad**
   ```python
   ✅ "🚨 ALERT: This wallet is allergic to profit!"
   ❌ "You are not staking. Consider staking."
   ```

4. **Reflejan el tono correcto para cada categoría**
   ```python
   # CHAD: Positivo, energético
   ✅ "🔥 GIGACHAD energy! Making Tezos stronger!"

   # BORING: Neutro, sarcástico
   ✅ "😴 Delegation: the diet soda of Tezos participation."

   # LAZY: Irónico, burlón
   ✅ "😂 The baker cries every time you don't stake!"
   ```

---

## 🧪 Testing

```bash
# Test el módulo directamente
python3 staking_messages.py

# Output esperado:
💪 Staking Messages Library Test

CHAD:
  [mensaje aleatorio de STAKING_CHAD]

BORING:
  [mensaje aleatorio de STAKING_BORING]

LAZY:
  [mensaje aleatorio de STAKING_LAZY]

📊 Statistics:
  Chad messages: 15
  Boring messages: 15
  Lazy messages: 22
  TOTAL: 52
```

---

## 🎯 Impacto y Objetivos

### Objetivos de UX:
1. **Promover el staking** de manera divertida y no intrusiva
2. **Educar** sobre los beneficios del staking vs solo delegación
3. **Crear engagement** con mensajes que hacen sonreír al usuario
4. **Reforzar comportamiento positivo** cuando están staking

### Métricas de éxito:
- ✅ Mensajes visibles en cada actualización de balance
- ✅ Cambio dinámico según comportamiento del usuario
- ✅ Tono apropiado para cada categoría
- ✅ Usuarios sonríen al ver los mensajes (feedback cualitativo)

### Por qué funciona:
- 🎮 **Gamificación**: Convierte la participación en un "status"
- 😄 **Humor**: Hace que la experiencia sea memorable
- 💰 **FOMO**: Los mensajes LAZY crean "fear of missing out"
- 🏆 **Reconocimiento**: Los mensajes CHAD validan el esfuerzo
- 🎨 **Psicología de color**:
  - 🟢 Verde = Éxito, aprobación, continúa así
  - 🟡 Amarillo = Advertencia suave, puedes mejorar
  - 🔴 Rojo = Urgencia, acción requerida

---

## 🔮 Roadmap Futuro

### Ideas para expansión:

- [ ] **Mensajes basados en cantidad staked**
  - "Whale alert! 🐋" para grandes cantidades
  - "Shrimp gang! 🦐" para pequeñas cantidades (con amor)

- [ ] **Mensajes temporales**
  - "Early bird staker! 🐦" para quienes staking desde temprano
  - "Fresh baker! 🥖" para wallets nuevas que empiezan staking

- [ ] **Mensajes según baker**
  - "Public baker supporter! 💚" para ciertos bakers conocidos
  - "Independent baker! 🦅" para bakers menos conocidos

- [ ] **Achievements/Milestones**
  - "First stake! 🎉" cuando alguien hace su primer stake
  - "1 month staking! 📅" para stakers consistentes

### Mejoras técnicas:

- [ ] Mensajes ponderados (algunos aparecen más que otros)
- [ ] Historial de mensajes (no repetir el mismo 2 veces seguidas)
- [ ] Mensajes personalizables por el usuario
- [ ] Integración con notificaciones cuando cambien de estado

---

## 🤝 Contribuir

¿Tienes ideas para mensajes divertidos? ¡Agrégalos!

1. Mantén el tono apropiado para cada categoría
2. Usa emojis relevantes
3. Mantén los mensajes cortos (máx 1-2 líneas)
4. Asegúrate de que sean divertidos pero no ofensivos
5. Prueba que funcione: `python3 staking_messages.py`

---

## 🎭 Ejemplos de Mensajes por Categoría

### 💪 CHAD (Staking Activo)

```
💪 What a CHAD! Securing the network like a BOSS!
🏆 Absolute legend! Staking AND securing! RESPECT!
💎 Diamond hands! TRUE Tezos believer right here!
👑 KING/QUEEN of staking! The network LOVES you!
🔥 GIGACHAD energy! Making Tezos stronger every block!
```

### 😴 BORING (Solo Delegando)

```
😴 Ok, fine, boring... Delegating but no skin in the game?
🥱 Meh. Delegation is ok, but staking is WHERE IT'S AT!
💤 Playing it safe, huh? Staking gives you MORE rewards...
🤷 I mean, sure, delegate... but have you TRIED staking?
😑 Delegation: the diet soda of Tezos participation.
```

### 😂 LAZY (Sin Participación)

```
😂 Do you even Tezos, bro? STAKE SOMETHING!
🏜️ It's so lonely here... Let's stake something please, for my family! 😢
🤡 Not delegating? Not staking? CLOWN BEHAVIOR! 🤡
💀 RIP to your potential rewards. F in the chat.
🚨 ALERT: This wallet is allergic to profit! Doctor says STAKE NOW!
```

---

**Mantenido por**: TUI Tezos Wallet Team
**Última actualización**: 2026-01-21
**Versión**: 1.3.0

💪 Keep Staking!
