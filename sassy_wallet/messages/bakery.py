"""
Bakery-themed messages for TUI Tezos Wallet.

This module provides a collection of fun, bakery-themed messages organized by context.
Messages are randomly selected to add variety and personality to the wallet experience.

Metaphor Guide:
- 🔥 OVEN: Used for operations being PROCESSED (transactions, RPC capabilities)
- 🪟 DISPLAY/SHELF: Used for COMPLETED data (history, balance, refresh)
"""

import random
from typing import Literal

# ============================================================================
# RPC WELCOME MESSAGES
# ============================================================================

RPC_OVEN_HOT = [
    "🔥 RPC oven is hot and ready! Bakers waiting to process any pastry you throw at 'em, baby! 🥐✨",
    "🔥 Oven preheated to perfection! Bakers standing by with their mitts ready! 🧑‍🍳✨",
    "🔥 RPC oven blazing! The bakers are pumped and ready to work their magic! 🥖🔥",
    "🔥 Temperature's just right! Bakers eager to turn your dough into gold! 💰🥐",
    "🔥 Oven's fired up! Bakers got their aprons on and flour everywhere! Let's bake! 👨‍🍳✨",
    "🔥 RPC oven smokin' hot! Bakers ready to make your transactions rise like sourdough! 🍞🚀",
    "🔥 Perfect baking conditions! Bakers flexing those kneading muscles! 💪🥖",
    "🔥 Oven temperature: IDEAL! Bakers sharpening their spatulas for action! 🔪🥐",
    "🔥 RPC kitchen is OPEN! Head bakers ready to cook up some blockchain magic! ✨👨‍🍳",
    "🔥 Oven roaring! Bakers caffeinated and ready to process at lightning speed! ☕⚡",
]

RPC_OVEN_WARM = [
    "⚡ RPC oven is warm but can't preview the dough! Blind baking mode enabled! ¬¬ 🥖",
    "⚡ Oven's hot but the window's foggy! Baking without peeking - trust the process! ¬¬ 🪟🥐",
    "⚡ Warm oven, no preview! Like baking with your eyes closed - adventurous! ¬¬ 😎🍞",
    "⚡ Oven ready but no test batches! Going in blind - baker's instinct mode! ¬¬ 🎯🥖",
    "⚡ Can bake but can't taste-test first! Living on the edge, baker style! 🤘🥐",
    "⚡ Oven's cooking but the timer's broken! Trusting your baker's intuition! ¬¬ ⏰✨",
    "⚡ Heat's there but no thermometer! Old-school baking vibes! ¬¬ 🌡️🥖",
    "⚡ Oven works but no taste testing! What could go wrong? ¬¬ 😬🥖",
    "⚡ Baking blind! Hope the recipe's right... ¬¬ 🤞🥐",
]

RPC_DISPLAY_ONLY = [
    "🪟 RPC oven is display-only! Window shopping at the bakery! ¬¬ 👀",
    "🪟 Glass case mode! You can look but can't touch the pastries! ¬¬ 🥐👁️",
    "🪟 Bakery showcase only! All the goodies behind glass! ¬¬ ✨🪟",
    "🪟 Display shelf activated! Admire the bread, don't buy the bread! ¬¬ 🍞😅",
    "🪟 Window browsing mode! Like a food court on a diet! ¬¬ 👀🥐",
    "🪟 Exhibition only! Museum of delicious pastries - no sampling! ¬¬ 🖼️🥖",
    "🪟 Showroom vibes! Everything's pretty but hands off! ¬¬ 🙅‍♀️✨",
    "🪟 Read-only bakery! Eyes only, no touching! ¬¬ 👁️🥖",
    "🪟 Spectator mode! Watch other people eat bread! ¬¬ 😑🍞",
]

RPC_CHECKING = [
    "🔍 Checking if the oven is preheated…",
    "🔍 Testing oven temperature…",
    "🔍 Knocking on the bakery door…",
    "🔍 Asking the bakers if they're ready…",
    "🔍 Checking the baker's schedule…",
    "🔍 Seeing if the ovens are fired up…",
    "🔍 Verifying baker availability…",
]

