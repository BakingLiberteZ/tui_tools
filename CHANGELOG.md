# 📋 Changelog - Sassy Wallet

Todos los cambios notables del proyecto se documentan en este archivo.

---

## [1.3.0] - 2026-01-21

### 🎉 Branding Oficial: Sassy Wallet
- **Logo oficial actualizado**: Nuevo logo ASCII "Sassy Wallet" en estilo figlet
  - Reemplaza el logo anterior "TUI - Tezos Wallet"
  - Refleja la personalidad sassy, atrevida y desafiante de la wallet
  - Nombre que representa la actitud motivacional y chistosa de todos los sistemas de mensajes
  - Logo de 12 líneas con diseño elegante usando caracteres ▓ y símbolos especiales
  - Marca el debut oficial del nombre "Sassy Wallet"
- **Filosofía de la marca**: Una wallet con personalidad que motiva a los usuarios a:
  - 💪 Trabajar más y aumentar su balance (mensajes por tier)
  - 🔥 Stakear y participar activamente en la red (mensajes de staking)
  - 🚀 Tomar acción en lugar de dejar sus fondos idle (mensajes lazy)
  - 😄 Disfrutar la experiencia cripto con humor y sass

### ✨ Añadido
- **🎭 Biblioteca de mensajes de panadería**: Nuevo archivo `bakery_messages.py` con mensajes dinámicos
  - 10+ variaciones para cada contexto (RPC, transacciones, refresh, import, backup, delete)
  - 35+ mensajes de spinner/loading diferentes
  - Mensajes seleccionados aleatoriamente para dar dinamismo y personalidad
  - Función helper `get_message(context, **kwargs)` para fácil uso
  - Testing incluido para validar todos los contextos
  - Sistema modular y extensible para agregar más frases
- **💪 Sistema de mensajes motivacionales de staking**: Nuevo archivo `staking_messages.py`
  - Promueve el staking y la participación en la red de manera divertida
  - 3 categorías de mensajes según comportamiento del usuario:
    - 💪 **CHAD** (15 mensajes): Para wallets con staking activo - Celebratorio y positivo en VERDE
    - 😴 **BORING** (15 mensajes): Para wallets solo delegando - Neutral con sarcasmo en AMARILLO
    - 😂 **LAZY** (22 mensajes): Para wallets sin participación - Irónico y burlón en ROJO
  - Sistema de colores psicológicos:
    - 🟢 **Verde**: Refuerzo positivo para quienes stakean ("What a CHAD!")
    - 🟡 **Amarillo**: Invitación amigable a stakear para delegadores ("Meh, try staking?")
    - 🔴 **Rojo**: Urgencia y llamado a la acción para inactivos ("Do you even Tezos?")
  - 52 mensajes únicos totales con personalidad y emojis
  - Gamificación para incentivar mejores prácticas de staking
  - Mensaje se cachea por refresh para consistencia (no cambia hasta próximo refresh)
  - Documentación completa en `STAKING_MESSAGES.md`
- **🚨 Mensajes para wallets vacías**: Nuevo archivo `empty_wallet_messages.py`
  - Mensajes divertidos e irónicos cuando el usuario abre la app sin wallets importadas
  - 30 mensajes únicos con personalidad y humor
  - Tono urgente pero amigable: "🚨 Import a wallet for god sake! This bakery needs customers!"
  - Mostrados en la lista de accounts cuando está vacía (en amarillo)
  - Mostrados en el panel de información de wallet con múltiples mensajes creativos
  - Mensaje se selecciona una vez al iniciar la app (consistente durante la sesión)
  - Llamado claro a la acción: todos mencionan "Press 'i' to import"
  - Refuerza la metáfora del bakery: "This bakery is empty..."
  - Documentación completa en `EMPTY_WALLET_MESSAGES.md`
