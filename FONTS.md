# 🖥️ Fuentes Retro Recomendadas para TUI Tezos Wallet

Este documento describe cómo configurar fuentes retro en tu terminal para obtener la mejor experiencia nostálgica con la aplicación.

---

## ⚠️ IMPORTANTE: Cómo Funcionan las Fuentes en TUI

**Las aplicaciones TUI (Terminal User Interface) heredan la fuente de tu terminal.**

- ✅ La fuente se configura en la **TERMINAL** (GNOME Terminal, Kitty, Alacritty, etc.)
- ❌ La aplicación **NO puede** cambiar la fuente por sí misma
- 🔄 Cualquier cambio de fuente requiere configurar tu terminal y reiniciar la app

---

## 🎨 Fuentes Retro Recomendadas

Estas son las mejores fuentes monoespaciadas para una experiencia retro:

1. **IBM Plex Mono** (Recomendada ⭐) - Estilo IBM terminal años 80/90
2. **JetBrains Mono** (Moderna retro) - La que usa Claude Terminal
3. **Fira Code** (Con ligaduras) - Popular entre desarrolladores
4. **Monaco** (Retro Mac) - Clásica de macOS
5. **Courier New** (Clásica) - Máquina de escribir
6. **Menlo** (macOS default) - Limpia y legible

---

## 📦 Instalación de Fuentes Recomendadas

### JetBrains Mono (Como Claude Terminal ⭐)

**Estilo:** Moderna, limpia, perfecta legibilidad
**Por qué:** La fuente que usa Claude Terminal, diseñada específicamente para código

#### Ubuntu/Debian
```bash
sudo apt install fonts-jetbrains-mono
```

#### Arch Linux
```bash
sudo pacman -S ttf-jetbrains-mono
```

#### Fedora
```bash
sudo dnf install jetbrains-mono-fonts
```

#### Manual (cualquier distribución)
```bash
# Descargar última versión
cd /tmp
wget https://github.com/JetBrains/JetBrainsMono/releases/download/v2.304/JetBrainsMono-2.304.zip
unzip JetBrainsMono-2.304.zip
mkdir -p ~/.local/share/fonts/jetbrains-mono
cp fonts/ttf/*.ttf ~/.local/share/fonts/jetbrains-mono/
fc-cache -f -v
```

---

### IBM Plex Mono (Retro auténtico)

**Estilo:** Terminal IBM de los años 80/90
**Por qué:** Diseñada por IBM, perfecta para terminales retro

#### Ubuntu/Debian
```bash
sudo apt install fonts-ibm-plex
```

#### Arch Linux
```bash
sudo pacman -S ttf-ibm-plex
```

#### Fedora
```bash
sudo dnf install ibm-plex-fonts
```

#### Manual (cualquier distribución)
```bash
# Descargar desde GitHub
wget https://github.com/IBM/plex/releases/download/v6.4.0/OpenType.zip
unzip OpenType.zip
mkdir -p ~/.local/share/fonts/ibm-plex
cp OpenType/IBM-Plex-Mono/*.otf ~/.local/share/fonts/ibm-plex/
fc-cache -f -v
```

---

### Otras Fuentes Retro Populares

#### VT323 (Terminal VT vintage)
```bash
# Ubuntu/Debian
sudo apt install fonts-vt323

# Manual
mkdir -p ~/.local/share/fonts
cd ~/.local/share/fonts
wget https://github.com/google/fonts/raw/main/ofl/vt323/VT323-Regular.ttf
fc-cache -f -v
```

#### Anonymous Pro (Diseñada para programadores)
```bash
# Ubuntu/Debian
sudo apt install fonts-anonymous-pro

# Manual
mkdir -p ~/.local/share/fonts
cd ~/.local/share/fonts
wget https://www.marksimonson.com/assets/content/fonts/AnonymousPro-1.002.zip
unzip AnonymousPro-1.002.zip
cp Anonymous\ Pro\ *.ttf .
fc-cache -f -v
```

#### Inconsolata (Terminal minimalista retro)
```bash
# Ubuntu/Debian
sudo apt install fonts-inconsolata
```

---

## ⚙️ Configurar la Terminal

### GNOME Terminal
1. Abrir Terminal
2. Menú → Preferencias
3. Perfiles → Editar perfil actual
4. Pestaña "Texto"
5. Desmarcar "Usar fuente del sistema"
6. Seleccionar: **IBM Plex Mono Medium 11** (o tu preferida)