# ============================================================================
# TRANSACTION PROCESSING MESSAGES (OVEN - being processed)
# ============================================================================

TX_PREPARING = [
    "🥖 Preparing your dough for the oven…",
    "🥐 Gathering ingredients for your pastry…",
    "🍞 Measuring flour for your transaction…",
    "👨‍🍳 Baker reviewing your recipe…",
    "📋 Checking the order slip…",
    "🥣 Mixing your transaction batter…",
    "⚖️ Weighing the dough precisely…",
]

TX_KNEADING = [
    "💪 Kneading the dough with love…",
    "🙌 Working that blockchain dough…",
    "🥖 Stretching and folding your transaction…",
    "👐 Punching down the dough…",
    "💫 Massaging the smart contract…",
    "🔄 Rolling out your XTZ…",
    "✨ Tenderizing your transfer…",
]

TX_INTO_OVEN = [
    "🔥 Sliding the tray into the oven…",
    "🚪 Into the blazing oven it goes!",
    "🔥 Transaction entering the heat zone…",
    "🌡️ Oven door closing… let's bake!",
    "🔥 Your pastry's in the hot seat now!",
    "🚀 Sending it to the fire pit!",
    "🔥 Into the inferno! 🔥",
]

TX_BAKING = [
    "⏰ Baking in progress… smells amazing!",
    "🔥 Watching it rise and brown…",
    "🍞 Transaction getting that golden crust…",
    "✨ Caramelizing to perfection…",
    "🥐 Layers forming beautifully…",
    "🌡️ Temperature's perfect, time's ticking…",
    "👨‍🍳 Baker's keeping a close eye…",
    "⏳ Almost there… patience, young baker!",
]

TX_DONE = [
    "✨ Baked to perfection! Golden and crispy! 🥐",
    "🎉 Fresh out the oven! Still warm! 🍞",
    "🏆 Masterpiece achieved! Chef's kiss! 👨‍🍳💋",
    "🥇 Perfect bake! The baker's proud! 🥖✨",
    "💯 Transaction completed! Smells heavenly! 🥐",
    "🎊 It's ready! Grab it while it's hot! 🔥🍞",
    "✅ Beautifully browned! Transaction complete! 🥖",
    "🌟 Perfection on a plate! Well done! 🥐✨",
]

# ============================================================================
# REFRESH MESSAGES (DISPLAY - viewing completed data)
# ============================================================================

REFRESH_CHECKING = [
    "🪟 Checking the display shelf…",
    "🧹 Dusting off the showcase…",
    "👀 Peeking at the bakery window…",
    "✨ Polishing the glass case…",
    "🪟 Inspecting the pastry lineup…",
    "🔍 Reading the price tags…",
    "📋 Reviewing today's selection…",
    "🧼 Wiping down the shelves…",
]

REFRESH_SUCCESS = [
    "✨ Display shelf refreshed! Fresh pastries on view! 🥐",
    "🪟 Showcase updated! Look at all those beauties! 🥖",
    "✨ Glass case sparkling! Everything's on display! 🍞",
    "🎉 Shelf restocked! New items visible! 🥐",
    "🪟 Window cleaned! Crystal clear view of your XTZ! 💎",
    "✨ Display revamped! Pastries looking gorgeous! 🥖",
    "🧹 Shelves dusted! Your history shining bright! ✨",
    "🪟 Showcase refreshed! Come see what's new! 🥐",
]

# ============================================================================
# SPINNER MESSAGES (GENERIC LOADING)
# ============================================================================

