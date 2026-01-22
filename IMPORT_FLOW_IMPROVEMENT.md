# ✨ Mejora: Flujo de Import con Botones Descriptivos

## 🎯 Objetivo

Mejorar la claridad del flujo de importación de wallets usando botones con nombres específicos y descriptivos en cada paso, guiando al usuario a través del proceso.

---

## 🔄 Flujo de Import

El flujo de import tiene varios pasos secuenciales:

1. **Account name** → Usuario ingresa nombre para la wallet
2. **Tezos account** → Usuario ingresa dirección tz1/tz2/tz3/tz4
3. **Secret key** → Usuario ingresa secret key (OPCIONAL, puede dejarse vacío para watch-only)
4. **Passphrase** → Usuario ingresa passphrase para encriptar (solo si proporcionó secret key)

---

## 📊 Cambios en Botones

### ANTES - Botones Genéricos:

```
Paso 1: Account name
┌────────────────────────────┐
│ Account name:              │
│ [input field]              │
│                            │
│    [OK]      [Cancel]      │  ❌ "OK" es genérico
└────────────────────────────┘

Paso 2: Tezos account
┌────────────────────────────┐
│ Tezos account (tz1...):    │
│ [input field]              │
│                            │
│    [OK]      [Cancel]      │  ❌ "OK" es genérico
└────────────────────────────┘

Paso 3: Secret key
┌────────────────────────────┐
│ Secret key (OPTIONAL):     │
│ [input field]              │
│                            │
│    [OK]      [Cancel]      │  ❌ "OK" no indica que es el último paso
└────────────────────────────┘

Paso 4: Passphrase (si hay secret key)
┌────────────────────────────┐
│ Passphrase to encrypt key: │
│ [password field]           │
│                            │
│    [OK]      [Cancel]      │  ❌ "OK" no indica que importará
└────────────────────────────┘
```

### DESPUÉS - Botones Descriptivos:

```
Paso 1: Account name
┌────────────────────────────┐
│ Account name:              │
│ [input field]              │
│                            │
│   [Next]     [Cancel]      │  ✅ "Next" indica continuación
└────────────────────────────┘

Paso 2: Tezos account
┌────────────────────────────┐
│ Tezos account (tz1...):    │
│ [input field]              │
│                            │
│   [Next]     [Cancel]      │  ✅ "Next" indica continuación
└────────────────────────────┘

Paso 3: Secret key
┌────────────────────────────┐
│ Secret key (OPTIONAL):     │
│ [input field]              │
│                            │
│  [Import]    [Cancel]      │  ✅ "Import" indica acción final
└────────────────────────────┘

Paso 4: Passphrase (si hay secret key)
┌────────────────────────────┐
│ Passphrase to encrypt key: │
│ [password field]           │
│                            │
│  [Import]    [Cancel]      │  ✅ "Import" indica acción final
└────────────────────────────┘
```

---

## 🔧 Cambios Técnicos

### 1. PromptScreen Parametrizable ✅

**Modificación**: Agregar parámetro `ok_label` en `__init__` y usar en `compose()`.

**Antes**:
```python
def __init__(self, title: str, placeholder: str = "", password: bool = False, wallet_info: str = ""):
    super().__init__()
    self._title = title
    self._placeholder = placeholder
    self._password = password
    self._wallet_info = wallet_info

def compose(self) -> ComposeResult:
    with Vertical():
        # ...
        with Horizontal():
            yield Button("OK", id="ok")  # ❌ Hardcoded
            yield Button("Cancel", id="cancel")
```

**Después**:
```python
def __init__(self, title: str, placeholder: str = "", password: bool = False,
             wallet_info: str = "", ok_label: str = "OK"):
    super().__init__()
    self._title = title
    self._placeholder = placeholder
    self._password = password
    self._wallet_info = wallet_info
    self._ok_label = ok_label  # ✅ Parametrizable

def compose(self) -> ComposeResult:
    with Vertical():
        # ...
        with Horizontal():
            yield Button(self._ok_label, id="ok", variant="primary")  # ✅ Dinámico
            yield Button("Cancel", id="cancel")
```

---

### 2. Flujo de Import Actualizado ✅

**Paso 1 - Account Name** (intermedio):
```python
# ANTES
name = await self.push_screen_wait(PromptScreen("Account name:"))

# DESPUÉS
name = await self.push_screen_wait(PromptScreen("Account name:", ok_label="Next"))
```