- **🎨 Logo ASCII actualizado**: Nuevo diseño de logo en `ascii_logo.txt`
  - Logo actualizado con diseño tipo "figlet" más profesional
  - Utiliza caracteres especiales (▓, \, /, _, |) para texto en relieve
  - 9 líneas de altura con diseño "TUI - Tezos Wallet"
  - Padding reducido (margin-bottom: 0, padding: 0) para mejor aprovechamiento del espacio
  - Se integra perfectamente sin modificar el layout existente
  - Cargado dinámicamente desde archivo para fácil modificación
  - Estilo moderno y profesional que se adapta al tema de la aplicación
- **💰 Sistema de mensajes por tier de balance**: Nuevo archivo `balance_messages.py`
  - Mensajes dinámicos que se adaptan al balance Y comportamiento del usuario
  - **6 tiers de balance**: DUST (0-1), BROKE (1-100), SAVER (100-500), INVESTOR (500-1K), BABY WHALE (1K-5K), WHALE (5K+)
  - **3 estados por tier**: Staking, Delegating, Lazy
  - **150 mensajes únicos** distribuidos en 18 categorías (6 tiers × 3 estados)
  - **Ejemplos de mensajes:**
    - BROKE + Staking: "💪 It ain't much, but you're STAKING! That's what winners do!"
    - SAVER + Delegating: "💰 Good savings, but delegating only? Staking unlocks MORE!"
    - WHALE + Lazy: "😱 5000+ XTZ IDLE?! That's LIFE-CHANGING money doing NOTHING!"
  - **Lógica inteligente**: Celebra el staking sin importar el monto, incentiva a mejorar
  - **Color cyan** para diferenciarse de otros mensajes (verde/amarillo/rojo)
  - Mensaje se cachea por refresh para consistencia
  - Integrado en la línea del balance
  - Gamificación completa del sistema de balance
  - Documentación completa en `BALANCE_MESSAGES.md`
- **Importar desde Backup**: Nueva opción para restaurar wallets desde archivos de backup JSON
  - Selector de tipo de importación con 3 opciones: Secret Key, Watch-Only, From Backup
  - Entrada manual de ruta con sugerencias claras del directorio por defecto
  - Placeholder muestra la ruta completa: `data/backups/wallet_backup_YYYY-MM-DD.json`
  - Soporte para rutas relativas, absolutas, y expansión de `~`
  - Validación completa de estructura de backup
  - Restauración automática de destinos recientes
  - Opción para renombrar wallet durante importación
  - Verificación de duplicados (por dirección)
  - Mensajes temáticos: "🥖 Reheated from the pantry!"
- **Flujo de importación modular**: División del flujo en 3 métodos independientes
  - `_import_with_secret_key()` - Importación con clave privada
  - `_import_watch_only()` - Importación en modo solo lectura
  - `_import_from_backup()` - Importación desde backup (NUEVO)

### 🔧 Mejorado
- **🌊 Efecto breathing glow durante transacciones**: Feedback visual mejorado durante el envío de XTZ
  - Efecto de "respiración" (breathing glow) con alternancia de color naranja brillante/tenue
  - Se activa automáticamente cuando la transacción está en proceso
  - Ciclo de 0.8 segundos entre estados para efecto suave y no intrusivo
  - Se detiene automáticamente al completar (éxito o error)
  - Mensajes actualizados a temática del baker: "👨‍🍳 Baker is processing your pastries, sit tight…"
  - Status bar verde brillante al completarse exitosamente con ✓ checkmark
  - CSS optimizado con clases `status-processing` y `status-processing-dim`
- **📐 Espaciado consistente en botones de modales**: Todos los botones dentro de ventanas modales ahora tienen el mismo espaciado que los botones principales
  - Agregado `margin: 0 1;` a botones dentro de todos los modales
  - Afecta a 13 ventanas modales: Import, Backup, Delete, Network, Receive, Send, Confirm, etc.
  - Los botones ya no están pegados y tienen separación visual clara
  - Consistencia visual en toda la aplicación
- **📏 Alineación mejorada en tabla de wallets**: Divisor vertical │ movido ligeramente a la derecha
  - Header ajustado con un espacio adicional para alinear perfectamente con el contenido
  - Ahora el divisor vertical del título coincide exactamente con el divisor del contenido
  - Mejor legibilidad y presentación visual