SPINNER_MESSAGES = [
    "Counting tez... 🪙",
    "Asking the blockchain nicely... 🙏",
    "Waking up the baker... ¬¬ 👨‍🍳",
    "Preheating the oven... 🔥",
    "Kneading the dough... 🥖",
    "Baking fresh blocks... 🍞",
    "Rolling croissants... 🥐",
    "Sprinkling flour on validators... 👨‍🍳",
    "Brewing some blockchain coffee... ☕",
    "Teaching octopuses to count... ¬¬ 🐙",
    "Consulting the Tezos oracle... 🔮",
    "Spinning the hamster wheel... ¬¬ 🐹",
    "Defrosting frozen tokens... ❄️",
    "Negotiating with smart contracts... ¬¬ 🤝",
    "Rolling the dice... 🎲",
    "Summoning blockchain spirits... 👻",
    "Polishing your XTZ... ✨",
    "Feeding the validators... 🍕",
    "Untangling the blockchain... 🧶",
    "Charging flux capacitor... ⚡",
    "Mixing the sourdough starter... 🧑‍🍳",
    "Letting the dough rise... ⏰",
    "Dusting the display shelf... 🧹✨",
    "Adding yeast to the network... 🧪",
    "Folding napkins at the bakery... ¬¬ 🧺",
    "Arranging croissants artistically... 🎨🥐",
    "Sifting the blockchain flour... 🌾",
    "Proofing the dough... ⏱️",
    "Glazing the donuts... 🍩",
    "Buttering the baguettes... 🧈🥖",
    "Setting the oven timer... ⏰",
    "Cleaning the mixing bowls... 🥣",
    "Sharpening the bread knife... 🔪",
    "Reading ancient baking scrolls... 📜",
    "Summoning the sourdough spirits... 👻🍞",
    "Convincing nodes to cooperate... ¬¬ 🤷",
    "Bribing the validators with cookies... ¬¬ 🍪",
    "Waiting for blockchain to wake up... ¬¬ 💤",
    "Explaining crypto to grandma... ¬¬ 👵",
    "Herding digital cats... ¬¬ 🐱",
    "Debugging the universe... ¬¬ 🌌",
    "Reticulating splines... ¬¬ 📐",
    "Calculating the meaning of XTZ... ¬¬ 🤔",
]

# ============================================================================
# BAKER/DELEGATION MESSAGES (for delegation operations)
# ============================================================================

BAKER_MESSAGES = [
    "🔥 Baking is happening... The baker is working hard!",
    "👨‍🍳 Baker preparing your delegation... Stand by!",
    "🥖 The bakery is firing up... Delegation in progress!",
    "🍞 Fresh delegation baking in the oven...",
    "⏰ Baker is on it! Your XTZ is being delegated...",
    "🔥 Ovens at full power! Delegation cooking...",
    "👑 Connecting you to your chosen baker...",
    "💪 Baker accepting your delegation... Almost there!",
    "🌟 The baking league is processing your request...",
    "⚡ Baker network activating... Delegation incoming!",
    "🥐 Your XTZ is joining the baker's batch...",
    "🎯 Locking in your baker choice... Processing!",
    "🔥 Hot delegation action! Baker standing by!",
    "👨‍🍳 Master baker reviewing your delegation...",
    "🍞 Blockchain bakery hard at work!",
]

# ============================================================================
# WALLET LOADING MESSAGES (for stake screen wallet info loading)
# ============================================================================

WALLET_LOADING = [
    "Waking up the baker... 👨‍🍳💤",
    "Consulting the blockchain... 🔮",
    "Counting XTZ... 🪙✨",
    "Checking staking status... ⚡",
    "Asking bakers nicely... 🙏🥖",
    "Summoning delegation info... 📡",
    "Brewing blockchain data... ☕",
    "Defrosting frozen stats... ❄️🔥",
    "Interrogating smart contracts... 🤔",
    "Negotiating with RPC... 🤝",
    "Polishing the numbers... ✨",
    "Teaching octopuses to count... 🐙",
    "Rolling the blockchain dice... 🎲",
    "Feeding the validators... 🍕",
    "Reading ancient ledgers... 📜",
    "Untangling the network... 🧶",
    "Spinning the hamster wheel... 🐹⚡",
    "Charging flux capacitor... ⚡🔋",
    "Summoning tez spirits... 👻💰",
    "Dusting off the ledger... 🧹",
    "Preheating the RPC oven... 🔥",
    "Mixing delegation data... 🥣",
    "Kneading the blockchain... 🥖",
    "Proofing the smart contracts... ⏱️",
    "Glazing the statistics... 🍩✨",
    "Sifting through blocks... 🌾",
    "Folding transaction history... 🧺",
    "Arranging data artistically... 🎨",
    "Buttering up the baker... 🧈👨‍🍳",
]

