#!/bin/bash
# Script para instalar fuentes retro recomendadas para TUI Tezos Wallet

set -e

echo "======================================================================"
echo "  🖥️  Instalador de Fuentes para TUI Tezos Wallet"
echo "======================================================================"
echo ""
echo "⚠️  IMPORTANTE: Las fuentes se configuran en tu TERMINAL, no en la app"
echo ""

# Detectar distribución
if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO=$ID
else
    echo "❌ No se pudo detectar la distribución de Linux"
    exit 1
fi

echo "📋 Sistema detectado: $PRETTY_NAME"
echo ""

# Función para verificar si una fuente está instalada
check_font() {
    if fc-list | grep -qi "$1"; then
        echo "✅ $1 ya está instalada"
        return 0
    else
        echo "❌ $1 no está instalada"
        return 1
    fi
}

# Verificar fuentes actuales
echo "🔍 Verificando fuentes instaladas..."
echo ""

check_font "JetBrains Mono" && JETBRAINS_INSTALLED=1 || JETBRAINS_INSTALLED=0
check_font "IBM Plex Mono" && IBM_INSTALLED=1 || IBM_INSTALLED=0
check_font "VT323" && VT_INSTALLED=1 || VT_INSTALLED=0

echo ""

# Si todas están instaladas, salir
if [ $JETBRAINS_INSTALLED -eq 1 ] && [ $IBM_INSTALLED -eq 1 ] && [ $VT_INSTALLED -eq 1 ]; then
    echo "🎉 ¡Todas las fuentes recomendadas ya están instaladas!"
    echo ""
    echo "Configura tu terminal para usar una de estas fuentes:"
    echo "  • JetBrains Mono (como Claude Terminal - recomendada)"
    echo "  • IBM Plex Mono (retro auténtico)"
    echo "  • VT323 (vintage terminal)"
    echo ""
    exit 0
fi

echo "📦 Instalando fuentes faltantes..."
echo ""

# Función para instalar JetBrains Mono
install_jetbrains_mono() {
    case $DISTRO in
        ubuntu|debian|linuxmint|pop)
            echo "🔧 Instalando JetBrains Mono via apt..."
            sudo apt update
            sudo apt install -y fonts-jetbrains-mono
            ;;
        fedora|rhel|centos)
            echo "🔧 Instalando JetBrains Mono via dnf..."
            sudo dnf install -y jetbrains-mono-fonts
            ;;
        arch|manjaro)
            echo "🔧 Instalando JetBrains Mono via pacman..."
            sudo pacman -S --noconfirm ttf-jetbrains-mono
            ;;
        opensuse*)
            echo "🔧 Instalando JetBrains Mono via zypper..."
            sudo zypper install -y jetbrains-mono-fonts
            ;;
        *)
            echo "⚠️  Instalación manual de JetBrains Mono..."
            install_jetbrains_mono_manual
            ;;
    esac
}

