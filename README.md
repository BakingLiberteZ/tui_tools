# 💅 Sassy Wallet

Una billetera de Tezos atrevida con actitud. No solo gestiona tus XTZ, sino que te motiva, te reta y te saca sonrisas con comentarios según tu balance, delegación y staking. Con interfaz TUI retro y personalidad única.

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.10+-green)
![License](https://img.shields.io/badge/license-MIT-yellow)

---

## ✨ Características

- 💅 **Personalidad Sassy**: Comentarios divertidos según tu balance, staking y delegación
- 🎭 **Mensajes Motivacionales**: Sistema de mensajes categorizados (CHAD/BORING/LAZY) con colores psicológicos
- 🔐 **Seguridad**: Cifrado AES-256 para claves privadas
- 🌐 **Multi-red**: Soporte para Mainnet y Ghostnet
- 💰 **Gestión completa**: Ver balance, historial, enviar XTZ
- 🎨 **Interfaz retro**: Diseño nostálgico con fuentes monoespaciadas
- ⚡ **Rápido**: Operaciones optimizadas con caché inteligente
- 🔒 **Thread-safe**: Protección contra race conditions
- 📝 **Logging estructurado**: Debugging fácil sin exponer información sensible

---

## 🚀 Instalación

### Requisitos

- Python 3.10 o superior
- pip (gestor de paquetes de Python)

### Instalar dependencias

```bash
pip install -r requirements.txt
```

### Ejecutar la aplicación

```bash
python3 app.py
```

---

## 🎨 Configuración de Fuentes

⚠️ **IMPORTANTE:** Las aplicaciones TUI heredan la fuente de tu terminal. Debes configurar la fuente en tu terminal (GNOME Terminal, Kitty, Alacritty, etc.), no en la app.

**Fuentes recomendadas (en orden de preferencia):**
1. **JetBrains Mono** ⭐ (Como Claude Terminal - recomendada)
2. **IBM Plex Mono** (Retro auténtico - estilo IBM terminal)
3. **VT323** (Vintage - simula terminales VT)

### Instalación rápida (Ubuntu/Debian)

```bash
# JetBrains Mono (recomendada - como Claude Terminal)
sudo apt install fonts-jetbrains-mono

# O IBM Plex Mono para look retro auténtico
sudo apt install fonts-ibm-plex

# O VT323 para look más vintage
sudo apt install fonts-vt323

# Actualizar caché de fuentes
fc-cache -f -v
```

**Después de instalar:**
1. Configura tu terminal para usar la fuente
2. Reinicia la terminal
3. Ejecuta `python3 app.py`

**📖 Guía completa:** Ver [FONTS.md](FONTS.md) para instrucciones detalladas de instalación y configuración por terminal.

---

## 📋 Uso

### Teclas de atajo principales

| Tecla | Acción |
|-------|--------|
| `i` | Importar/Crear wallet |
| `b` | Backup wallet |
| `Del` | Eliminar wallet |
| `s` | Enviar XTZ |
| `r` | Recibir (mostrar dirección) |
| `n` | Cambiar red (Mainnet/Ghostnet) |
| `m` | Ver todas las transacciones |
| `↑/↓` | Navegar listas |
| `Enter` | Seleccionar |
| `Esc` | Volver/Cancelar |
| `q` | Salir |

### Primera vez

Presiona `i` para abrir el selector de importación. Elige tu método:

1. **🔑 Importar con Secret Key (Clave privada):**
   - Ingresa nombre de wallet
   - Ingresa tu clave privada (edsk...)
   - 🔮 **La dirección se deriva automáticamente!**
   - Crea una contraseña para cifrar
   - ✨ ¡Listo! Wallet completa e importada

2. **👀 Watch-Only (Solo monitoreo):**
   - Ingresa nombre de wallet
   - Ingresa una dirección de Tezos (tz1/tz2/tz3/tz4)
   - 👀 Podrás ver balance/historial sin poder enviar

3. **📦 Desde Backup (Restaurar):**
   - Ingresa la ruta al archivo de backup JSON
   - La app valida y extrae los datos
   - Confirma o renombra la wallet
   - 🥖 Wallet restaurada con todos sus datos!
   - Los destinos recientes también se restauran

**🎯 Ventaja:** Ya no necesitas ingresar tu dirección manualmente cuando tienes la clave privada. La app la calcula por ti!

### Enviar XTZ

1. Selecciona la wallet origen
2. Presiona `s`
3. Ingresa dirección destino
4. Ingresa cantidad
5. Selecciona nivel de fee (Low/Medium/High)
6. Confirma y ingresa contraseña

### Ver transacciones

- Las últimas 5 transacciones se muestran automáticamente
- Presiona `m` para ver historial completo
- Usa `↑/↓` para navegar
- Presiona `Enter` para ver detalles de una transacción
- Click en hash para abrir en TzKT explorer

---

## 🔒 Seguridad

### Cifrado

- **Algoritmo**: AES-256-GCM
- **Key Derivation**: Argon2id (resistente a GPU/ASIC)
- **Almacenamiento**: `~/.config/tezos_tui_wallet/store.json`

### Buenas prácticas

✅ **Hacer:**
- Usa contraseñas fuertes (12+ caracteres)
- Haz backup regular de tu frase semilla
- Guarda la semilla offline y segura
- Prueba envíos en Ghostnet primero

❌ **No hacer:**
- No compartas tu frase semilla
- No guardes la semilla en texto plano digital
- No uses la misma contraseña en múltiples lugares
- No ignores advertencias de red

---

## 📊 Arquitectura

### Estructura del proyecto

```
sassy-wallet/
├── app.py                      # Aplicación principal (UI + lógica)
├── wallet/
│   ├── crypto.py              # Cifrado AES-256
│   ├── logger.py              # Sistema de logging estructurado
│   ├── store.py               # Persistencia de datos
│   └── tezos.py               # Interacción con blockchain
├── bakery_messages.py         # Mensajes dinámicos para operaciones
├── staking_messages.py        # Mensajes motivacionales de staking (CHAD/BORING/LAZY)
├── balance_messages.py        # Mensajes según tier de balance
├── empty_wallet_messages.py   # Mensajes para wallets vacías
├── logs/
│   └── wallet.log             # Logs de depuración
├── test_*.py                  # Tests de validación
├── FONTS.md                   # Guía de configuración de fuentes
├── REFACTORING_SUMMARY.md     # Documentación técnica
└── README.md                  # Este archivo
```

### Dependencias principales

- **Textual**: Framework TUI moderno
- **PyTezos**: Cliente de Tezos para Python
- **Cryptography**: Cifrado AES-256
- **Argon2-cffi**: Key derivation segura

---

## 🧪 Testing

### Ejecutar tests automatizados

```bash
# Todos los tests (37 tests)
python3 test_all_phases.py

# Tests individuales
python3 test_phase1_complete.py  # Logging
python3 test_phase2_complete.py  # Thread safety
python3 test_phase3_complete.py  # Timeouts
python3 test_phase4_complete.py  # Type hints
python3 test_phase5_complete.py  # Constants
```

### Testing manual (Ghostnet)

Ver [REFACTORING_SUMMARY.md](REFACTORING_SUMMARY.md) sección "Deployment Checklist" para checklist completo.

---

## 📝 Logs y Debugging

Los logs se guardan en `logs/wallet.log` con rotación automática (max 10MB).

```bash
# Ver logs en tiempo real
tail -f logs/wallet.log

# Ver últimas líneas
tail -50 logs/wallet.log

# Buscar errores
grep ERROR logs/wallet.log
```

**Nota:** Los logs contienen información detallada de debugging pero NUNCA incluyen claves privadas ni contraseñas.

---

## 🐛 Solución de Problemas

### App no inicia

```bash
# Verificar dependencias
pip install -r requirements.txt

# Verificar Python
python3 --version  # Debe ser 3.10+

# Ver logs
cat logs/wallet.log
```

### Error de conexión RPC

- Verifica tu conexión a internet
- Cambia de red: presiona `n`
- Espera y reintenta: los RPCs públicos pueden estar ocupados

### Balance no actualiza

- Presiona `F5` para forzar refresh
- Verifica que estés en la red correcta
- Los cambios pueden tardar 30 segundos en aparecer

### Transacción no aparece

- Las transacciones tardan ~30 segundos en confirmarse
- Presiona `m` para ver historial completo
- Verifica en TzKT explorer (click en hash)

---

## 🤝 Contribuir

### Reportar bugs

1. Verifica que sea reproducible
2. Incluye `logs/wallet.log` (revisa que no tenga info sensible)
3. Describe pasos para reproducir
4. Incluye tu versión de Python y OS

### Desarrollo

```bash
# Clonar repositorio
git clone <repo-url>
cd tui-tezos-wallet

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar tests
python3 test_all_phases.py

# Hacer cambios...

# Verificar que tests pasen
python3 test_all_phases.py
```

---

## 📄 Licencia

MIT License - Ver archivo LICENSE para detalles.

---

## 🙏 Créditos

- **PyTezos**: Cliente de Tezos para Python
- **Textual**: Framework TUI por Textualize
- **IBM Plex**: Fuente retro por IBM
- **TzKT**: API de blockchain explorer

---

## 🔗 Links Útiles

- [Documentación de Tezos](https://tezos.com/developers/)
- [TzKT Explorer](https://tzkt.io/)
- [Textual Framework](https://textual.textualize.io/)
- [PyTezos Docs](https://pytezos.org/)

---

## 📞 Soporte

Para soporte, por favor:
1. Revisa [REFACTORING_SUMMARY.md](REFACTORING_SUMMARY.md)
2. Consulta [FONTS.md](FONTS.md) para problemas de fuentes
3. Revisa logs en `logs/wallet.log`
4. Abre un issue con detalles completos

---

**💅 ¡Disfruta tu Sassy Wallet con actitud!**

*"A wallet with an attitude"* 💅

Generado: 2026-01-22
Versión: 1.3.0
