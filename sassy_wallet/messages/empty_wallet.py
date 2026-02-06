"""
Empty wallet messages for TUI Tezos Wallet.

This module provides fun, motivational messages to encourage importing a wallet
when the user first opens the app with no wallets configured.

Message Categories:
- 🚨 EMPTY: Funny, ironic messages encouraging the user to import a wallet
"""

import secrets

# ============================================================================
# NO WALLETS IMPORTED: EMPTY MESSAGES 🚨
# ============================================================================

EMPTY_WALLET_MESSAGES = [
    "🚨 Import a wallet for god sake! This bakery needs customers! ¬¬",
    "😭 It's SO empty in here! Press 'i' to import and fill this void!",
    "🏜️ Tumbleweed rolling by... Import a wallet, please! Press 'i'! ¬¬",
    "🤷 No wallets? Really? Come on, press 'i' to get started! ¬¬",
    "🥐 This bakery is dead without croissants — import them now from France! 🇫🇷",
    "🎪 Welcome to the circus of NOTHING! Press 'i' to add a wallet! ¬¬",
    "😂 You opened a wallet app... with NO wallets. Bold move! ¬¬",
    "🦗 *Cricket sounds* ... Import a wallet? Maybe? Press 'i'? ¬¬",
    "🚫 ERROR 404: Wallets not found. Press 'i' to fix this tragedy!",
    "🥺 I'm begging you... just ONE wallet? Press 'i'! Pretty please?",
    "⚰️ This app is literally useless without wallets. Press 'i' to revive it! ¬¬",
    "🤡 Running a wallet app with no wallets? That's some clown energy! ¬¬",
    "🏚️ Empty shelves, empty dreams. Import a wallet to start baking! ¬¬",
    "😴 Nothing to see here... because there's NOTHING! Press 'i'! ¬¬",
    "🌵 Desert vibes. No wallets, no life. Import one already! ¬¬",
    "📦 This box is EMPTY! Time to unpack some wallets! Press 'i'!",
    "🎻 Playing the world's smallest violin for your empty wallet list. ¬¬",
    "🦴 Bone dry. No wallets. Not even one. Press 'i' to hydrate! ¬¬",
    "👻 BOO! Just kidding, there's nothing here. Import a wallet! ¬¬",
    "🎭 The show can't start without actors! Import a wallet (press 'i')!",
    "💤 Zzzz... wake me up when you import a wallet. Press 'i'! ¬¬",
    "🔔 DING DING! Reminder: This app needs wallets! Press 'i'!",
    "🚀 Ready to launch... but there's no fuel! Import a wallet! ¬¬",
    "🎯 Mission: Import a wallet. Status: Not started. Press 'i'! ¬¬",
    "🏁 Race starts when you import a wallet! Ready, set... press 'i'!",
    "🎨 This canvas is blank. Paint it with wallets! Press 'i'!",
    "📍 You are here: Nowhere. Import a wallet to start your journey! ¬¬",
    "🔮 The crystal ball shows... NOTHING! Import a wallet to change fate! ¬¬",
    "⏰ Time is ticking... and you STILL have no wallets! Press 'i'! ¬¬",
    "🎬 ACTION! Except there's no action because NO WALLETS! Press 'i'! ¬¬",
    "🍃 Light as a feather... because NOTHING is here! Press 'i'! ¬¬",
    "🎪 Step right up to see... absolutely nothing! Import a wallet! ¬¬",
    "🏚️ Abandoned warehouse vibes. Import something, anything! ¬¬",
    "🎮 Game over before it even started. Press 'i' to continue! ¬¬",
    "🪦 RIP to your crypto journey... that never started. Press 'i'! ¬¬",
]

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_empty_wallet_message() -> str:
    """
    Get a random empty wallet message to encourage importing a wallet.

    Returns:
        A random motivational/funny message string

    Example:
        >>> get_empty_wallet_message()
        "🚨 Import a wallet for god sake! This bakery needs customers!"
    """
    return secrets.choice(EMPTY_WALLET_MESSAGES)


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    print("🚨 Empty Wallet Messages Library Test\n")

    print("SAMPLE MESSAGES (5 random):")
    for i in range(5):
        print(f"  {i+1}. {get_empty_wallet_message()}")
        print()

    print("\n📊 Statistics:")
    print(f"  Total messages: {len(EMPTY_WALLET_MESSAGES)}")
    print("\n💡 Tip: All messages encourage pressing 'i' to import a wallet!")
