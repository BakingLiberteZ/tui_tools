"""
Staking motivational messages for TUI Tezos Wallet.

This module provides fun, motivational messages to encourage staking and delegation.
Messages are randomly selected based on the wallet's staking/delegation status.

Message Categories:
- 💪 CHAD: Has staking balance > 0 (promoting network security!)
- 😴 BORING: Delegating but not staking (it's ok, but could do better)
- 😂 LAZY: Not delegating and not staking (come on, help the network!)
"""

import secrets
from typing import Literal

# ============================================================================
# STAKING > 0: CHAD MESSAGES 💪
# ============================================================================

STAKING_CHAD = [
    "💪 What a CHAD! Securing the network like a BOSS!",
    "🏆 Absolute legend! Staking AND securing! RESPECT!",
    "💎 Diamond hands! TRUE Tezos believer right here!",
    "👑 KING/QUEEN of staking! The network LOVES you!",
    "🔥 GIGACHAD energy! Making Tezos stronger every block!",
    "⚡ BEAST MODE! Staking like there's no tomorrow!",
    "🦾 SIGMA GRINDSET! Passive income + network security!",
    "🎖️ Network guardian! Salute to you, brave staker!",
    "🌟 ELITE status! You're what makes Tezos great!",
    "💰 SMART MONEY! Earning while securing! GENIUS!",
    "🚀 TO THE MOON! Staking your way to success!",
    "🔒 FORTRESS MODE! Your XTZ working hard for you!",
    "⭐ ALL-STAR! The baker's favorite kind of delegator!",
    "🎯 LOCKED IN! Commitment level: MAXIMUM!",
    "🏅 HALL OF FAME! True Tezos OG right here!",
]

# ============================================================================
# STAKING = 0 BUT DELEGATING: BORING MESSAGES 😴
# ============================================================================

STAKING_BORING = [
    "😴 Ok, fine, boring... Delegating but no skin in the game?",
    "🥱 Meh. Delegation is ok, but staking is WHERE IT'S AT!",
    "💤 Playing it safe, huh? Staking gives you MORE rewards...",
    "🤷 I mean, sure, delegate... but have you TRIED staking?",
    "😑 Delegation: the diet soda of Tezos participation.",
    "🙄 Oh, delegating... how... pedestrian. Ever heard of STAKING?",
    "💭 Delegation? That's cute. Staking? That's POWER.",
    "🚶 Walking when you could be RUNNING. Stake it up!",
    "📉 Delegating only? You're leaving rewards on the table!",
    "😪 Wake me up when you decide to actually STAKE.",
    "🥉 Bronze medal effort. Staking is the GOLD standard!",
    "🐌 Slow and steady... but staking is FASTER and steadier!",
    "👻 Present but not really HERE. Stake for full participation!",
    "🎻 Playing the world's smallest violin for your missed rewards.",
    "🌧️ Cloudy with a chance of missed staking opportunities.",
]

# ============================================================================
# STAKING = 0 AND NOT DELEGATING: LAZY MESSAGES 😂
# ============================================================================

STAKING_LAZY = [
    "😂 Do you even Tezos, bro? STAKE SOMETHING!",
    "🏜️ It's so lonely here... Let's stake something please, for my family! 😢",
    "🤡 Not delegating? Not staking? CLOWN BEHAVIOR! 🤡",
    "💀 RIP to your potential rewards. F in the chat.",
    "🚨 ALERT: This wallet is allergic to profit! Doctor says STAKE NOW!",
    "🍃 Your XTZ just sitting there collecting DUST. Wake them up!",
    "😭 The baker cries every time you don't delegate OR stake!",
    "🙈 Monkey see, monkey do NOTHING. Come on, participate!",
    "🥀 Your XTZ are wilting! They need the sunshine of STAKING!",
    "⚰️ Passive income has LEFT THE CHAT. Are you even alive?",
    "🤦 Facepalm. HELP THE NETWORK! Delegate! Stake! ANYTHING!",
    "🎪 Welcome to the circus! You're the main attraction: THE DO-NOTHING!",
    "🌵 Desert vibes. No delegation, no staking, just... tumbleweeds.",
    "🦥 Sloth mode ACTIVATED. The network needs YOU, not your nap!",
    "💸 Money printer goes BRRR... but not for you! STAKE IT!",
    "🚪 Opportunity is KNOCKING. Will you answer? STAKE NOW!",
    "🏚️ Your XTZ house is EMPTY. Time to furnish it with STAKING!",
    "🎲 You're gambling by NOT staking. Ironic, isn't it?",
    "🔕 Notification: You've been nominated for 'Most Passive Wallet 2026'!",
    "🥶 Cold storage? More like FROZEN OPPORTUNITY! Thaw it with staking!",
    "🤷‍♂️ I'm not mad, just disappointed. The network is too.",
    "🍿 Grabbing popcorn to watch you NOT earn rewards. Thrilling!",
]

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

StakingContext = Literal["chad", "boring", "lazy"]

def get_staking_message(context: StakingContext) -> str:
    """
    Get a random staking motivational message based on wallet status.

    Args:
        context: The staking context:
            - "chad": Wallet has staking balance > 0 (💪 securing network!)
            - "boring": Wallet is delegating but not staking (😴 meh)
            - "lazy": Wallet is not delegating and not staking (😂 come on!)

    Returns:
        A random motivational/funny message string

    Example:
        >>> get_staking_message("chad")
        "💪 What a CHAD! Securing the network like a BOSS!"
    """
    messages_map = {
        "chad": STAKING_CHAD,
        "boring": STAKING_BORING,
        "lazy": STAKING_LAZY,
    }

    messages = messages_map.get(context, STAKING_LAZY)
    return secrets.choice(messages)


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    print("💪 Staking Messages Library Test\n")

    contexts: list[StakingContext] = ["chad", "boring", "lazy"]

    for context in contexts:
        print(f"{context.upper()}:")
        print(f"  {get_staking_message(context)}")
        print()

    print("\n📊 Statistics:")
    print(f"  Chad messages: {len(STAKING_CHAD)}")
    print(f"  Boring messages: {len(STAKING_BORING)}")
    print(f"  Lazy messages: {len(STAKING_LAZY)}")
    print(f"  TOTAL: {len(STAKING_CHAD) + len(STAKING_BORING) + len(STAKING_LAZY)}")