# ============================================================================
# IMPORT MESSAGES
# ============================================================================

IMPORT_SECRET_KEY = [
    "🎉 New pastry '{name}' fresh from the oven! Golden-brown and ready to roll! 🥐✨",
    "🥖 Hot and fresh! '{name}' just came out of the oven! Full wallet powers unlocked! 🔥",
    "🥐 Introducing '{name}'! Freshly baked with love! Ready to send and receive! ✨",
    "🍞 Warm welcome to '{name}'! Straight from the baker's table! Full power mode! 💪",
    "🎊 '{name}' has entered the bakery! Steaming hot and ready for action! 🥖🔥",
    "✨ Fresh batch alert! '{name}' is ready to conquer the blockchain! 🥐💰",
    "🥖 '{name}' rolled in hot! Baker's special with all the features! 🌟",
]

IMPORT_WATCH_ONLY = [
    "👁️ New display pastry '{name}' in the showcase! Gorgeous to look at! 🪟✨",
    "🪟 '{name}' added to the glass case! Window shopping mode activated! 👀🥐",
    "👀 Showcase item '{name}' on display! Beautiful but hands-off! 🥖✨",
    "🪟 '{name}' behind glass! Admire from afar, no touching! 👁️🥐",
    "✨ Display-only '{name}' in the window! Eye candy mode! 🪟🍞",
    "👁️ '{name}' on exhibition! Watch-only wallet vibes! 🎨🥖",
]

IMPORT_FROM_BACKUP = [
    "📦 Vintage pastry '{name}' restored from the recipe book! ✨",
    "🥖 Reheated from the pantry! '{name}' back in business! 🔥",
    "📚 Old recipe restored! '{name}' fresh from the archives! 🥐",
    "♻️ '{name}' back from storage! Good as new! 🍞✨",
    "📦 Unboxed '{name}' from the vault! Ready to bake again! 🥖",
    "🎉 '{name}' restored! Like it never left the bakery! 🥐✨",
]

IMPORT_CANCELLED = [
    "↩️ Import cancelled - No dough, no bread! ¬¬ 🍞",
    "🚫 Import aborted - Oven stays empty! ¬¬ 🔥",
    "↩️ Cancelled - The dough stays in storage! ¬¬ 📦",
    "🛑 Import stopped - No pastries today! ¬¬ 🥐",
    "↩️ Backing out - Kitchen remains closed! ¬¬ 👨‍🍳",
    "🚫 Nevermind! The bakery stays walletless! ¬¬ 🏚️",
    "↩️ Changed your mind? Classic! ¬¬ 🤷",
    "🛑 Import aborted! The oven sighs in relief! ¬¬ 😮‍💨",
]

# ============================================================================
# BACKUP MESSAGES
# ============================================================================

BACKUP_SUCCESS = [
    "✓ 📦 Wallet recipe saved! '{name}' packaged fresh in the pantry! 🥖",
    "✓ 💾 '{name}' backed up! Recipe book updated! 📚✨",
    "✓ 🥐 '{name}' preserved for posterity! Safe in the vault! 🔒",
    "✓ 📦 Backup complete! '{name}' recipe secured! 🥖✨",
    "✓ 💾 '{name}' saved! Your dough is protected! 🍞🔐",
    "✓ 📚 Recipe archived! '{name}' safe and sound! 🥐✨",
]

