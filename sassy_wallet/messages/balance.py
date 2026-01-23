"""
Balance tier messages for TUI Tezos Wallet.

This module provides fun, motivational messages based on wallet balance tiers
and staking/delegation status. Messages adapt dynamically to encourage good practices.

Balance Tiers:
- 🌫️ DUST (0-1 XTZ): Almost nothing
- 💸 BROKE (1-100 XTZ): Starting out
- 💰 SAVER (100-500 XTZ): Building wealth
- 🏦 INVESTOR (500-1000 XTZ): Serious player
- 🐋 BABY WHALE (1000-5000 XTZ): Big league
- 🐳 WHALE (5000+ XTZ): Crypto royalty

Combined with staking status for personalized messages!
"""

import random
from decimal import Decimal
from typing import Literal

# ============================================================================
# TIER DEFINITIONS (balance ranges in XTZ)
# ============================================================================

TIER_DUST = (Decimal('0'), Decimal('1'))
TIER_BROKE = (Decimal('1'), Decimal('100'))
TIER_SAVER = (Decimal('100'), Decimal('500'))
TIER_INVESTOR = (Decimal('500'), Decimal('1000'))
TIER_WHALE_BABY = (Decimal('1000'), Decimal('5000'))
TIER_WHALE = (Decimal('5000'), Decimal('999999999'))

# ============================================================================
# 🌫️ DUST TIER (0-1 XTZ) - Almost nothing
# ============================================================================

DUST_STAKING = [
    "🌱 It's not much, but it's honest work! Staking your dust like a BOSS!",
    "💎 Every diamond starts as coal! Staking even dust = legend status!",
    "🦸 SUPERHERO! Staking with almost nothing! True believer energy!",
    "🌟 Penny stocks? Nah! Penny STAKING! You're doing it right!",
    "💪 Broke but staking? That's COMMITMENT! Respect!",
    "🔥 Dust staker = Future millionaire! Mark my words!",
    "🎯 Small balance, BIG vision! Staking even dust shows character!",
    "⚡ Zero to hero journey starts HERE! Dust staking is the way!",
]

DUST_DELEGATING = [
    "😅 Delegating dust? Hey, at least you're trying! Baby steps!",
    "🤏 Tiny balance, tiny effort. Consider staking for MORE!",
    "🌾 Delegating crumbs... but it's something! Upgrade to staking?",
    "💨 Light as air! Delegate AND stake for maximum gains!",
    "🍃 Featherweight delegation. Try staking to level up!",
]

DUST_LAZY = [
    "😂 Less than 1 XTZ and not even delegating? BOLD strategy! ¬¬",
    "🌫️ Your balance is basically air. At least delegate it! ¬¬",
    "💀 Ghost wallet! Almost nothing AND not participating? Come on! ¬¬",
    "🦗 *Crickets* Even dust should be delegated! Do something! ¬¬",
    "🎭 The audacity of having dust and doing NOTHING with it! ¬¬",
    "🤷 Dust + lazy = certified crypto hobo! ¬¬",
    "😑 Your wallet is basically a museum piece. ¬¬",
]

# ============================================================================
# 💸 BROKE TIER (1-100 XTZ) - Starting out
# ============================================================================

BROKE_STAKING = [
    "💪 It ain't much, but you're STAKING! That's what winners do!",
    "🏆 McDonald's paycheck but STAKING like a champ! Respect!",
    "🌱 Small seed, big dreams! Staking shows you understand the game!",
    "🔥 Broke but not broken! Staking = smart money moves!",
    "💎 Started from the bottom, now we're staking! Drake would be proud!",
    "⚡ Student budget but PRO mindset! Staking it all!",
    "🎯 Small stack, BIG brain! Staking is the secret weapon!",
    "🦸 Everyday hero! Staking even with humble means!",
    "💡 It's not the size, it's what you DO with it! And you're STAKING!",
    "🌟 Ramen budget, caviar mentality! Staking like a boss!",
    "🚀 Small rocket, big ambitions! Staking to the moon!",
    "🎮 Grinding in real life! Staking your way up!",
]