**Paso 2 - Tezos Account** (intermedio):
```python
# ANTES
addr = await self.push_screen_wait(PromptScreen("Tezos account (tz1/tz2/tz3/tz4):"))

# DESPUÉS
addr = await self.push_screen_wait(PromptScreen("Tezos account (tz1/tz2/tz3/tz4):", ok_label="Next"))
```

**Paso 3 - Secret Key** (puede ser final si se deja vacío):
```python
# ANTES
secret = await self.push_screen_wait(PromptScreen("Secret key (edsk...) OPTIONAL (blank = watch-only):"))

# DESPUÉS
secret = await self.push_screen_wait(PromptScreen("Secret key (edsk...) OPTIONAL (blank = watch-only):", ok_label="Import"))
```

**Paso 4 - Passphrase** (final si hay secret key):
```python
# ANTES
pw = await self.push_screen_wait(PromptScreen("Passphrase to encrypt key:", password=True, wallet_info=f"Wallet: {name}"))

# DESPUÉS
pw = await self.push_screen_wait(PromptScreen("Passphrase to encrypt key:", password=True, wallet_info=f"Wallet: {name}", ok_label="Import"))
```

---

## 🎨 Flujo Visual Completo

### Opción A: Con Secret Key (4 pasos)

```
1. [Import (i)] → Click
   ↓
2. ┌─────────────────────────┐
   │ Account name:           │
   │ ┌─────────────────────┐ │
   │ │ My Wallet           │ │
   │ └─────────────────────┘ │
   │   [Next]    [Cancel]    │  ← "Next" indica continuación
   └─────────────────────────┘
   ↓
3. ┌─────────────────────────┐
   │ Tezos account (tz1...): │
   │ ┌─────────────────────┐ │
   │ │ tz1abc...xyz        │ │
   │ └─────────────────────┘ │
   │   [Next]    [Cancel]    │  ← "Next" indica continuación
   └─────────────────────────┘
   ↓
4. ┌─────────────────────────┐
   │ Secret key (OPTIONAL):  │
   │ ┌─────────────────────┐ │
   │ │ edsk...             │ │
   │ └─────────────────────┘ │
   │  [Import]   [Cancel]    │  ← "Import" porque puede ser el último
   └─────────────────────────┘
   ↓ (si se proporcionó secret key)
5. ┌─────────────────────────┐
   │ Passphrase to encrypt:  │
   │ Wallet: My Wallet       │
   │ ┌─────────────────────┐ │
   │ │ ••••••••            │ │
   │ └─────────────────────┘ │
   │  [Import]   [Cancel]    │  ← "Import" acción final
   └─────────────────────────┘
   ↓
6. ✅ Account saved successfully
```

### Opción B: Sin Secret Key - Watch-Only (3 pasos)

```
1. [Import (i)] → Click
   ↓
2. ┌─────────────────────────┐
   │ Account name:           │
   │ ┌─────────────────────┐ │
   │ │ Watch Wallet        │ │
   │ └─────────────────────┘ │
   │   [Next]    [Cancel]    │  ← "Next" indica continuación
   └─────────────────────────┘
   ↓
3. ┌─────────────────────────┐
   │ Tezos account (tz1...): │
   │ ┌─────────────────────┐ │
   │ │ tz1abc...xyz        │ │
   │ └─────────────────────┘ │
   │   [Next]    [Cancel]    │  ← "Next" indica continuación
   └─────────────────────────┘
   ↓
4. ┌─────────────────────────┐
   │ Secret key (OPTIONAL):  │
   │ ┌─────────────────────┐ │
   │ │ (vacío)             │ │
   │ └─────────────────────┘ │
   │  [Import]   [Cancel]    │  ← "Import" porque es el último paso
   └─────────────────────────┘
   ↓
5. ✅ Account saved successfully (watch-only)
```

---

## ✅ Beneficios

### 1. **Guía Clara del Proceso**
"Next" indica al usuario que hay más pasos por delante.

### 2. **Confirmación Explícita**
"Import" comunica claramente que es el último paso y se ejecutará la importación.

### 3. **Mejor UX en Flujos Multi-Paso**
El usuario entiende dónde está en el proceso:
- "Next" → Hay más pasos
- "Import" → Este es el último paso

### 4. **Consistencia con Otros Modales**
Ahora Import también usa botones específicos como Backup, Export y Delete.

### 5. **Menos Ambigüedad**
No hay confusión sobre si "OK" guardará la wallet o simplemente avanzará al siguiente paso.

---

## 🧪 Cómo Probar

```bash
python3 app.py
```

### Test 1: Import con Secret Key

