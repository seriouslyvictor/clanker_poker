"""
archetypes.py — Archetype definitions and game-start assignment.

D-09: Data-driven config — adding a new archetype requires only a new entry in ARCHETYPES.
D-08: assign_archetypes() shuffles ARCHETYPES randomly so each player gets a unique one.
D-10: 4 baseline archetypes matching AI-06 requirements for viewer-legible style contrast.
"""
from __future__ import annotations
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Archetype:
    name: str
    description: str           # Used verbatim in system prompt (D-04)
    hand_looseness: float      # Min win_probability to call/stay in hand
    raise_freq: float          # Min win_probability to raise
    bluff_freq: float          # Probability of raising regardless of hand strength
    tilt_threshold: float      # Reserved for future tilt mechanic (v2)


# Bias thresholds tuned for visible differentiation in the 0.30-0.70 win_probability band
# (Pitfall 4 in RESEARCH.md — archetypes must differ where it counts)
ARCHETYPES: list[Archetype] = [
    Archetype(
        name="Gunslinger",
        description=(
            "An aggressive, fearless raiser who applies maximum pressure at every opportunity. "
            "You believe attack is the best defense. You raise to define your range, punish limpers, "
            "and take down pots before showdown. Even with the nuts you raise — trapping is not your style."
        ),
        hand_looseness=0.30,
        raise_freq=0.40,
        bluff_freq=0.15,
        tilt_threshold=0.80,
    ),
    Archetype(
        name="Rock",
        description=(
            "A tight, disciplined folder who only commits chips with premium holdings. "
            "You fold marginal hands without hesitation. Patience is your edge. "
            "You call when the math is clear and raise only with the best of it."
        ),
        hand_looseness=0.65,
        raise_freq=0.80,
        bluff_freq=0.02,
        tilt_threshold=0.95,
    ),
    Archetype(
        name="Grinder",
        description=(
            "A tight-solid, position-aware player who grinds out profit through correct fundamentals. "
            "You respect pot odds, play position, and avoid marginal spots. "
            "You raise for value and protection — rarely for show."
        ),
        hand_looseness=0.55,
        raise_freq=0.65,
        bluff_freq=0.05,
        tilt_threshold=0.90,
    ),
    Archetype(
        name="Chaotic Optimist",
        description=(
            "An eternally optimistic caller who believes every hand has a chance. "
            "You call anything because you might hit. Folding feels like giving up, "
            "and you never give up. The turn or river will save you — it always does."
        ),
        hand_looseness=0.10,
        raise_freq=0.35,
        bluff_freq=0.20,
        tilt_threshold=0.50,
    ),
]


def assign_archetypes(players: list) -> dict[str, Archetype]:
    """
    Randomly shuffle ARCHETYPES and assign one unique archetype per player (D-08).

    Args:
        players: List of Player objects with .id attribute.
                 Must have len(players) <= len(ARCHETYPES).

    Returns:
        dict mapping player.id -> Archetype (unique assignment, no repeats)
    """
    shuffled = list(ARCHETYPES[: len(players)])
    random.shuffle(shuffled)
    return {player.id: arch for player, arch in zip(players, shuffled)}