BROKE_DELEGATING = [
    "😐 Delegating is OK, but you could do MORE! Try staking! ¬¬",
    "🥉 Bronze medal effort. Staking = gold! Upgrade your game! ¬¬",
    "💤 Playing it safe with delegation? Staking has better rewards! ¬¬",
    "🤷 Small bag delegating only? You're missing out on staking! ¬¬",
    "😴 Delegation is the participation trophy. Staking is the real deal! ¬¬",
    "📈 Your balance could GROW faster with staking! Just saying... ¬¬",
    "🎻 Could be earning more... switch to staking! Trust me! ¬¬",
]

BROKE_LAZY = [
    "😂 McDonald's not paying too much, crypto bro? AND not delegating? ¬¬",
    "💀 Under 100 XTZ and doing NOTHING? Opportunity = missed! ¬¬",
    "🤡 Small bag, zero effort! At LEAST delegate, come on! ¬¬",
    "🦥 Sloth mode activated! Your XTZ wants to work, let them! ¬¬",
    "💸 Not much to work with AND not delegating? Savage behavior! ¬¬",
    "😭 Broke AND lazy? Double whammy! Start delegating NOW! ¬¬",
    "🏜️ Desert vibes: dry wallet, dry participation. Do something! ¬¬",
    "🎪 Welcome to the circus: small balance + zero action = clown! ¬¬",
    "🪦 RIP to your potential earnings. ¬¬",
    "🎮 Playing crypto on easy mode... and still losing. ¬¬",
]

# ============================================================================
# 💰 SAVER TIER (100-500 XTZ) - Building wealth
# ============================================================================

SAVER_STAKING = [
    "💰 Nice savings AND staking! You're on the right path!",
    "🏆 Smart saver! Staking shows you're thinking long-term!",
    "💎 Solid stack with staking! That's responsible crypto!",
    "🎯 Building wealth the RIGHT way! Staking + patience = success!",
    "🌟 Nice cushion! And staking it? You GET IT!",
    "🔥 Healthy balance with active staking! Pro moves!",
    "💡 Financial discipline + staking = future millionaire vibes!",
    "🏦 Savings account energy! But BETTER because STAKING!",
    "⚡ Not broke, not greedy, just smart! Staking like a pro!",
    "🚀 Middle class with FIRST CLASS vision! Staking to grow!",
    "💪 Respectable stack! And STAKING it! Well done!",
    "🎖️ Saver + Staker = Winner combo! Keep going!",
]

SAVER_DELEGATING = [
    "💰 Good savings, but delegating only? Staking unlocks MORE! ¬¬",
    "🤔 Nice bag! Why not STAKE it for better rewards? ¬¬",
    "💤 Delegating your savings? Staking would be the next level! ¬¬",
    "📊 Solid balance, but you're leaving money on the table! ¬¬",
    "🥈 Silver tier! Go for GOLD with staking! ¬¬",
    "😐 Nice cushion, but it could be NICER with staking! ¬¬",
    "🎯 Close to pro level! Just need to stake instead of delegate! ¬¬",
]

SAVER_LAZY = [
    "😱 100-500 XTZ just SITTING there? Criminal negligence! ¬¬",
    "💀 Nice savings doing NOTHING! What a waste! ¬¬",
    "🤦 That's real money just collecting dust! Delegate or stake! ¬¬",
    "🔥 Your XTZ are screaming 'USE US!' Listen to them! ¬¬",
    "💸 Leaving money on the table like it's a buffet! Stop it! ¬¬",
    "😭 SO MUCH POTENTIAL... wasted! Stake or delegate NOW! ¬¬",
    "🎪 The greatest show: Good balance + zero action = tragedy! ¬¬",
    "🪦 Your XTZ are dying of boredom. ¬¬",
    "🏖️ Your coins on permanent vacation. Nice life! ¬¬",
]

# ============================================================================
# 🏦 INVESTOR TIER (500-1000 XTZ) - Serious player
# ============================================================================