1. Presiona **i** (Import)
2. **Paso 1**: Ingresa nombre → Verifica botón **[Next]**
3. Click en [Next]
4. **Paso 2**: Ingresa dirección → Verifica botón **[Next]**
5. Click en [Next]
6. **Paso 3**: Ingresa secret key → Verifica botón **[Import]**
7. Click en [Import]
8. **Paso 4**: Ingresa passphrase → Verifica botón **[Import]**
9. Click en [Import]
10. ✅ Wallet importada con secret key encriptada

### Test 2: Import Watch-Only (sin secret key)

1. Presiona **i** (Import)
2. **Paso 1**: Ingresa nombre → Verifica botón **[Next]**
3. Click en [Next]
4. **Paso 2**: Ingresa dirección → Verifica botón **[Next]**
5. Click en [Next]
6. **Paso 3**: Deja vacío secret key → Verifica botón **[Import]**
7. Click en [Import]
8. ✅ Wallet watch-only importada (sin step 4)

### Test 3: Cancel en Cualquier Paso

1. Presiona **i** (Import)
2. En cualquier paso, click en [Cancel]
3. ✅ Proceso cancelado correctamente

---

## 📊 Comparación de Botones

### ANTES:

| Paso | Botón | Problema |
|------|-------|----------|
| 1. Name | "OK" | ❌ Genérico |
| 2. Address | "OK" | ❌ Genérico |
| 3. Secret | "OK" | ❌ No indica que es final |
| 4. Passphrase | "OK" | ❌ No indica que importará |

### DESPUÉS:

| Paso | Botón | Mejora |
|------|-------|--------|
| 1. Name | "Next" | ✅ Indica continuación |
| 2. Address | "Next" | ✅ Indica continuación |
| 3. Secret | "Import" | ✅ Indica acción final |
| 4. Passphrase | "Import" | ✅ Indica acción final |

---

## 💡 Lógica de Botones

### ¿Por qué "Import" en paso 3 Y 4?

- **Paso 3 (Secret key)**: Puede ser el último paso si se deja vacío (watch-only)
- **Paso 4 (Passphrase)**: Es el último paso si se proporcionó secret key

**Ambos son potencialmente finales**, por eso ambos usan "Import".

### ¿Por qué no "Skip" para secret key vacío?

Usar "Import" es más claro porque el usuario entiende que al dejarlo vacío y hacer click en "Import", se importará una wallet watch-only. "Skip" podría confundirse con "saltar este paso" sin importar nada.

---

## 📐 Tamaño de Modales

Los modales de PromptScreen tienen:
- **width**: 50 (compacto, apropiado para inputs simples)
- **height**: auto (se ajusta al contenido)

Este tamaño es apropiado para inputs de una línea. Los modales se mantienen compactos y focalizados.

---

## 🎉 Resultado

**Antes**: Todos los pasos del import usaban botón genérico "OK", sin indicación clara de cuándo se ejecutaría la importación.

**Ahora**: Flujo claro con botones descriptivos:
- Pasos intermedios → "Next" (indica continuación)
- Pasos finales → "Import" (indica acción final)

Los usuarios ahora tienen una guía clara del proceso de importación, sabiendo exactamente cuándo se ejecutará la acción final.

**¡Flujo más intuitivo y profesional!** ✨

---

## 🎨 Coherencia con Otros Modales

Ahora TODOS los modales principales usan botones específicos:

| Modal | Botón Principal | Contexto |
|-------|----------------|----------|
| **Import** | "Next" / "Import" | Multi-paso con botón final específico |
| **Backup** | "Backup" | Selector con botón específico |
| **Export** | "Export" | Selector con botón específico |
| **Delete** | "Delete" | Confirmación con botón específico |
| **SEND** | "Next" / [acción] | Multi-paso (destination, amount, confirm) |

**Sistema consistente en toda la aplicación!** 🎯

---

## 📚 Archivos Modificados

### app.py
1. **PromptScreen** (línea ~470-485)
   - Agregado parámetro `ok_label`
   - Botón usa `self._ok_label` en lugar de "OK" hardcoded
   - Agregado `variant="primary"` al botón OK

2. **action_import_wallet** (línea ~2878-2903)
   - Paso 1 (name): `ok_label="Next"`
   - Paso 2 (address): `ok_label="Next"`
   - Paso 3 (secret): `ok_label="Import"`
   - Paso 4 (passphrase): `ok_label="Import"`

---

**Fecha**: $(date)
**Tipo**: UX Improvement
**Estado**: ✅ Completado