# ============================================================================
# DELETE MESSAGES
# ============================================================================

DELETE_SUCCESS = [
    "✓ 🔥 Wallet '{name}' returned to the oven! Burned like toast - crispy and gone forever! 🍞💨",
    "✓ 🔥 '{name}' incinerated! Back to ashes! Nothing left but crumbs! 💥",
    "✓ 🗑️ '{name}' tossed! Stale bread in the bin! 🥖🚮",
    "✓ 🔥 '{name}' burnt to a crisp! Charcoal mode activated! 💨",
    "✓ 🗑️ Wallet '{name}' discarded! Yesterday's bread! 🍞",
    "✓ 🔥 '{name}' torched! Not even crumbs remain! 💥🔥",
    "✓ 🗑️ '{name}' deleted! Composted for the blockchain! ♻️🥖",
]

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

MessageContext = Literal[
    "rpc_hot", "rpc_warm", "rpc_display", "rpc_checking",
    "tx_preparing", "tx_kneading", "tx_into_oven", "tx_baking", "tx_done",
    "refresh_checking", "refresh_success",
    "spinner",
    "import_secret", "import_watch", "import_backup", "import_cancel",
    "backup_success",
    "delete_success"
]

def get_message(context: MessageContext, **kwargs) -> str:
    """
    Get a random message for the specified context.

    Args:
        context: The message context (e.g., "rpc_hot", "tx_baking")
        **kwargs: Optional formatting arguments (e.g., name="My Wallet")

    Returns:
        A formatted message string

    Example:
        >>> get_message("import_secret", name="My Wallet")
        "🎉 New pastry 'My Wallet' fresh from the oven! ..."
    """
    messages_map = {
        "rpc_hot": RPC_OVEN_HOT,
        "rpc_warm": RPC_OVEN_WARM,
        "rpc_display": RPC_DISPLAY_ONLY,
        "rpc_checking": RPC_CHECKING,
        "tx_preparing": TX_PREPARING,
        "tx_kneading": TX_KNEADING,
        "tx_into_oven": TX_INTO_OVEN,
        "tx_baking": TX_BAKING,
        "tx_done": TX_DONE,
        "refresh_checking": REFRESH_CHECKING,
        "refresh_success": REFRESH_SUCCESS,
        "spinner": SPINNER_MESSAGES,
        "baker": BAKER_MESSAGES,
        "import_secret": IMPORT_SECRET_KEY,
        "import_watch": IMPORT_WATCH_ONLY,
        "import_backup": IMPORT_FROM_BACKUP,
        "import_cancel": IMPORT_CANCELLED,
        "backup_success": BACKUP_SUCCESS,
        "delete_success": DELETE_SUCCESS,
    }

    messages = messages_map.get(context, ["Message not found"])
    message = random.choice(messages)

    # Format with kwargs if provided
    if kwargs:
        try:
            message = message.format(**kwargs)
        except KeyError:
            # If formatting fails, return unformatted
            pass

    return message


def get_spinner_message() -> str:
    """Get a random spinner/loading message."""
    return random.choice(SPINNER_MESSAGES)


def get_baker_message() -> str:
    """Get a random baker/delegation message."""
    return random.choice(BAKER_MESSAGES)


def get_wallet_loading_message() -> str:
    """Get a random wallet loading message for stake screen."""
    return random.choice(WALLET_LOADING)


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    print("🥖 Bakery Messages Library Test\n")

    contexts = [
        ("rpc_hot", {}),
        ("rpc_checking", {}),
        ("tx_baking", {}),
        ("tx_done", {}),
        ("refresh_success", {}),
        ("import_secret", {"name": "Test Wallet"}),
        ("backup_success", {"name": "Test Wallet"}),
        ("delete_success", {"name": "Test Wallet"}),
        ("spinner", {}),
    ]

    for context, kwargs in contexts:
        print(f"{context}:")
        print(f"  {get_message(context, **kwargs)}")
        print()