INVESTOR_STAKING = [
    "🏦 Serious investor alert! AND staking? You're a professional!",
    "💎 Big brain energy! Staking 500+ shows you understand value!",
    "🔥 WHALE BEHAVIOR! Staking substantial amounts = vision!",
    "👑 Crypto royalty! Staking this much means you're ALL IN!",
    "⚡ Power player! Your staking game is STRONG!",
    "🎯 This is REAL money! And staking it? LEGEND status!",
    "💡 Financial genius detected! Staking + big bag = success formula!",
    "🚀 Investor class! Staking to compound those gains!",
    "🏆 You're not playing games! Serious money, serious staking!",
    "💪 HEAVYWEIGHT! Your stake secures the whole network!",
    "🌟 VIP treatment! Staking at this level = respected!",
    "🦅 Eagle vision! You see the future and it's STAKED!",
]

INVESTOR_DELEGATING = [
    "🤔 500+ XTZ but only delegating? You're SO CLOSE to greatness! ¬¬",
    "💼 Business class traveler using economy! STAKE for first class! ¬¬",
    "😐 That's serious money not being SERIOUS! Stake it! ¬¬",
    "📊 Investor-level bag, beginner-level strategy. Upgrade to staking! ¬¬",
    "🎯 You have the capital, now add the strategy: STAKE! ¬¬",
    "💰 That's investment-grade capital doing tourist-level work! ¬¬",
]

INVESTOR_LAZY = [
    "😱 500+ XTZ just IDLE?! That's a CAR not working for you! ¬¬",
    "💀 SERIOUS money doing NOTHING! This hurts to see! ¬¬",
    "🔥 Your portfolio is ON FIRE... but not in a good way! ¬¬",
    "😭 Investor-level bag, ZERO-level action! UNACCEPTABLE! ¬¬",
    "💸 That's rent money × 10 just sitting! Delegate or stake! ¬¬",
    "🤦 The network NEEDS you and you're just... watching?! ¬¬",
    "🏝️ Vacation mode with serious money? Interesting choice. ¬¬",
    "🎰 Having serious cash and doing nothing = gambling against yourself! ¬¬",
]

# ============================================================================
# 🐋 BABY WHALE TIER (1000-5000 XTZ) - Big league
# ============================================================================

WHALE_BABY_STAKING = [
    "🐋 BABY WHALE SPOTTED! Staking = ELITE mindset!",
    "👑 Crypto ROYALTY! Your stake matters to the entire network!",
    "💎 DIAMOND WHALE! Staking this much = true believer!",
    "🏆 CHAMPION! You're securing Tezos like a BOSS!",
    "⚡ POWER USER! Your staking contribution is MASSIVE!",
    "🔥 WHALE ENERGY! The network LOVES you!",
    "🎯 BIG LEAGUE! Staking 4 figures shows serious commitment!",
    "💡 GENIUS INVESTOR! Staking to maximize returns!",
    "🚀 MOON MISSION! This is whale-level staking!",
    "💪 HEAVYWEIGHT CHAMPION! Your stake is substantial!",
    "🌟 SUPERSTAR! The baker salutes your contribution!",
    "🦅 HIGH FLYER! Staking at this altitude = respect!",
    "🎖️ DECORATED VETERAN! You understand the long game!",
    "🏛️ PILLAR OF THE NETWORK! Your stake matters!",
]

WHALE_BABY_DELEGATING = [
    "🐋 Baby whale delegating? STAKE IT! You're leaving BIG rewards! ¬¬",
    "💼 That's a down payment on a HOUSE just delegating! ¬¬",
    "😐 Whale-level bag, shrimp-level strategy. STAKE! ¬¬",
    "🎯 You have whale power, use it! STAKE for maximum impact! ¬¬",
    "💰 That's investment property money! Make it work HARDER! ¬¬",
    "🤔 At this level, staking isn't optional, it's MANDATORY! ¬¬",
]

WHALE_BABY_LAZY = [
    "😱 1000+ XTZ IDLE?! That's a small BUSINESS not running! ¬¬",
    "💀 WHALE doing NOTHING! The ocean is CRYING! ¬¬",
    "🔥 This is BIG MONEY just... existing?! STAKE IT! ¬¬",
    "😭 The network DESPERATELY needs whales like you! PARTICIPATE! ¬¬",
    "💸 That's a NEW CAR sitting in your wallet! Make it WORK! ¬¬",
    "🤦 Whale-level responsibility, zero-level action. Not OK! ¬¬",
    "🏖️ Baby whale on permanent beach vacation. Must be nice! ¬¬",
    "🎭 The tragedy of having whale money and doing plankton work. ¬¬",
]

