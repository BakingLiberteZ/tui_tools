"""
Short baker commentary messages for main screen display.

Provides concise, impactful messages for the main wallet view.
"""

import random
from decimal import Decimal
from typing import Optional
from .baker_commentary import get_baker_tier, TIER_MICRO, TIER_SMALL, TIER_MEDIUM, TIER_LARGE, TIER_VERY_LARGE, TIER_WHALE


# Short messages for each tier (displayed on main screen)
_SHORT_MESSAGES = {
    TIER_MICRO: [
        "[green]Community hero! 🌱[/green]",
        "[green]Absolute legend! 🌱[/green]",
        "[green]Gigabrain choice! 🌱[/green]",
        "[green]Peak decentralization! 🌱[/green]",
        "[green]Based move! 🌱[/green]",
        "[green]Grassroots power! 🌱[/green]",
        "[green]Small baker love! 🌱[/green]",
        "[green]Diamond hands! 🌱[/green]",
        "[green]Network backbone! 🌱[/green]",
        "[green]Decentralization king! 🌱[/green]",
    ],
    TIER_SMALL: [
        "[green]Great for the network! 🌿[/green]",
        "[green]Excellent choice! 🌿[/green]",
        "[green]Perfect size! 🌿[/green]",
        "[green]Small = beautiful! 🌿[/green]",
        "[green]Network diversity! 🌿[/green]",
        "[green]Bullseye! 🌿[/green]",
        "[green]Winner choice! 🌿[/green]",
        "[green]Blooming great! 🌿[/green]",
        "[green]Stellar pick! 🌿[/green]",
        "[green]Green light! 🌿[/green]",
    ],
    TIER_MEDIUM: [
        "[cyan]Solid choice! 🌳[/cyan]",
        "[cyan]Nice balance! 🌳[/cyan]",
        "[cyan]Good call! 🌳[/cyan]",
        "[cyan]Sweet spot! 🌳[/cyan]",
        "[cyan]Smooth sailing! 🌳[/cyan]",
        "[cyan]Bright choice! 🌳[/cyan]",
        "[cyan]Drama-free! 🌳[/cyan]",
        "[cyan]Lucky find! 🌳[/cyan]",
        "[cyan]Reliable pick! 🌳[/cyan]",
        "[cyan]Artful balance! 🌳[/cyan]",
    ],
    TIER_LARGE: [
        "[yellow]Consider smaller? 🏢[/yellow]",
        "[yellow]Big baker alert! 🏢[/yellow]",
        "[yellow]Maybe too big? 🏢[/yellow]",
        "[yellow]Small ones need love! 🏢[/yellow]",
        "[yellow]Worth exploring smaller! 🏢[/yellow]",
        "[yellow]Think smaller! 🏢[/yellow]",
        "[yellow]Safe bet, but... 🏢[/yellow]",
        "[yellow]Mix it up! 🏢[/yellow]",
        "[yellow]Balance check! 🏢[/yellow]",
        "[yellow]Small = MVP! 🏢[/yellow]",
    ],
    TIER_VERY_LARGE: [
        "[yellow]Pretty big baker... 🏰[/yellow]",
        "[yellow]Whale-adjacent! 🏰[/yellow]",
        "[yellow]Elephant in room! 🏰[/yellow]",
        "[yellow]Quite large! 🏰[/yellow]",
        "[yellow]Consider downsizing! 🏰[/yellow]",
        "[yellow]Share the love! 🏰[/yellow]",
        "[yellow]Small = better! 🏰[/yellow]",
        "[yellow]Decentralize more! 🏰[/yellow]",
        "[yellow]Too much power! 🏰[/yellow]",
        "[yellow]Go smaller! 🏰[/yellow]",
    ],
    TIER_WHALE: [
        "[red]Whale alert! Think small! 🐋[/red]",
        "[red]Yikes! Too centralized! 🐋[/red]",
        "[red]Mega baker! Go micro! 🐋[/red]",
        "[red]Centralization detected! 🐋[/red]",
        "[red]This whale has enough! 🐋[/red]",
        "[red]Bruh... go small! 🐋[/red]",
        "[red]Help the small bakers! 🐋[/red]",
        "[red]Too much power here! 🐋[/red]",
        "[red]Network needs you elsewhere! 🐋[/red]",
        "[red]Awkward choice... 🐋[/red]",
    ],
}


def get_baker_commentary_short(baker_balance_xtz: Optional[Decimal]) -> str:
    """
    Get a short, punchy message about the baker for main screen display.

    Args:
        baker_balance_xtz: Baker's balance in XTZ (None if unknown)
                          Note: Used internally for tier determination, not displayed to user

    Returns:
        A concise message appropriate to the baker's size tier
    """
    if baker_balance_xtz is None:
        return "[dim]Baker info unavailable[/dim]"

    tier = get_baker_tier(baker_balance_xtz)
    messages = _SHORT_MESSAGES.get(tier, [])

    if not messages:
        return "[dim]Unknown tier[/dim]"

    # Randomly select one of the messages for this tier
    return random.choice(messages)
