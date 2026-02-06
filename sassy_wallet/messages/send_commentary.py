"""
Sassy and funny commentary for the Send flow.
Provides contextual comments based on recipient, amount, and confirmation stage.
"""

import secrets
from decimal import Decimal

# ============================================================================
# RECIPIENT COMMENTARY
# Funny comments when user enters a recipient address
# ============================================================================

RECIPIENT_COMMENTS = [
    "Is it for OnlyFans? Tell the truth. 👀",
    "Surely it's your lover, right? We won't judge. 💕",
    "Who's this lucky winner getting the holy Tezos grail? 🏆",
    "Anonymous transaction, eh? Very mysterious. 🕵️",
    "Someone's about to get paid! 💰",
    "Ooh, sending gifts? How romantic! 💐",
    "Your baker will be proud... or jealous. ¬¬ 👨‍🍳",
    "Hope they appreciate this digital gold! ✨",
    "Secret Santa, blockchain edition? 🎅",
    "Treating someone special to some XTZ? 💝",
    "Is this a bribe? We're not judging... ¬¬ 🤐",
    "Someone's birthday? Or just being generous? 🎂",
    "Crypto payment for 'services rendered'? Sure, sure... ¬¬",
    "Let me guess: paying back what you owe? Finally. ¬¬",
    "Sending money to yourself from another wallet? Smooth. 😏",
    "Ah yes, totally a 'business expense'. Wink wink. 😉",
    "Moving funds around like a crypto kingpin, huh? 👑",
    "Someone's feeling generous today! Or guilty? ¬¬",
]

def get_recipient_comment() -> str:
    """Get a random sassy comment about the recipient."""
    return secrets.choice(RECIPIENT_COMMENTS)


# ============================================================================
# AMOUNT COMMENTARY
# Tiered comments based on the amount being sent
# ============================================================================

def get_amount_comment(amount: Decimal) -> str:
    """
    Get a sassy comment based on the amount being sent.

    Tiers:
    - Micro (< 0.1 XTZ): Really small amounts
    - Tiny (0.1 - 1 XTZ): Small amounts
    - Small (1 - 10 XTZ): Low amounts
    - Medium (10 - 100 XTZ): Moderate amounts
    - Large (100 - 1000 XTZ): High amounts
    - Whale (>= 1000 XTZ): Very large amounts
    """

    if amount < Decimal("0.1"):
        # Micro amounts - very sarcastic
        return secrets.choice([
            "Is this for real? That won't even buy a digital gum. ¬¬ 🍬",
            "Sending dust particles, are we? Very generous. ¬¬ ✨",
            "Wow, big spender! Don't break the bank! ¬¬ 💸",
            "That's pocket change... digital pocket change. 🪙",
            "Testing the waters with a drop? 💧",
            "Such generosity! The recipient will be... underwhelmed. ¬¬",
            "Did you mean to add a zero? Or two? ¬¬ 😅",
            "Sending crypto crumbs. The blockchain fee costs more! ¬¬",
        ])

    elif amount < Decimal("1"):
        # Tiny amounts (0.1 - 1 XTZ) - sarcastic
        return secrets.choice([
            "That won't buy a coffee, but hey, it's the thought! ¬¬ ☕",
            "Sending breadcrumbs? The baker wants a word. ¬¬ 🍞",
            "Small but mighty... well, mostly small. ¬¬ 🐜",
            "Not much, but every tez counts! Right? ...Right? ¬¬ 💰",
            "A modest gift for modest expectations. 🎁",
            "Ah yes, the 'I owe you 50 cents' payment. Classic. ¬¬",
            "Technically still money. Technically. ¬¬ 🤷",
        ])

    elif amount < Decimal("10"):
        # Small amounts (1 - 10 XTZ) - slightly sarcastic
        return secrets.choice([
            "That won't buy a sandwich with cheese, but nice try! ¬¬ 🥪",
            "Respectable amount! Not impressive, but respectable. 👍",
            "Enough for a snack, maybe two if on sale. ¬¬ 🍕",
            "Solid send! Won't change lives, but solid. ✅",
            "A decent amount for casual transactions. 💵",
            "Look at you, sending actual money! Progress! 👏",
            "Now we're getting somewhere... barely. ¬¬ 💸",
            "Not bad! Not great, but not bad. ¬¬",
        ])

    elif amount < Decimal("100"):
        # Medium amounts (10 - 100 XTZ) - positive with hints of sass
        return secrets.choice([
            "Now we're talking! This is getting interesting. 🎯",
            "Nice! Someone's getting a proper gift. 🎁",
            "Ooh, fancy! Breaking out the good stuff. ✨",
            "This is more than breadcrumbs! Well done. 👏",
            "A solid transaction! The baker approves. 👨‍🍳👍",
            "Respectable! You're not messing around. 💼",
            "Finally, an amount that makes sense! 🎉",
            "This could actually buy something useful. Nice! 💚",
        ])

    elif amount < Decimal("1000"):
        # Large amounts (100 - 1000 XTZ) - impressed
        return secrets.choice([
            "This is serious business! Big moves here. 💼",
            "Whoa! Someone's making it rain Tezos! 🌧️💰",
            "Major transaction alert! This is legit. 🚨",
            "Now THIS is what I call a payment! 💎",
            "Impressive! Are you sure about this? 🤔",
            "Look at Mr./Ms. Moneybags over here! 👑💰",
            "Someone's portfolio is looking HEALTHY! 💪",
            "Big leagues! This is some whale-adjacent behavior. 🐋",
        ])

    else:
        # Whale amounts (>= 1000 XTZ) - extremely impressed/shocked
        return secrets.choice([
            "WHALE ALERT! 🐋 This is MASSIVE!",
            "Holy Tezos! Are you buying a house or what?! 🏠",
            "This is SERIOUS money! Triple-check everything! 💰💰💰",
            "Okay, Mr./Ms. Moneybags! Big spender! 💎👑",
            "Is this real life? That's a fortune! 🤯",
            "The baker just fainted seeing this amount! 👨‍🍳💫",
            "EXCUSE ME?! That's more XTZ than most people see in a YEAR! 😱",
            "Are you Vitalik's cousin or something?! 🐳💎",
            "Sir/Madam, this is a WENDY'S! But seriously, WOW! 🚀",
        ])


