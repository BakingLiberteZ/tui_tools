# 💰 Balance Tier Messages Library

Sistema de mensajes dinámicos y motivacionales basados en el balance de la wallet y el estado de staking/delegación.

---

## 📚 Filosofía de Diseño

La wallet usa mensajes **divertidos, motivacionales e irónicos** que se adaptan al balance del usuario Y su comportamiento de staking/delegación. Los mensajes están diseñados para:

1. **Celebrar** a quienes stakean (sin importar el monto)
2. **Incentivar** a quienes solo delegan a que stakeen
3. **Motivar** (con humor) a quienes no participan
4. **Reconocer** los diferentes niveles de inversión

---

## 🎯 Tiers de Balance

### 🌫️ DUST (0-1 XTZ)
**"Almost nothing"**
- **+ Staking**: "Es poco pero es trabajo honesto" - celebración de compromiso
- **+ Delegando**: Reconocimiento gentil con invitación a stakear
- **+ Lazy**: Humor ligero sobre tener casi nada y no hacer nada

### 💸 BROKE (1-100 XTZ)
**"Starting out"**
- **+ Staking**: "McDonald's no paga mucho pero STAKEAS!" - respeto al esfuerzo
- **+ Delegando**: Invitación a mejorar, "podrías hacer más"
- **+ Lazy**: "McDonald's no paga mucho, crypto bro" - humor sobre no participar

### 💰 SAVER (100-500 XTZ)
**"Building wealth"**
- **+ Staking**: "Buenos ahorros Y stakeando!" - felicitaciones por hacerlo bien
- **+ Delegando**: "Tienes capital serio, por qué no stakeas?"
- **+ Lazy**: "Eso es dinero REAL sin hacer nada!" - urgencia aumenta

### 🏦 INVESTOR (500-1000 XTZ)
**"Serious player"**
- **+ Staking**: "Inversor serio con visión de futuro!" - respeto máximo
- **+ Delegando**: "Tienes capital de inversión, upgradea a staking!"
- **+ Lazy**: "Eso es un CARRO sin trabajar para ti!" - asombro

### 🐋 BABY WHALE (1000-5000 XTZ)
**"Big league"**
- **+ Staking**: "BALLENA BEBÉ! Elite mindset!" - celebración mayor
- **+ Delegando**: "Nivel ballena con estrategia principiante?"
- **+ Lazy**: "Eso es un NEGOCIO sin operar!" - crisis

### 🐳 WHALE (5000+ XTZ)
**"Crypto royalty"**
- **+ Staking**: "BALLENA CONFIRMADA! Defines la red!" - leyenda status
- **+ Delegating**: "Riqueza generacional solo delegando?"
- **+ Lazy**: "EMERGENCIA BALLENA! Dinero que cambia vidas IDLE!" - SOS

---

## 🎨 Sistema de Colores

Los mensajes del balance usan **CYAN** para diferenciarse:

```
Balance: 250 XTZ [cyan]💰 Nice savings AND staking! You're on the right path![/cyan]
```

Esto se diferencia de:
- 🟢 **Verde**: Mensajes de staking positivos
- 🟡 **Amarillo**: Mensajes de solo delegación
- 🔴 **Rojo**: Mensajes de inactividad
- 🔵 **Cyan**: Mensajes del balance tier

---

## 📊 Estadísticas

| Tier | Rango | Staking | Delegating | Lazy | Total |
|------|-------|---------|------------|------|-------|
| **DUST** | 0-1 XTZ | 8 | 5 | 5 | 18 |
| **BROKE** | 1-100 XTZ | 12 | 7 | 8 | 27 |
| **SAVER** | 100-500 XTZ | 12 | 7 | 7 | 26 |
| **INVESTOR** | 500-1K XTZ | 12 | 6 | 6 | 24 |
| **BABY WHALE** | 1K-5K XTZ | 14 | 6 | 6 | 26 |
| **WHALE** | 5K+ XTZ | 16 | 6 | 7 | 29 |
| **TOTAL** | - | **74** | **37** | **39** | **150** |

---

## 🔧 Uso

### Función Principal: `get_balance_message()`

```python
from balance_messages import get_balance_message
from decimal import Decimal

# Ejemplo 1: BROKE tier staking
balance = Decimal('50')
is_staking = True
is_delegating = False
msg = get_balance_message(balance, is_staking, is_delegating)
# Devuelve: "💪 It ain't much, but you're STAKING! That's what winners do!"

# Ejemplo 2: SAVER tier solo delegando
balance = Decimal('250')
is_staking = False
is_delegating = True
msg = get_balance_message(balance, is_staking, is_delegating)
# Devuelve: "💰 Good savings, but delegating only? Staking unlocks MORE!"

# Ejemplo 3: WHALE tier staking
balance = Decimal('10000')
is_staking = True
is_delegating = True
msg = get_balance_message(balance, is_staking, is_delegating)
# Devuelve: "🐳 WHALE CONFIRMED! Your stake DEFINES the network!"
```