# ============================================================================
# 🐳 WHALE TIER (5000+ XTZ) - Crypto royalty
# ============================================================================

WHALE_STAKING = [
    "🐳 WHALE CONFIRMED! Your stake DEFINES the network!",
    "👑 ABSOLUTE ROYALTY! The blockchain bows to your stake!",
    "💎 DIAMOND HANDS WHALE! True Tezos OG right here!",
    "🏆 MEGA CHAMPION! Your contribution is LEGENDARY!",
    "⚡ POWER WHALE! The network EXISTS because of stakers like you!",
    "🔥 GIGAWHALE! You're not just playing, you're DOMINATING!",
    "🎯 APEX PREDATOR! Staking at this level = ICON status!",
    "💡 MASTERMIND! You understand value at the HIGHEST level!",
    "🚀 GALACTIC! Your stake reaches the STARS!",
    "💪 TITAN! Your staking power is UNMATCHED!",
    "🌟 CONSTELLATION! You light up the entire ecosystem!",
    "🦅 MYTHICAL! Tales will be told of your staking prowess!",
    "🎖️ HALL OF FAME! Permanent legend status achieved!",
    "🏛️ FOUNDATION! The network stands on stakes like yours!",
    "🌊 OCEAN MASTER! You control the crypto seas!",
    "💫 TRANSCENDENT! You've achieved crypto enlightenment!",
]

WHALE_DELEGATING = [
    "🐳 WHALE delegating?! You should be STAKING! Imagine the rewards! ¬¬",
    "👑 Royalty-level bag with peasant-level strategy? STAKE IT! ¬¬",
    "💎 You have LIFE-CHANGING money! STAKE for even MORE! ¬¬",
    "😐 That's generational wealth just... delegating? STAKE! ¬¬",
    "🎯 At THIS level, you should be setting the example! STAKE! ¬¬",
    "💰 That's a HOUSE! And you're just delegating? Upgrade NOW! ¬¬",
]

WHALE_LAZY = [
    "😱 5000+ XTZ IDLE?! That's LIFE-CHANGING money doing NOTHING! ¬¬",
    "💀 WHALE EMERGENCY! This much idle is a TRAGEDY! ¬¬",
    "🔥 The ENTIRE network is waiting for you! STAKE OR DELEGATE! ¬¬",
    "😭 Your bag could change lives! Instead it's just... existing?! ¬¬",
    "💸 That's a TESLA + insurance sitting idle! UNACCEPTABLE! ¬¬",
    "🤦 Whale-level bag, plankton-level participation. CRISIS! ¬¬",
    "🆘 SOS! WHALE needs immediate staking intervention! ¬¬",
    "🏝️ Retired whale living off... nothing? Interesting strategy. ¬¬",
    "🎪 The circus called: they want their whale-sized opportunity waste back! ¬¬",
]

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _get_tier(balance: Decimal) -> tuple:
    """Determine balance tier."""
    if balance < TIER_DUST[1]:
        return TIER_DUST
    elif balance < TIER_BROKE[1]:
        return TIER_BROKE
    elif balance < TIER_SAVER[1]:
        return TIER_SAVER
    elif balance < TIER_INVESTOR[1]:
        return TIER_INVESTOR
    elif balance < TIER_WHALE_BABY[1]:
        return TIER_WHALE_BABY
    else:
        return TIER_WHALE