# Instalación manual de JetBrains Mono
install_jetbrains_mono_manual() {
    echo "📥 Descargando JetBrains Mono..."
    TEMP_DIR=$(mktemp -d)
    cd "$TEMP_DIR"

    wget -q --show-progress https://github.com/JetBrains/JetBrainsMono/releases/download/v2.304/JetBrainsMono-2.304.zip

    echo "📦 Extrayendo archivos..."
    unzip -q JetBrainsMono-2.304.zip

    echo "💾 Instalando fuentes..."
    mkdir -p ~/.local/share/fonts/jetbrains-mono
    cp fonts/ttf/*.ttf ~/.local/share/fonts/jetbrains-mono/

    echo "🧹 Limpiando archivos temporales..."
    cd ~
    rm -rf "$TEMP_DIR"
}

# Función para instalar IBM Plex Mono
install_ibm_plex() {
    case $DISTRO in
        ubuntu|debian|linuxmint|pop)
            echo "🔧 Instalando IBM Plex Mono via apt..."
            sudo apt update
            sudo apt install -y fonts-ibm-plex
            ;;
        fedora|rhel|centos)
            echo "🔧 Instalando IBM Plex Mono via dnf..."
            sudo dnf install -y ibm-plex-fonts
            ;;
        arch|manjaro)
            echo "🔧 Instalando IBM Plex Mono via pacman..."
            sudo pacman -S --noconfirm ttf-ibm-plex
            ;;
        opensuse*)
            echo "🔧 Instalando IBM Plex Mono via zypper..."
            sudo zypper install -y ibm-plex-fonts
            ;;
        *)
            echo "⚠️  Instalación manual de IBM Plex Mono..."
            install_ibm_plex_manual
            ;;
    esac
}

# Instalación manual de IBM Plex Mono
install_ibm_plex_manual() {
    echo "📥 Descargando IBM Plex Mono..."
    TEMP_DIR=$(mktemp -d)
    cd "$TEMP_DIR"

    wget -q --show-progress https://github.com/IBM/plex/releases/download/v6.4.0/OpenType.zip

    echo "📦 Extrayendo archivos..."
    unzip -q OpenType.zip

    echo "💾 Instalando fuentes..."
    mkdir -p ~/.local/share/fonts/ibm-plex
    cp OpenType/IBM-Plex-Mono/*.otf ~/.local/share/fonts/ibm-plex/

    echo "🧹 Limpiando archivos temporales..."
    cd ~
    rm -rf "$TEMP_DIR"
}

# Función para instalar VT323
install_vt323() {
    case $DISTRO in
        ubuntu|debian|linuxmint|pop)
            echo "🔧 Instalando VT323 via apt..."
            sudo apt update
            sudo apt install -y fonts-vt323
            ;;
        *)
            echo "⚠️  Instalación manual de VT323..."
            mkdir -p ~/.local/share/fonts
            cd ~/.local/share/fonts
            wget -q --show-progress https://github.com/google/fonts/raw/main/ofl/vt323/VT323-Regular.ttf
            ;;
    esac
}

# Función para instalar Anonymous Pro
install_anonymous_pro() {
    case $DISTRO in
        ubuntu|debian|linuxmint|pop)
            echo "🔧 Instalando Anonymous Pro via apt..."
            sudo apt update
            sudo apt install -y fonts-anonymous-pro
            ;;
        fedora|rhel|centos)
            echo "🔧 Instalando Anonymous Pro via dnf..."
            sudo dnf install -y anonymous-pro-fonts
            ;;
        arch|manjaro)
            echo "🔧 Instalando Anonymous Pro via pacman..."
            sudo pacman -S --noconfirm ttf-anonymous-pro
            ;;
        *)
            echo "⚠️  Instalación manual de Anonymous Pro..."
            mkdir -p ~/.local/share/fonts
            cd ~/.local/share/fonts
            wget -q --show-progress https://www.marksimonson.com/assets/content/fonts/AnonymousPro-1.002.zip
            unzip -q AnonymousPro-1.002.zip
            cp "Anonymous Pro"*.ttf .
            rm AnonymousPro-1.002.zip
            ;;
    esac
}

# Instalar fuentes faltantes
if [ $JETBRAINS_INSTALLED -eq 0 ]; then
    echo "📍 Instalando JetBrains Mono..."
    install_jetbrains_mono
    echo "✅ JetBrains Mono instalada"
    echo ""
fi

if [ $IBM_INSTALLED -eq 0 ]; then
    echo "📍 Instalando IBM Plex Mono..."
    install_ibm_plex
    echo "✅ IBM Plex Mono instalada"
    echo ""
fi

if [ $VT_INSTALLED -eq 0 ]; then
    echo "📍 Instalando VT323..."
    install_vt323
    echo "✅ VT323 instalada"
    echo ""
fi

# Actualizar caché de fuentes
echo "🔄 Actualizando caché de fuentes..."
fc-cache -f -v > /dev/null 2>&1

echo ""
echo "======================================================================"
echo "  ✅ Instalación completada exitosamente!"
echo "======================================================================"
echo ""
echo "📋 Fuentes instaladas:"
check_font "JetBrains Mono"
check_font "IBM Plex Mono"
check_font "VT323"
echo ""
echo "🎨 Próximos pasos:"
echo ""
echo "1. ⚠️  IMPORTANTE: Configura tu TERMINAL para usar una fuente:"
echo "   • JetBrains Mono Regular 11pt (como Claude Terminal - recomendada)"
echo "   • IBM Plex Mono Medium 11pt (retro auténtico)"
echo "   • VT323 Regular 13pt (vintage terminal)"
echo ""
echo "2. Reinicia tu terminal para aplicar la fuente"
echo ""
echo "3. Ver guía completa: cat FONTS.md"
echo ""
echo "4. Ejecutar la aplicación: python3 app.py"
echo ""
echo "💡 Recuerda: Las aplicaciones TUI heredan la fuente de tu terminal."
echo "   No puedes cambiar la fuente desde la app, solo desde tu terminal."
echo ""
echo "======================================================================"