### Integración en app.py

```python
from balance_messages import get_balance_message

# Obtener información necesaria
balance_xtz = mutez_to_xtz(bal)
delegate = get_delegation_info(rpc, address)
staking_bal = get_staking_balance(rpc, address)

# Determinar estados
is_staking = staking_bal > 0
is_delegating = delegate is not None

# Seleccionar mensaje y cachear
self._balance_message = get_balance_message(balance_xtz, is_staking, is_delegating)

# Mostrar en UI
self.query_one("#wallet_balance", Static).update(
    f"Balance: [b]{format_xtz(balance_xtz)} XTZ[/b] [cyan]{self._balance_message}[/cyan]"
)
```

---

## ➕ Cómo Agregar Nuevos Mensajes

### 1. Identificar el tier y estado

```python
# En balance_messages.py

BROKE_STAKING = [
    "💪 It ain't much, but you're STAKING! That's what winners do!",
    "🏆 McDonald's paycheck but STAKING like a champ! Respect!",
    # ✨ AGREGAR AQUÍ:
    "🌟 Small bag, BIG heart! Staking shows you care!",
]
```

### 2. Mantener el tono apropiado según tier + estado

**BROKE + STAKING (positivo, celebratorio):**
```python
✅ "💪 It ain't much, but you're STAKING! That's what winners do!"
❌ "You're staking... I guess that's something." (muy neutro)
```

**SAVER + DELEGATING (invitación a mejorar):**
```python
✅ "💰 Good savings, but delegating only? Staking unlocks MORE!"
❌ "STAKE NOW OR LOSE EVERYTHING!" (muy agresivo)
```

**WHALE + LAZY (urgencia crítica con humor):**
```python
✅ "😱 5000+ XTZ IDLE?! That's LIFE-CHANGING money doing NOTHING!"
❌ "You should probably delegate." (muy suave para este tier)
```

---

## 🎭 Ejemplos por Tier + Estado

### 🌫️ DUST Tier (0-1 XTZ)

**Staking:**
```
🌱 It's not much, but it's honest work! Staking your dust like a BOSS!
💎 Every diamond starts as coal! Staking even dust = legend status!
🦸 SUPERHERO! Staking with almost nothing! True believer energy!
```

**Delegating:**
```
😅 Delegating dust? Hey, at least you're trying! Baby steps!
🤏 Tiny balance, tiny effort. Consider staking for MORE!
```

**Lazy:**
```
😂 Less than 1 XTZ and not even delegating? BOLD strategy!
🌫️ Your balance is basically air. At least delegate it!
```

### 💸 BROKE Tier (1-100 XTZ)

**Staking:**
```
💪 It ain't much, but you're STAKING! That's what winners do!
🏆 McDonald's paycheck but STAKING like a champ! Respect!
🌱 Small seed, big dreams! Staking shows you understand the game!
```

**Delegating:**
```
😐 Delegating is OK, but you could do MORE! Try staking!
🥉 Bronze medal effort. Staking = gold! Upgrade your game!
```

**Lazy:**
```
😂 McDonald's not paying too much, crypto bro? AND not delegating?
💀 Under 100 XTZ and doing NOTHING? Opportunity = missed!
```

### 💰 SAVER Tier (100-500 XTZ)

**Staking:**
```
💰 Nice savings AND staking! You're on the right path!
🏆 Smart saver! Staking shows you're thinking long-term!
💎 Solid stack with staking! That's responsible crypto!
```

**Delegating:**
```
💰 Good savings, but delegating only? Staking unlocks MORE!
🤔 Nice bag! Why not STAKE it for better rewards?
```

**Lazy:**
```
😱 100-500 XTZ just SITTING there? Criminal negligence!
💀 Nice savings doing NOTHING! What a waste!
```

### 🏦 INVESTOR Tier (500-1000 XTZ)

**Staking:**
```
🏦 Serious investor alert! AND staking? You're a professional!
💎 Big brain energy! Staking 500+ shows you understand value!
👑 Crypto royalty! Staking this much means you're ALL IN!
```

**Delegating:**
```
🤔 500+ XTZ but only delegating? You're SO CLOSE to greatness!
💼 Business class traveler using economy! STAKE for first class!
```

