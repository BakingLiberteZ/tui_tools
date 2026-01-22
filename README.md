# 💅 Sassy Wallet

A bold Tezos wallet with attitude. Not just managing your XTZ, but motivating you, challenging you, and making you smile with dynamic comments based on your balance, delegation, and staking behavior. Features a retro TUI interface with unique personality.

![Version](https://img.shields.io/badge/version-1.3.0-blue)
![Python](https://img.shields.io/badge/python-3.10+-green)
![License](https://img.shields.io/badge/license-MIT-yellow)

---

## ✨ Features

- 💅 **Sassy Personality**: Fun comments based on your balance, staking, and delegation
- 🎭 **Motivational Messages**: Categorized message system (CHAD/BORING/LAZY) with psychological colors
- 🔐 **Security**: AES-256 encryption for private keys
- 🌐 **Multi-network**: Support for Mainnet and Ghostnet
- 💰 **Complete Management**: View balance, history, send XTZ
- 🎨 **Retro Interface**: Nostalgic design with monospaced fonts
- ⚡ **Fast**: Optimized operations with smart caching
- 🔒 **Thread-safe**: Protection against race conditions
- 📝 **Structured Logging**: Easy debugging without exposing sensitive info

---

## 🚀 Installation

### Requirements

- Python 3.10 or higher
- pip (Python package manager)

### Option 1: Install from Source (Recommended for Development)

```bash
# Clone the repository
git clone https://github.com/BakingLiberteZ/tui-tezos-wallet.git
cd tui-tezos-wallet

# Install in development mode
pip install -e .

# Run the application
sassy-wallet
```

### Option 2: Install as Package

```bash
# Clone and install
git clone https://github.com/BakingLiberteZ/tui-tezos-wallet.git
cd tui-tezos-wallet
pip install .

# Run from anywhere
sassy-wallet
```

### Option 3: Run Directly (Without Installation)

```bash
# Clone the repository
git clone https://github.com/BakingLiberteZ/tui-tezos-wallet.git
cd tui-tezos-wallet

# Install dependencies
pip install -r requirements.txt

# Run as module
python -m sassy_wallet
```

---

## 🎨 Font Configuration

⚠️ **IMPORTANT:** TUI applications inherit the font from your terminal. You must configure the font in your terminal (GNOME Terminal, Kitty, Alacritty, etc.), not in the app.

**Recommended Fonts (in order of preference):**
1. **JetBrains Mono** ⭐ (Like Claude Terminal - recommended)
2. **IBM Plex Mono** (Authentic retro - IBM terminal style)
3. **VT323** (Vintage - simulates VT terminals)

### Quick Installation (Ubuntu/Debian)

```bash
# JetBrains Mono (recommended - like Claude Terminal)
sudo apt install fonts-jetbrains-mono

# Or IBM Plex Mono for authentic retro look
sudo apt install fonts-ibm-plex

# Or VT323 for more vintage look
sudo apt install fonts-vt323

# Update font cache
fc-cache -f -v
```

**After installation:**
1. Configure your terminal to use the font
2. Restart the terminal
3. Run `python3 app.py`

---

## 📋 Usage

### Main Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `i` | Import/Create wallet |
| `b` | Backup wallet |
| `Del` | Delete wallet |
| `s` | Send XTZ |
| `r` | Receive (show address) |
| `n` | Change network (Mainnet/Ghostnet) |
| `m` | View all transactions |
| `↑/↓` | Navigate lists |
| `Enter` | Select |
| `Esc` | Back/Cancel |
| `q` | Quit |

### First Time

Press `i` to open the import selector. Choose your method:

1. **🔑 Import with Secret Key (Private key):**
   - Enter wallet name
   - Enter your private key (edsk...)
   - 🔮 **Address is automatically derived!**
   - Create a password to encrypt
   - ✨ Done! Full wallet imported

2. **👀 Watch-Only (Monitoring only):**
   - Enter wallet name
   - Enter a Tezos address (tz1/tz2/tz3/tz4)
   - 👀 You can view balance/history without sending

3. **📦 From Backup (Restore):**
   - Enter the path to the backup JSON file
   - The app validates and extracts the data
   - Confirm or rename the wallet
   - 🥖 Wallet restored with all its data!
   - Recent destinations are also restored

**🎯 Advantage:** You no longer need to manually enter your address when you have the private key. The app calculates it for you!

### Send XTZ

1. Select the source wallet
2. Press `s`
3. Enter destination address
4. Enter amount
5. Select fee level (Low/Medium/High)
6. Confirm and enter password

### View Transactions

- The last 5 transactions are shown automatically
- Press `m` to view full history
- Use `↑/↓` to navigate
- Press `Enter` to view transaction details
- Click on hash to open in TzKT explorer

---

## 🔒 Security

### Encryption

- **Algorithm**: AES-256-GCM
- **Key Derivation**: Argon2id (GPU/ASIC resistant)
- **Storage**: `~/.config/tezos_tui_wallet/store.json`

### Best Practices

✅ **Do:**
- Use strong passwords (12+ characters)
- Make regular backups of your seed phrase
- Store seed offline and secure
- Test sends on Ghostnet first

❌ **Don't:**
- Don't share your seed phrase
- Don't store seed in plain text digitally
- Don't use the same password in multiple places
- Don't ignore network warnings

---

## 📊 Architecture

### Project Structure

```
sassy-wallet/
├── sassy_wallet/               # Main package
│   ├── __init__.py            # Package initialization
│   ├── __main__.py            # CLI entry point
│   ├── ui/                    # User interface
│   │   ├── __init__.py
│   │   └── app.py             # Textual TUI application
│   ├── core/                  # Core functionality
│   │   ├── __init__.py
│   │   ├── crypto.py          # AES-256 encryption
│   │   ├── logger.py          # Structured logging
│   │   ├── store.py           # Data persistence
│   │   └── tezos.py           # Blockchain interaction
│   ├── messages/              # Dynamic message systems
│   │   ├── __init__.py
│   │   ├── bakery.py          # Operation messages
│   │   ├── balance.py         # Balance tier messages
│   │   ├── staking.py         # Staking messages
│   │   ├── empty_wallet.py    # Empty wallet messages
│   │   └── modal.py           # Modal messages
│   └── assets/
│       └── logo.txt           # ASCII logo
├── tests/                     # Test suite
│   ├── __init__.py
│   └── test_basic.py
├── .github/
│   └── workflows/
│       └── python-app.yml     # CI/CD pipeline
├── LICENSE                    # MIT License
├── README.md                  # This file
├── CHANGELOG.md               # Version history
├── pyproject.toml             # Modern Python packaging
├── setup.py                   # Backward compatibility
└── requirements.txt           # Dependencies
```

### Main Dependencies

- **Textual**: Modern TUI framework
- **PyTezos**: Tezos client for Python
- **Cryptography**: AES-256 encryption
- **Argon2-cffi**: Secure key derivation

---

## 🧪 Testing

### Run Automated Tests

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=sassy_wallet --cov-report=term-missing

# Run specific test
pytest tests/test_basic.py -v
```

### Manual Testing (Ghostnet)

Use Ghostnet for testing before using on Mainnet. Press `n` to switch networks.

### CI/CD

The project includes GitHub Actions for automated testing on Python 3.10, 3.11, and 3.12.

---

## 📝 Logs and Debugging

Logs are saved in `logs/wallet.log` with automatic rotation (max 10MB).

```bash
# View logs in real-time
tail -f logs/wallet.log

# View last lines
tail -50 logs/wallet.log

# Search errors
grep ERROR logs/wallet.log
```

**Note:** Logs contain detailed debugging information but NEVER include private keys or passwords.

---

## 🐛 Troubleshooting

### App Won't Start

```bash
# Verify dependencies
pip install -r requirements.txt

# Verify Python
python3 --version  # Must be 3.10+

# View logs
cat logs/wallet.log
```

### RPC Connection Error

- Check your internet connection
- Change network: press `n`
- Wait and retry: public RPCs can be busy

### Balance Not Updating

- Press `F5` to force refresh
- Verify you're on the correct network
- Changes may take 30 seconds to appear

### Transaction Not Showing

- Transactions take ~30 seconds to confirm
- Press `m` to view full history
- Check on TzKT explorer (click on hash)

---

## 🤝 Contributing

### Report Bugs

1. Verify it's reproducible
2. Include `logs/wallet.log` (check for sensitive info)
3. Describe steps to reproduce
4. Include your Python and OS version

### Development

```bash
# Clone repository
git clone https://github.com/BakingLiberteZ/tui-tezos-wallet.git
cd tui-tezos-wallet

# Install dependencies
pip install -r requirements.txt

# Run tests
python3 test_all_phases.py

# Make changes...

# Verify tests pass
python3 test_all_phases.py
```

---

## 📄 License

MIT License - See LICENSE file for details.

---

## 🙏 Credits

- **PyTezos**: Tezos client for Python
- **Textual**: TUI framework by Textualize
- **IBM Plex**: Retro font by IBM
- **TzKT**: Blockchain explorer API

---

## 🔗 Useful Links

- [Tezos Documentation](https://tezos.com/developers/)
- [TzKT Explorer](https://tzkt.io/)
- [Textual Framework](https://textual.textualize.io/)
- [PyTezos Docs](https://pytezos.org/)

---

## 📞 Support

For support, please:
1. Check the logs in `logs/wallet.log`
2. Review existing GitHub issues
3. Open a new issue with complete details

---

**💅 Enjoy your Sassy Wallet with attitude!**

*"A wallet with an attitude"* 💅

Generated: 2026-01-22
Version: 1.3.0