- **📝 Indentación del título "Recent Transactions"**: Título separado del borde izquierdo
  - Agregado `padding-left: 2;` al título para consistencia visual
  - Ya no está pegado al borde izquierdo de la aplicación
  - Alineado con otros elementos de la interfaz
- **🪟 Ventana de Receive optimizada**: Mejor adaptación al contenido y consistencia de colores
  - Reducido `min-width` de 60 a 50 para mejor adaptación al texto
  - Reducido `max-width` de 75 a 70 para ventana más compacta
  - Botón "Copy" ahora usa el color azul estándar (#3b82f6) como botones principales
  - Hover effect consistente con resto de la app
  - Mejor experiencia visual y coherencia de diseño
- **Consistencia temática de mensajes**: Diferenciación clara entre metáforas de oven y display
  - 🔥 **Oven/Horno**: Para operaciones que se están PROCESANDO (transacciones, RPC check)
  - 🪟 **Display/Shelf/Vitrina**: Para datos YA LISTOS/TERMINADOS (historial, balance)
  - Refresh: "🪟 Checking the display shelf…" → "✨ Display shelf refreshed! Fresh pastries on view! 🥐"
  - RPC check inicial: Mantiene metáfora de oven (correcto para procesamiento)
  - Spinner messages: "Dusting the display shelf... 🧹✨" (para refresh/historial)
- **Selector de tipo de importación**: Modal interactivo para elegir método de importación
  - Interfaz visual consistente con resto de la app
  - Descripción clara de cada opción
  - Navegación por teclado
- **Validación robusta**: Verificación exhaustiva de archivos de backup
  - Validación de JSON
  - Validación de estructura
  - Validación de dirección Tezos
- **Limitación de wallets visibles**: Máximo 3 wallets visibles con scroll automático
  - Panel principal: max 3 wallets visibles
  - Selectores modales: max 3 wallets visibles
  - Evita que los paneles se agranden demasiado
  - Scroll automático para más de 3 wallets
- **Etiqueta de staking mejorada**: Cambio de "Staking" a "Staked Balance"
  - Más claro y descriptivo
  - Consistente con terminología de Tezos
- **Mensajes divertidos en selectores**: Tema de panadería en todos los selectores modales
  - Backup: "💾 Save that precious dough, baby! Your recipe book awaits!" (botón amarillo)
  - Delete: "🔥 Back to the oven it goes! Choose wisely - no unbaking!" (botón rojo)
  - Mantiene consistencia del tema en toda la app
  - CSS personalizado para colores de botones (amarillo para backup, rojo para delete)
- **Ruta de backup en status**: El mensaje de backup exitoso ahora muestra la ruta completa
  - Formato: "📦 Wallet recipe saved! 'name' (X.X KB) → /full/path/to/backup.json"
  - Facilita encontrar el archivo de backup
  - Ruta absoluta para claridad
- **Mensajes RPC con tema de panadería**: Status inicial del RPC ahora usa el tema
  - ✅ RPC OK: "🔥 RPC oven is hot and ready! Bakers waiting to process any pastry you throw at 'em, baby! 🥐✨"
  - ⚠️ Simulación restringida: "⚡ RPC oven is warm but can't preview the dough! Blind baking mode enabled! 🥖"
  - ⚠️ Solo lectura: "🪟 RPC oven is display-only! Window shopping at the bakery! 👀"
  - Checking: "🔍 Checking if the oven is preheated…"
  - Mensajes ahora mencionan a los bakers esperando procesar transacciones
- **Tiempo visible del mensaje de borrado**: Agregado delay de 0.8s después de borrar wallet
  - El mensaje "Burned like toast" ahora es visible antes de que la UI se actualice
  - Mejor feedback visual para el usuario
- **Mensajes de importación más elocuentes**: Status más llamativos y celebratorios al importar wallets
  - Secret Key: "🎉 New pastry 'name' fresh from the oven! Golden-brown and ready to roll! 🥐✨"
  - Watch-Only: "👁️ New display pastry 'name' in the showcase! Gorgeous to look at! 🪟✨"
  - From Backup: "📦 Vintage pastry 'name' restored from the recipe book! ✨"
  - Más energéticos y celebratorios que antes
  - Mantienen el tema de panadería consistente
- **🎨 Sistema de feedback visual mejorado**: Barra de estatus con colores dinámicos según el tipo de mensaje
  - ✓ **Success (Verde)**: Mensajes de éxito con borde verde (#22c55e) y fondo oscuro verde
  - ⚠️ **Warning (Amarillo)**: Advertencias con borde amarillo (#eab308) y fondo oscuro amarillo
  - ❌ **Error (Rojo)**: Errores con borde rojo (#ef4444) y fondo oscuro rojo
  - ℹ️ **Info (Azul)**: Información con borde azul (#3b82f6) y fondo oscuro azul
  - Transición suave de 5 segundos antes de volver al estado default
  - Checkmark (✓) agregado a todos los mensajes de éxito
- **Aplicación de estilos visuales**:
  - ✓ Import exitoso: Borde verde + checkmark
  - ✓ Backup exitoso: Borde verde + checkmark + ruta del archivo
  - ⚠️ Delete exitoso: Borde amarillo + checkmark (acción destructiva exitosa)
  - ❌ Errores de import/backup/delete: Borde rojo
  - Auto-revert a estado normal después de 5 segundos
- **📋 Panel de detalles de transacciones mejorado**: Información completa con formato compacto
  - **Formato compacto**: Label y valor en la misma línea (excepto Hash y TzKT link)
  - **Date**: Fecha y hora completa en una línea
  - **From**: Dirección origen completa en una línea
  - **To**: Dirección destino completa en una línea
  - **Amount**: Cantidad con color (verde para IN, rojo para OUT) en una línea
  - **Baker**: Dirección completa del baker en una línea (si aplica)
  - **Hash**: Hash completo en 2 líneas (label + valor) para mejor legibilidad
  - **TzKT Explorer**: URL completa en 2 líneas (label + URL) como texto copiable
  - Scroll vertical automático si el contenido excede el espacio
  - Optimizado para mostrar más información en menos espacio
- **🎨 Logo optimizado**: Reducido de 7 líneas a 3 líneas para ganar espacio vertical
  - Espacio vertical adicional disponible para detalles de transacciones y lista de wallets
  - Mantiene la estética retro del diseño original
  - No afecta el grid interno de la aplicación
- **📏 Espaciado consistente en lista de wallets**: Interlineado compacto como en panel de detalles
  - `margin-bottom: 0` mantenido para consistencia visual
  - Alineación y padding aplicados sin separación excesiva
  - Estilo compacto similar al resto de la información de wallet
- **🎨 Ventanas modales optimizadas**: Ancho dinámico en todos los modales
  - Todos los modales usan `width: auto` para ajustarse al contenido presentado
  - Afecta a 13 modales: Confirm, Prompt, Network, Address, Import, Wallet Selector, Backup, Delete, Receive, TxDetails, ConfirmSend, Destination
  - Separación de botones mediante padding estándar de Textual
- **📋 Lista de transacciones simplificada**: Hash eliminado de la lista para mejor alineación
  - Hash ya visible en panel de detalles (lado derecho)
  - Formato simplificado: `[Hora] [DIR] [Monto] ↔ [Dirección]`
  - Eliminado separador `│` y columna de hash
  - Mejor alineación vertical y menos información redundante
  - Dirección de counterparty ahora más visible (10...8 chars en vez de 8...6)
- **📊 Headers de columnas en historial**: Títulos agregados a ambos paneles de transacciones
  - Panel izquierdo: "Time  ↕  Amount  ↔  Destination"
  - Panel derecho: "Extra Details"
  - Símbolos de dirección mejorados:
    - Header usa ↕ (flecha arriba-abajo) en lugar de "DIR"
    - Contenido usa ↑ (flecha arriba = IN) y ↓ (flecha abajo = OUT)
    - Más compacto e intuitivo visualmente
  - "Destination" en lugar de "Address" para mayor claridad
  - Ambos headers perfectamente alineados horizontalmente en la misma fila
  - Usa fila existente sin modificar layout vertical
  - Estilo consistente con header de lista de wallets (color accent, background surface)
  - Panel izquierdo: padding izquierdo de 2 para alineación con contenido del ListView
  - Panel derecho: padding izquierdo de 1 con borde izquierdo (border-left)
  - Todo alineado a la izquierda (headers y contenido)

### 🐛 Corregido
- **Error de markup en link TzKT**: Corregido `MarkupError` en panel de detalles de transacción
  - Textual no soporta URLs con `://` dentro del markup `[link=]`
  - Cambiado a mostrar URL como texto plano copiable
  - Formato: `TzKT Explorer: https://tzkt.io/[hash]`
  - Usuario puede copiar la URL completa directamente desde el panel
- **Alineación de tabla de wallets**: Línea vertical del header ahora coincide con contenido
  - Header tenía 28 caracteres antes del separador │, contenido usa 30
  - Agregados 2 espacios adicionales para alineación perfecta
  - Formato consistente: 30 caracteres para nombre + " │ " + dirección
- **File picker removido**: Eliminado botón "Browse" que causaba crashes del terminal
  - Tkinter file picker era incompatible con aplicaciones TUI
  - Causaba que la aplicación se cerrara inesperadamente
  - **Solución**: Entrada manual de ruta con placeholder mejorado
  - Placeholder muestra ruta sugerida completa del directorio de backups
  - Soporte completo para `~`, rutas relativas y absolutas
  - Experiencia más estable y consistente con TUI

### 📝 Documentación
- Actualizado `IMPORT_FLOW.md` con sección de backup import (pendiente)
- Actualizado `README.md` con instrucciones de backup import (pendiente)

---

## [1.2.0] - 2026-01-21

### ✨ Añadido
- **Derivación automática de direcciones**: La app ahora deriva automáticamente la dirección pública desde la clave privada
  - Elimina paso redundante de ingresar dirección manualmente
  - Reduce errores de "address mismatch"
  - Flujo más rápido: 3 pasos en vez de 4
- **Tema de panadería consistente**: Mensajes divertidos en todas las operaciones
  - Importar: "🥐 Fresh wallet baked to perfection!"
  - Backup: "📦 Wallet recipe saved!"
  - Eliminar: "🔥 Burned like toast!"
  - Estados de transacción: Ya implementados previamente
- **Guía de importación**: Nueva documentación `IMPORT_FLOW.md` con ejemplos visuales

### 🔧 Mejorado
- **Flujo de importación optimizado**:
  - Con clave privada: Nombre → Clave → Passphrase (dirección derivada automáticamente)
  - Watch-only: Nombre → [Skip clave] → Dirección
- **Mensajes de cancelación** más divertidos con tema de panadería
- **Diálogo de confirmación** para eliminar wallet con tema "burn"
- **Ventanas modales**: Todas ajustadas con tamaños dinámicos (width: auto)
- **Padding consistente**: Aumentado de 1 a 2 en todas las ventanas modales

### 📝 Documentación
- `IMPORT_FLOW.md`: Guía completa del nuevo flujo de importación
- FAQ sobre derivación de direcciones
- Comparación visual del flujo antiguo vs nuevo

---

## [1.1.1] - 2026-01-21

### 🐛 Corregido
- **Error de CSS**: Eliminada propiedad `font-family` no soportada por Textual
  - Las fuentes se configuran en la TERMINAL, no en la app
  - La app hereda automáticamente la fuente de tu terminal
  - Documentación actualizada para aclarar este comportamiento

### 📝 Mejorado
- **JetBrains Mono**: Agregada como opción principal (como Claude Terminal)
- **FONTS.md**: Aclarado que fuentes se configuran en terminal
- **install_retro_fonts.sh**: Mensaje más claro sobre configuración
- **README.md**: Instrucciones actualizadas

---

## [1.1.0] - 2026-01-21

### ✨ Añadido
- **Documentación de fuentes**: Guías para configurar fuentes en terminal
  - JetBrains Mono como fuente principal recomendada (como Claude Terminal)
  - IBM Plex Mono para look retro auténtico
  - VT323 para vintage terminal
  - Guía completa de instalación en `FONTS.md`
  - Script automático de instalación: `install_retro_fonts.sh`

- **Padding mejorado en UI**: Separación visual consistente
  - Padding izquierdo de 2 espacios en todas las listas
  - Padding en módulo de información de wallet
  - Padding en selectores y modales
  - Mejor alineación vertical del contenido

- **Documentación completa**:
  - `README.md`: Guía de usuario completa
  - `FONTS.md`: Guía de configuración de fuentes retro
  - `CHANGELOG.md`: Este archivo
  - `install_retro_fonts.sh`: Instalador automático de fuentes

### 🔧 Mejorado
- Alineación de columnas en tabla de wallets
- Consistencia visual en todos los componentes
- Separación lógica del contenido de los bordes

### 📝 Notas
- Las fuentes se configuran mediante CSS en la aplicación
- La apariencia final depende de la configuración de la terminal
- Se recomienda instalar IBM Plex Mono para la mejor experiencia

---

## [1.0.0] - 2026-01-21

### 🎉 Lanzamiento Inicial

#### ✨ Características Principales
- **Sistema de logging estructurado**
  - 48 excepciones envueltas con logging
  - Logs detallados en `logs/wallet.log`
  - No expone stack traces al usuario
  - Rotación automática de logs (10MB)

- **Thread safety completo**
  - 4 RLocks implementados
  - Protección de store, selected, history_cache, balance_cache
  - Helpers thread-safe: `_get_selected()`, `_set_selected()`
  - Eliminación de 6 race conditions

- **Gestión de recursos**
  - Timeouts consolidados en Config
  - Timer cleanup en `on_unmount()`
  - Prevención de resource leaks

- **Type hints mejorados**
  - TypedDict para estructuras de datos
  - Return types anotados
  - Cobertura +15% (~60% → ~75%)

- **Constantes consolidadas**
  - 9 RPC URLs en Config
  - 8 timeouts en Config
  - Single source of truth

#### 🔒 Seguridad
- Cifrado AES-256-GCM para claves privadas
- Key derivation con Argon2id
- Almacenamiento seguro en `~/.config/tezos_tui_wallet/`

#### 💰 Funcionalidades de Wallet
- Crear, importar, y eliminar wallets
- Ver balance en tiempo real
- Historial de transacciones
- Enviar XTZ con estimación de fees
- Soporte para watch-only addresses
- Delegación y staking info
- Multi-red (Mainnet/Ghostnet)

#### 🎨 Interfaz de Usuario
- TUI moderna con Textual
- Navegación por teclado completa
- Shortcuts intuitivos
- Modales para confirmaciones
- Actualización en tiempo real
- ASCII art logo retro

#### 🧪 Testing
- 37 tests automatizados (100% passing)
- 5 fases de validación
- Test suite completo
- Checklist de testing manual

#### 📚 Documentación
- `REFACTORING_SUMMARY.md`: Documentación técnica completa
- Tests de validación por fase
- Master test suite
- Deployment checklist

---

## [Unreleased]

### 🔮 Planeado para futuras versiones

#### v1.2.0 (Próximo)
- [ ] Soporte para hardware wallets (Ledger)
- [ ] Exportar historial a CSV
- [ ] Configuración de colores personalizables
- [ ] Más temas retro (amber, green, blue)

#### v1.3.0
- [ ] Multi-asset support (tokens FA1.2/FA2)
- [ ] Address book persistente
- [ ] Etiquetas personalizadas para transacciones
- [ ] Gráficos de balance histórico

#### v2.0.0
- [ ] Soporte para NFTs
- [ ] Integration con DeFi protocols
- [ ] Modo offline para signing
- [ ] Mobile companion app

---

## 📝 Formato del Changelog

Este changelog sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/lang/es/).

### Tipos de cambios
- `Añadido` para nuevas funcionalidades
- `Cambiado` para cambios en funcionalidad existente
- `Obsoleto` para funcionalidades que serán removidas
- `Removido` para funcionalidades removidas
- `Corregido` para corrección de bugs
- `Seguridad` para vulnerabilidades corregidas

---

Mantenido por: TUI Tezos Wallet Team
Última actualización: 2026-01-21