def get_balance_message(balance_xtz: Decimal, is_staking: bool, is_delegating: bool) -> str:
    """
    Get a random balance tier message based on amount and staking status.

    Args:
        balance_xtz: Balance in XTZ (not mutez)
        is_staking: True if wallet has staking balance > 0
        is_delegating: True if wallet is delegating

    Returns:
        A random motivational/funny message string based on tier and status

    Examples:
        >>> get_balance_message(Decimal('50'), True, False)
        "💪 It ain't much, but you're STAKING! That's what winners do!"

        >>> get_balance_message(Decimal('250'), False, True)
        "💰 Good savings, but delegating only? Staking unlocks MORE!"

        >>> get_balance_message(Decimal('2500'), True, True)
        "🐋 BABY WHALE SPOTTED! Staking = ELITE mindset!"
    """
    tier = _get_tier(balance_xtz)

    # Determine which message pool to use
    if tier == TIER_DUST:
        if is_staking:
            messages = DUST_STAKING
        elif is_delegating:
            messages = DUST_DELEGATING
        else:
            messages = DUST_LAZY
    elif tier == TIER_BROKE:
        if is_staking:
            messages = BROKE_STAKING
        elif is_delegating:
            messages = BROKE_DELEGATING
        else:
            messages = BROKE_LAZY
    elif tier == TIER_SAVER:
        if is_staking:
            messages = SAVER_STAKING
        elif is_delegating:
            messages = SAVER_DELEGATING
        else:
            messages = SAVER_LAZY
    elif tier == TIER_INVESTOR:
        if is_staking:
            messages = INVESTOR_STAKING
        elif is_delegating:
            messages = INVESTOR_DELEGATING
        else:
            messages = INVESTOR_LAZY
    elif tier == TIER_WHALE_BABY:
        if is_staking:
            messages = WHALE_BABY_STAKING
        elif is_delegating:
            messages = WHALE_BABY_DELEGATING
        else:
            messages = WHALE_BABY_LAZY
    else:  # WHALE
        if is_staking:
            messages = WHALE_STAKING
        elif is_delegating:
            messages = WHALE_DELEGATING
        else:
            messages = WHALE_LAZY

    return random.choice(messages)


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    print("💰 Balance Tier Messages Library Test\n")

    test_cases = [
        (Decimal('0.5'), True, False, "DUST + Staking"),
        (Decimal('50'), True, False, "BROKE + Staking"),
        (Decimal('50'), False, True, "BROKE + Delegating"),
        (Decimal('50'), False, False, "BROKE + Lazy"),
        (Decimal('250'), True, True, "SAVER + Staking"),
        (Decimal('250'), False, True, "SAVER + Delegating"),
        (Decimal('750'), True, True, "INVESTOR + Staking"),
        (Decimal('2500'), True, True, "BABY WHALE + Staking"),
        (Decimal('10000'), True, True, "WHALE + Staking"),
        (Decimal('10000'), False, False, "WHALE + Lazy"),
    ]

    for balance, staking, delegating, label in test_cases:
        msg = get_balance_message(balance, staking, delegating)
        print(f"{label} ({balance} XTZ):")
        print(f"  {msg}")
        print()

    print("\n📊 Statistics:")
    total = (len(DUST_STAKING) + len(DUST_DELEGATING) + len(DUST_LAZY) +
             len(BROKE_STAKING) + len(BROKE_DELEGATING) + len(BROKE_LAZY) +
             len(SAVER_STAKING) + len(SAVER_DELEGATING) + len(SAVER_LAZY) +
             len(INVESTOR_STAKING) + len(INVESTOR_DELEGATING) + len(INVESTOR_LAZY) +
             len(WHALE_BABY_STAKING) + len(WHALE_BABY_DELEGATING) + len(WHALE_BABY_LAZY) +
             len(WHALE_STAKING) + len(WHALE_DELEGATING) + len(WHALE_LAZY))
    print(f"  Total messages: {total}")
    print(f"  Dust messages: {len(DUST_STAKING) + len(DUST_DELEGATING) + len(DUST_LAZY)}")
    print(f"  Broke messages: {len(BROKE_STAKING) + len(BROKE_DELEGATING) + len(BROKE_LAZY)}")
    print(f"  Saver messages: {len(SAVER_STAKING) + len(SAVER_DELEGATING) + len(SAVER_LAZY)}")
    print(f"  Investor messages: {len(INVESTOR_STAKING) + len(INVESTOR_DELEGATING) + len(INVESTOR_LAZY)}")
    print(f"  Baby Whale messages: {len(WHALE_BABY_STAKING) + len(WHALE_BABY_DELEGATING) + len(WHALE_BABY_LAZY)}")
    print(f"  Whale messages: {len(WHALE_STAKING) + len(WHALE_DELEGATING) + len(WHALE_LAZY)}")
