"""
Sarcastic messages for when users try to use Advanced mode.

This module provides funny, discouraging messages to gently mock users
who think they need to manually configure gas/fee parameters.

Message tone: "You think you're an expert? Just pick a normal option!"
"""

import secrets

# ============================================================================
# ADVANCED MODE ATTEMPT MESSAGES 🤓
# ============================================================================

ADVANCED_MODE_MESSAGES = [
    "🤓 Oh wow, an EXPERT! Just pick Economy/Normal/Priority like everyone else. ¬¬",
    "🎓 PhD in blockchain? No? Then use the normal options above. ¬¬",
    "👨‍💻 Stop pretending you're Vitalik and pick an option above. ¬¬",
    "🧠 Big brain mode activated? Nah, just use Normal fee. Trust me. ¬¬",
    "🚀 Advanced mode? Really? The presets work fine. ¬¬",
    "🤡 You don't need this. Seriously. Pick Economy/Normal/Priority. ¬¬",
    "⚙️ Advanced? More like 'I have no idea what I'm doing' mode. ¬¬",
    "🎯 Unless you REALLY know what you're doing, use the options above. ¬¬",
    "💡 Pro tip: You're not a pro. Use the simple options. ¬¬",
    "🔧 Tinkering with gas limits? Bold move. Or just... don't. ¬¬",
    "📚 Did you read the Tezos documentation? No? Then click above. ¬¬",
    "🎮 This isn't a video game difficulty setting. Use Normal. ¬¬",
    "🧪 Experimenting? Cool. But maybe not with real money? ¬¬",
    "🎪 Welcome to the 'I will mess this up' circus! Use presets. ¬¬",
    "🏆 Congrats on finding this button! Now ignore it and use Normal. ¬¬",
    "🤦 Advanced mode is for people who like paying wrong fees. ¬¬",
    "💸 Want to overpay OR underpay? Advanced is perfect! Or just... Normal? ¬¬",
    "🎭 Playing expert? The blockchain doesn't care. Pick Normal. ¬¬",
    "🔬 Unless you're testing something, you don't need this. ¬¬",
    "⚡ Fast, cheap, or reliable? That's literally what the presets are. ¬¬",
    "🎨 Customization is nice, but gas limits aren't art. Use presets. ¬¬",
    "🌟 You're special, but not 'needs custom gas limits' special. ¬¬",
    "📊 Do you even know what gas limits are? Pick a preset. ¬¬",
    "🎪 Step right up to make a mistake! Or... just use Normal fee. ¬¬",
    "🧙 Wizard mode? Nope. Just Economy/Normal/Priority. ¬¬",
    "💀 Advanced mode: where transactions go to die. Use presets. ¬¬",
    "🏴‍☠️ Arr matey, even pirates use Normal fee! ¬¬",
    "🎯 Hit the target: pick Normal. Don't overthink it. ¬¬",
    "🤹 Juggling gas parameters? You'll drop them. Use presets. ¬¬",
    "🎢 Want a rollercoaster? Try Advanced. Want success? Use Normal. ¬¬",
]

def get_advanced_mode_message() -> str:
    """
    Get a random sarcastic message for Advanced mode attempts.

    Returns:
        A random discouraging/funny message string

    Example:
        >>> get_advanced_mode_message()
        "🤓 Oh wow, an EXPERT! Just pick Economy/Normal/Priority like everyone else. ¬¬"
    """
    return secrets.choice(ADVANCED_MODE_MESSAGES)


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    print("🤓 Advanced Mode Messages Library Test\n")

    print("SAMPLE MESSAGES (5 random):")
    for i in range(5):
        print(f"  {i+1}. {get_advanced_mode_message()}")
        print()

    print(f"\n📊 Statistics:")
    print(f"  Total messages: {len(ADVANCED_MODE_MESSAGES)}")
    print(f"\n💡 Tip: All messages discourage using Advanced mode!")
