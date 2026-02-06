"""
Baker commentary messages based on baker size.

Provides fun, educational messages that encourage decentralization
by promoting delegation to smaller bakers.
"""

import secrets
from typing import Optional
from decimal import Decimal


# Baker tiers based on staking balance (in XTZ)
TIER_MICRO = "micro"          # < 10,000 XTZ
TIER_SMALL = "small"          # 10,000 - 50,000 XTZ
TIER_MEDIUM = "medium"        # 50,000 - 100,000 XTZ
TIER_LARGE = "large"          # 100,000 - 250,000 XTZ
TIER_VERY_LARGE = "very_large"  # 250,000 - 500,000 XTZ
TIER_WHALE = "whale"          # > 500,000 XTZ


def get_baker_tier(baker_balance_xtz: Decimal) -> str:
    """
    Categorize a baker based on their staking balance.

    Args:
        baker_balance_xtz: Baker's total staking balance in XTZ

    Returns:
        Tier identifier string
    """
    balance = baker_balance_xtz

    if balance < 10_000:
        return TIER_MICRO
    elif balance < 50_000:
        return TIER_SMALL
    elif balance < 100_000:
        return TIER_MEDIUM
    elif balance < 250_000:
        return TIER_LARGE
    elif balance < 500_000:
        return TIER_VERY_LARGE
    else:
        return TIER_WHALE


# Messages for each tier
_MESSAGES = {
    TIER_MICRO: [
        # Very encouraging - heroes of decentralization
        "🌱 **Community hero detected!** Small bakers are the backbone of Tezos!",
        "💪 **What a chad move!** Supporting micro bakers = peak decentralization",
        "✨ **Absolute legend!** You're helping bootstrap a community baker",
        "🎯 **Gigabrain choice!** Small bakers need heroes like you",
        "🌟 **This is the way!** Grassroots baking keeps Tezos healthy",
        "🔥 **Based and decentralization-pilled!** Micro bakers appreciate you!",
        "👑 **King/Queen of decentralization!** Every small baker starts somewhere",
        "💎 **Diamond hands move!** Supporting the little guy is epic",
        "🚀 **To the moon together!** Small bakers, big impact",
        "🎊 **Celebration mode!** You're making Tezos more resilient",
    ],

    TIER_SMALL: [
        # Encouraging - great for the network
        "🌿 **Excellent choice!** Small bakers are gems for decentralization",
        "👏 **Well done!** Community bakers love supporters like you",
        "💚 **Green light for decentralization!** Small = beautiful",
        "🎈 **Perfect size!** Not too big, not too small, just right",
        "⭐ **Stellar decision!** Small bakers keep the network diverse",
        "🌈 **Rainbow of bakers!** Diversity makes Tezos stronger",
        "🎯 **Bullseye!** This baker size is ideal for the network",
        "🏆 **Winner winner!** Supporting small bakers = winning strategy",
        "💝 **With love from Tezos!** Small bakers appreciate the delegation",
        "🌻 **Blooming choice!** Helping small bakers grow is beautiful",
    ],

    TIER_MEDIUM: [
        # Positive - good balance
        "👍 **Solid choice!** Medium bakers offer a nice balance",
        "✅ **Good call!** This baker has room to grow without dominating",
        "🎵 **In tune!** Medium bakers hit the sweet spot",
        "💙 **Nice pick!** Still supporting decentralization here",
        "🌊 **Smooth sailing!** Medium bakers are reliable choices",
        "🎨 **Artful balance!** Not too big, keeping it distributed",
        "🌤️ **Bright choice!** Medium bakers are growing healthily",
        "🎭 **Drama-free!** Medium bakers, medium drama, all good",
        "🍀 **Lucky find!** Medium bakers with growth potential",
        "🎪 **Center stage!** Medium bakers doing their thing",
    ],

    TIER_LARGE: [
        # Neutral with gentle nudge
        "🤔 **Interesting choice...** Maybe check out smaller bakers too?",
        "📊 **Big baker alert!** Consider diversifying with smaller ones?",
        "⚖️ **Balance check!** Large bakers are fine, but small ones need love too",
        "💭 **Food for thought...** Smaller bakers could use your support",
        "🎲 **Safe bet?** Large bakers work, but small ones add spice!",
        "🔍 **Worth exploring!** Plenty of excellent smaller bakers out there",
        "🌐 **Think global!** Smaller bakers = more decentralization",
        "🎯 **Hit or miss...** Large works, but small bakers are the real MVPs",
        "💡 **Pro tip:** Mix it up! Try smaller bakers for max decentralization",
        "🧩 **Puzzle piece:** Large bakers fit, but small ones complete the picture",
    ],

    TIER_VERY_LARGE: [
        # Gently discouraging - promoting smaller
        "😬 **Hmm, pretty big baker there...** Small bakers crying in the corner",
        "⚠️ **Whale-adjacent!** This baker doesn't need more power, friend",
        "🐘 **Elephant in the room!** Maybe share the love with smaller bakers?",
        "📢 **PSA:** Very large bakers = less decentralization. Consider downsizing!",
        "🎭 **Plot twist idea:** Delegate to a micro baker instead? Just saying...",
        "🌊 **Making waves...** but not the good kind. Smaller = better!",
        "🔔 **Ding ding!** Decentralization alarm! This baker is quite large",
        "💬 **Friendly reminder:** The network thanks you when you go small",
        "🎪 **Big top energy...** but circus belongs with small bakers too!",
        "🤷 **Your call, but...** small bakers would appreciate you more!",
    ],

    TIER_WHALE: [
        # Humorously discouraging - strong push for decentralization
        "🐋 **WHALE ALERT!** Mmm, not a fan of decentralization, are we?",
        "😅 **Yikes!** This baker has more XTZ than small countries have GDP",
        "🚨 **Centralization detected!** Small bakers are *right there*, friend",
        "💀 **Bruh...** Satoshi is crying somewhere. Think small, delegate small!",
        "🎪 **Circus level:** Mega. This baker is already a king, help the peasants!",
        "⛔ **Decentralization.exe has stopped working.** Reboot with small baker?",
        "🤦 **Facepalm moment!** This whale doesn't need MORE delegates",
        "🌪️ **Storm warning!** Too much power in one place = bad for network",
        "🎯 **Mission failed!** Decentralization needs you elsewhere, soldier",
        "🔥 **Hot take:** This baker has enough. Be a hero, go micro!",
        "😬 **Awkward...** Like bringing a tank to a knife fight. Too much!",
        "🎭 **Drama mode:** Tezos governance shaking their heads right now",
    ],
}