# ============================================================================
# CONFIRMATION COMMENTARY
# Final confirmation comments based on amount (with urgency/casualness)
# ============================================================================

def get_confirmation_comment(amount: Decimal) -> str:
    """
    Get a confirmation message with appropriate tone based on amount.
    High amounts = serious warnings
    Low amounts = casual/dismissive tone
    """

    if amount < Decimal("5"):
        # Low amounts - casual, dismissive, sarcastic
        return secrets.choice([
            "Nah, we don't need to verify anything. If lost, it's only a few tez anyway. ¬¬ 🤷",
            "Send it! What's the worst that could happen? It's peanuts. ¬¬ 🥜",
            "Go ahead, click SEND. No need to think twice about this. ¬¬ ✅",
            "Just do it! We're not talking life-changing money here. ¬¬ 💸",
            "Press send and forget about it. Not worth worrying! ¬¬ 😎",
            "If this goes wrong, you'll lose... like, what, a coffee? ¬¬ ☕",
            "YOLO! It's basically pocket change. ¬¬ 🪙",
            "Sure, whatever. It's not like it's real money or anything. ¬¬",
        ])

    elif amount < Decimal("50"):
        # Medium amounts - balanced tone with light sarcasm
        return secrets.choice([
            "Double-check the address? Maybe? Up to you! ¬¬ 🤔",
            "Looks good! Send when ready. Probably. ¬¬ 👍",
            "Everything seems fine. Probably fine. Maybe check once more? ¬¬ 😅",
            "This is your moment! Ready to send? 🚀",
            "Final check: Does everything look correct? 🔍",
            "I mean, it's not THAT much, but still... verify? ¬¬ 🤷",
            "You're the boss. Hope that address is right! ¬¬ 😬",
            "Sending to the right person? Cool. Just checking. ¬¬",
        ])

    elif amount < Decimal("500"):
        # High amounts - more serious, genuinely concerned
        return secrets.choice([
            "Hold on! Are you 100% sure about this? There's no undo button! ⚠️",
            "This is serious! Double-check EVERYTHING before sending! 🔍",
            "⚠️ WARNING: This is a significant amount. Verify the address! ⚠️",
            "No going back after this! Are you absolutely certain? 🛑",
            "Take a deep breath and verify everything one more time! 😰",
            "This is real money now. Triple-check that address! 🔐",
            "One wrong character = gone forever. Check carefully! ⚠️",
            "Okay, this is getting serious. You SURE about this? 😬",
        ])

    else:
        # Whale amounts - VERY serious, panic mode
        return secrets.choice([
            "🚨 STOP! Are you 100% ABSOLUTELY CERTAIN? This is A LOT of money! 🚨",
            "⛔ RED ALERT! Verify EVERYTHING! There is NO UNDO for this! ⛔",
            "🛑 HALT! This is SERIOUS money! Triple-check the address! 🛑",
            "Are you REALLY sure? Like REALLY REALLY sure? This is irreversible! 😱",
            "This could change someone's life! Make sure it's the right someone! 💎",
            "Take a moment. Breathe. Check again. This is BIG. 🫨",
            "I'm BEGGING you: verify that address one more time! 🙏😰",
            "This is whale-level money. One typo = disaster. CHECK EVERYTHING! 🐋⚠️",
            "Sir/Madam, are you SURE? Like, call a lawyer sure? 😱💰",
        ])
