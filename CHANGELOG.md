# 📋 Changelog - Sassy Wallet

All notable changes to this project are documented in this file.

---

## [1.3.0] - 2026-01-21

### 🎉 Official Branding: Sassy Wallet
- **New official ASCII logo**: "Sassy Wallet" in figlet style
- Reflects the sassy, bold, and defiant personality of the wallet
- Represents the motivational and fun attitude across all message systems

### ✨ Added
- **🎭 Bakery Message Library**: Dynamic messages for operations
  - 10+ variations for each context (RPC, transactions, refresh, import, backup, delete)
  - 35+ different spinner/loading messages
  - Modular and extensible system
- **💪 Motivational Staking System**: Messages based on user behavior
  - 💪 **CHAD** (15 messages): For wallets with active staking - Celebratory in GREEN
  - 😴 **BORING** (15 messages): For wallets only delegating - Neutral with sarcasm in YELLOW
  - 😂 **LAZY** (22 messages): For wallets without participation - Ironic in RED
  - Psychological color system for positive reinforcement
- **💰 Balance Tier Message System**: Messages adapt to balance AND behavior
  - 6 balance tiers: DUST (0-1), BROKE (1-100), SAVER (100-500), INVESTOR (500-1K), BABY WHALE (1K-5K), WHALE (5K+)
  - 3 states per tier: Staking, Delegating, Lazy
  - 150 unique messages distributed across 18 categories
  - Gamification of the complete balance system
- **🚨 Empty Wallet Messages**: Fun messages when no wallets are imported
  - 30 unique messages with personality and humor
  - Clear call to action: all mention "Press 'i' to import"
- **Import from Backup**: New option to restore wallets from JSON backup files
  - Interactive type selector with 3 options
  - Complete backup structure validation
  - Automatic restoration of recent destinations

### 🔧 Improved
- **🌊 Breathing Glow Effect**: Visual feedback during XTZ sending
  - "Breathing" effect with bright/dim orange alternation
  - 0.8 second cycle for smooth, non-intrusive effect
- **Consistent Modal Button Spacing**: All buttons within modal windows have same spacing
- **Enhanced Status Feedback**: Dynamic colored status bar
  - ✓ Success (Green), ⚠️ Warning (Yellow), ❌ Error (Red), ℹ️ Info (Blue)
  - Smooth 5-second transition before returning to default state
- **Compact Transaction Details Panel**: Complete information in compact format
- **Optimized Logo**: Reduced from 7 lines to 3 for more vertical space
- **Optimized Modal Windows**: Dynamic width in all modals

---

## [1.2.0] - 2026-01-21

### ✨ Added
- **Automatic Address Derivation**: App now derives public address from private key
  - Eliminates redundant step of manually entering address
  - Reduces "address mismatch" errors
  - Faster flow: 3 steps instead of 4
- **Consistent Bakery Theme**: Fun messages across all operations
  - Import: "🥐 Fresh wallet baked to perfection!"
  - Backup: "📦 Wallet recipe saved!"
  - Delete: "🔥 Burned like toast!"

### 🔧 Improved
- **Optimized Import Flow**:
  - With private key: Name → Key → Passphrase (address derived automatically)
  - Watch-only: Name → [Skip key] → Address

---

## [1.1.0] - 2026-01-21

### ✨ Added
- **Font Documentation**: Guides for configuring fonts in terminal
  - JetBrains Mono as main recommended font (like Claude Terminal)
  - IBM Plex Mono for authentic retro look
  - Complete installation guide
- **Improved UI Padding**: Consistent visual separation
  - 2-space left padding on all lists
  - Better vertical content alignment

---

## [1.0.0] - 2026-01-21

### 🎉 Initial Release

#### ✨ Main Features
- **Structured Logging System**
  - 48 exceptions wrapped with logging
  - Detailed logs in `logs/wallet.log`
  - Automatic log rotation (10MB)
- **Complete Thread Safety**
  - 4 RLocks implemented
  - Thread-safe helpers
  - Elimination of 6 race conditions
- **Resource Management**
  - Timeouts consolidated in Config
  - Timer cleanup in `on_unmount()`
  - Resource leak prevention
- **Improved Type Hints**
  - TypedDict for data structures
  - Annotated return types
  - ~75% coverage

#### 🔒 Security
- AES-256-GCM encryption for private keys
- Argon2id key derivation
- Secure storage in `~/.config/tezos_tui_wallet/`

#### 💰 Wallet Functionalities
- Create, import, and delete wallets
- Real-time balance view
- Transaction history
- Send XTZ with fee estimation
- Watch-only address support
- Delegation and staking info
- Multi-network (Mainnet/Ghostnet)

#### 🎨 User Interface
- Modern TUI with Textual
- Complete keyboard navigation
- Intuitive shortcuts
- Confirmation modals
- Real-time updates
- Retro ASCII art logo

#### 🧪 Testing
- 37 automated tests (100% passing)
- 5 validation phases
- Complete test suite

---

## 📝 Changelog Format

This changelog follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

### Change Types
- `Added` for new features
- `Changed` for changes to existing functionality
- `Deprecated` for features that will be removed
- `Removed` for removed features
- `Fixed` for bug fixes
- `Security` for fixed vulnerabilities

---

Maintained by: Sassy Wallet Team
Last updated: 2026-01-22