def get_baker_commentary(baker_balance_xtz: Optional[Decimal]) -> str:
    """
    Get a fun, educational message about the baker based on their size.

    Args:
        baker_balance_xtz: Baker's staking balance in XTZ (None if unknown)

    Returns:
        A fun message appropriate to the baker's size tier
    """
    # If balance is unknown, return a neutral message
    if baker_balance_xtz is None:
        return "🔍 Checking baker size... Good bakers come in all sizes, but small ones are special!"

    tier = get_baker_tier(baker_balance_xtz)
    messages = _MESSAGES.get(tier, [])

    if not messages:
        return "✨ Nice choice!"

    return secrets.choice(messages)


def get_baker_tier_emoji(baker_balance_xtz: Optional[Decimal]) -> str:
    """
    Get an emoji representing the baker's tier.

    Args:
        baker_balance_xtz: Baker's staking balance in XTZ (None if unknown)

    Returns:
        An emoji representing the tier
    """
    if baker_balance_xtz is None:
        return "❓"

    tier = get_baker_tier(baker_balance_xtz)

    emoji_map = {
        TIER_MICRO: "🌱",
        TIER_SMALL: "🌿",
        TIER_MEDIUM: "🌳",
        TIER_LARGE: "🏢",
        TIER_VERY_LARGE: "🏰",
        TIER_WHALE: "🐋",
    }

    return emoji_map.get(tier, "⭐")


def get_baker_tier_label(baker_balance_xtz: Optional[Decimal]) -> str:
    """
    Get a human-readable label for the baker's tier.

    Args:
        baker_balance_xtz: Baker's staking balance in XTZ (None if unknown)

    Returns:
        A tier label string
    """
    if baker_balance_xtz is None:
        return "Unknown Size"

    tier = get_baker_tier(baker_balance_xtz)

    label_map = {
        TIER_MICRO: "Micro Baker",
        TIER_SMALL: "Small Baker",
        TIER_MEDIUM: "Medium Baker",
        TIER_LARGE: "Large Baker",
        TIER_VERY_LARGE: "Very Large Baker",
        TIER_WHALE: "Whale Baker",
    }

    return label_map.get(tier, "Baker")


def format_baker_balance_info(
    baker_address: str,
    baker_balance_xtz: Optional[Decimal],
    include_commentary: bool = True
) -> str:
    """
    Format a complete info message about the baker including size and commentary.

    Args:
        baker_address: The baker's address
        baker_balance_xtz: Baker's staking balance in XTZ (None if unknown)
        include_commentary: Whether to include the fun commentary

    Returns:
        Formatted info string with markup
    """
    if baker_balance_xtz is None:
        return f"🔍 Analyzing baker [cyan]{baker_address[:10]}...[/cyan]"

    emoji = get_baker_tier_emoji(baker_balance_xtz)
    label = get_baker_tier_label(baker_balance_xtz)

    # Format balance with thousands separators
    balance_str = f"{baker_balance_xtz:,.2f}".rstrip('0').rstrip('.')

    info = f"{emoji} **{label}** | Balance: [cyan]{balance_str} XTZ[/cyan]"

    if include_commentary:
        commentary = get_baker_commentary(baker_balance_xtz)
        info += f"\n\n{commentary}"

    return info


def should_show_decentralization_warning(baker_balance_xtz: Optional[Decimal]) -> bool:
    """
    Determine if we should show a decentralization warning.

    Args:
        baker_balance_xtz: Baker's staking balance in XTZ (None if unknown)

    Returns:
        True if baker is large enough to warrant a warning
    """
    if baker_balance_xtz is None:
        return False

    tier = get_baker_tier(baker_balance_xtz)
    return tier in [TIER_VERY_LARGE, TIER_WHALE]


def get_decentralization_recommendation() -> str:
    """
    Get a recommendation message promoting decentralization.

    Returns:
        A message encouraging delegation to smaller bakers
    """
    recommendations = [
        "💡 **Pro tip:** Small bakers (< 100k XTZ) help keep Tezos decentralized!",
        "🌱 **Consider this:** Micro bakers offer the same rewards with more impact!",
        "🎯 **Network health:** The more distributed the stake, the stronger Tezos!",
        "✨ **Did you know?** Small bakers often have more engaged communities!",
        "🚀 **Level up:** Supporting small bakers is a gigabrain Tezos move!",
    ]

    return secrets.choice(recommendations)