**Lazy:**
```
😱 500+ XTZ just IDLE?! That's a CAR not working for you!
💀 SERIOUS money doing NOTHING! This hurts to see!
```

### 🐋 BABY WHALE Tier (1000-5000 XTZ)

**Staking:**
```
🐋 BABY WHALE SPOTTED! Staking = ELITE mindset!
👑 Crypto ROYALTY! Your stake matters to the entire network!
💎 DIAMOND WHALE! Staking this much = true believer!
```

**Delegating:**
```
🐋 Baby whale delegating? STAKE IT! You're leaving BIG rewards!
💼 That's a down payment on a HOUSE just delegating!
```

**Lazy:**
```
😱 1000+ XTZ IDLE?! That's a small BUSINESS not running!
💀 WHALE doing NOTHING! The ocean is CRYING!
```

### 🐳 WHALE Tier (5000+ XTZ)

**Staking:**
```
🐳 WHALE CONFIRMED! Your stake DEFINES the network!
👑 ABSOLUTE ROYALTY! The blockchain bows to your stake!
💎 DIAMOND HANDS WHALE! True Tezos OG right here!
🌊 OCEAN MASTER! You control the crypto seas!
```

**Delegating:**
```
🐳 WHALE delegating?! You should be STAKING! Imagine the rewards!
👑 Royalty-level bag with peasant-level strategy? STAKE IT!
```

**Lazy:**
```
😱 5000+ XTZ IDLE?! That's LIFE-CHANGING money doing NOTHING!
💀 WHALE EMERGENCY! This much idle is a TRAGEDY!
🆘 SOS! WHALE needs immediate staking intervention!
```

---

## 🧪 Testing

```bash
# Test el módulo directamente
python3 balance_messages.py

# Output esperado:
💰 Balance Tier Messages Library Test

DUST + Staking (0.5 XTZ):
  [mensaje aleatorio]

BROKE + Staking (50 XTZ):
  [mensaje aleatorio]

...

📊 Statistics:
  Total messages: 150
  Dust messages: 18
  Broke messages: 27
  Saver messages: 26
  Investor messages: 24
  Baby Whale messages: 26
  Whale messages: 29
```

---

## 🎯 Impacto y Objetivos

### Objetivos de UX:
1. **Reconocer** todos los niveles de inversión de manera positiva
2. **Celebrar** el staking sin importar el monto
3. **Incentivar** mejores prácticas (staking > delegating > nothing)
4. **Entretener** con humor apropiado para cada situación
5. **Personalizar** la experiencia según el comportamiento del usuario

### Métricas de éxito:
- ✅ Mensajes visibles en cada actualización de balance
- ✅ Cambio dinámico según balance Y comportamiento
- ✅ Tono apropiado para cada combinación tier + estado
- ✅ Usuarios sonríen y se sienten reconocidos

### Por qué funciona:
- 🎮 **Gamificación**: Convierte el balance en un "achievement" system
- 😄 **Humor inteligente**: Mensajes divertidos pero no ofensivos
- 💡 **Educación sutil**: Enseña diferencias entre staking/delegating/nothing
- 🏆 **Reconocimiento escalonado**: Celebra TODOS los niveles
- 🎨 **Psicología de tiers**: Crea aspiración a "subir de nivel"
- 💪 **Refuerzo positivo**: Siempre celebra el staking sin importar monto

---

## 🔮 Roadmap Futuro

### Ideas para expansión:

- [ ] **Mensajes de progreso**
  - "Subiste de tier! De BROKE a SAVER! 🎉"
  - "Wow, ahora eres WHALE! Journey complete!"

- [ ] **Mensajes históricos**
  - "Hace un mes tenías 50 XTZ, ahora 500! Growth!"
  - "Staking consistente por 3 meses! Diamond hands!"

- [ ] **Mensajes según red**
  - Mainnet: Mensajes más serios
  - Testnet: Mensajes más juguetones

- [ ] **Achievements especiales**
  - "Primera vez WHALE! 🐳"
  - "100 días staking consecutivos! 💯"

---

## 🤝 Contribuir

¿Tienes ideas para mensajes por tier? ¡Agrégalos!

1. Identifica el tier correcto (DUST/BROKE/SAVER/INVESTOR/BABY_WHALE/WHALE)
2. Identifica el estado correcto (STAKING/DELEGATING/LAZY)
3. Mantén el tono apropiado para esa combinación
4. Usa emojis relevantes
5. Mantén mensajes cortos (máx 1-2 líneas)
6. Prueba: `python3 balance_messages.py`

---

**Mantenido por**: TUI Tezos Wallet Team
**Última actualización**: 2026-01-21
**Versión**: 1.3.0

💰 Keep Stacking!