### Kitty Terminal
Editar `~/.config/kitty/kitty.conf`:
```bash
font_family      IBM Plex Mono
bold_font        IBM Plex Mono Bold
italic_font      IBM Plex Mono Italic
bold_italic_font IBM Plex Mono Bold Italic
font_size        11.0
```

### Alacritty Terminal
Editar `~/.config/alacritty/alacritty.yml`:
```yaml
font:
  normal:
    family: "IBM Plex Mono"
    style: Regular
  bold:
    family: "IBM Plex Mono"
    style: Bold
  italic:
    family: "IBM Plex Mono"
    style: Italic
  size: 11.0
```

### Tilix
1. Preferencias → Perfil
2. Fuente personalizada
3. Seleccionar: **IBM Plex Mono 11**

---

## 🎯 Configuración Óptima Retro

### Tamaño de Fuente Recomendado
- **11-12pt**: Balance perfecto entre legibilidad y estética retro
- **10pt**: Más denso, estilo terminal antiguo
- **13-14pt**: Más cómodo para sesiones largas

### Colores de Terminal Retro (opcional)

#### Esquema "IBM 3278" (Verde sobre negro)
```bash
# Para GNOME Terminal
dconf write /org/gnome/terminal/legacy/profiles:/:b1dcc9dd-5262-4d8d-a863-c897e6d979b9/background-color "'#000000'"
dconf write /org/gnome/terminal/legacy/profiles:/:b1dcc9dd-5262-4d8d-a863-c897e6d979b9/foreground-color "'#00ff00'"
```

#### Esquema "Amber Monitor" (Ámbar sobre negro)
- Background: `#000000`
- Foreground: `#ffb000`

#### Esquema "Matrix" (Verde brillante)
- Background: `#0d0208`
- Foreground: `#00ff41`

---

## 🔍 Verificar Fuentes Instaladas

```bash
# Listar todas las fuentes monoespaciadas
fc-list :mono | grep -i "plex\|courier\|monaco\|consolas"

# Verificar IBM Plex Mono específicamente
fc-list | grep "IBM Plex Mono"
```

---

## 🚀 Aplicar Cambios

Después de instalar nuevas fuentes:

```bash
# Actualizar caché de fuentes
fc-cache -f -v

# Reiniciar terminal
# Luego ejecutar:
python3 app.py
```

---

## 💡 Tips de Experiencia Retro

1. **Pantalla completa**: Usa `F11` en tu terminal para experiencia inmersiva
2. **Sin barras**: Oculta barras de menú/título para look más limpio
3. **Transparencia**: 5-10% de transparencia puede dar toque retro CRT
4. **Líneas escaneo**: Algunos terminales permiten efectos de líneas de escaneo

---

## 🐛 Solución de Problemas

### La fuente no cambia
- Verifica que la fuente esté instalada: `fc-list | grep "IBM"`
- Reinicia la terminal completamente
- Verifica configuración de perfil de terminal

### Caracteres se ven raros
- Algunas fuentes no tienen todos los glifos Unicode
- Usa IBM Plex Mono que tiene soporte completo

### Tamaño incorrecto
- Ajusta en configuración de terminal, no en la app
- El tamaño se hereda de la configuración de terminal

---

## 📚 Recursos Adicionales

- [IBM Plex Repository](https://github.com/IBM/plex)
- [Google Fonts - Monospace](https://fonts.google.com/?category=Monospace)
- [Nerd Fonts](https://www.nerdfonts.com/) - Fuentes con iconos adicionales

---

## 💡 Configuraciones Recomendadas

### Opción 1: Como Claude Terminal (Recomendada ⭐)
```
Fuente: JetBrains Mono Regular
Tamaño: 11-12pt
Terminal: Cualquiera (Kitty, Alacritty, GNOME Terminal)
Esquema: Dark (default del sistema)
```

### Opción 2: Retro Auténtico
```
Fuente: IBM Plex Mono Medium
Tamaño: 11pt
Terminal: Kitty o Alacritty
Esquema: Dark o Green on Black (IBM 3278)
```

### Opción 3: Vintage Terminal
```
Fuente: VT323 Regular
Tamaño: 13pt (necesita ser más grande)
Terminal: Cualquiera
Esquema: Amber o Green on Black
```

---

## 🔧 Recuerda

- ✅ **Configura la fuente en tu TERMINAL, no en la app**
- ✅ **Reinicia la terminal** después de instalar fuentes
- ✅ **Reinicia la app** para ver los cambios
- ✅ La app heredará automáticamente la fuente de tu terminal

---

Generado: 2026-01-21
Proyecto: TUI Tezos Wallet
Actualizado: 2026-01-21 (Corregido: fuentes se configuran en terminal)
