"""Enums, colours, field-position mappings, and other constants used across the engine."""

from __future__ import annotations

from enum import Enum


# ---------------------------------------------------------------------------
# Colours (RGB tuples used by pygame)
# ---------------------------------------------------------------------------

BLUEY_GREEN = (0, 200, 200)
LIGHT_GREEN = (100, 255, 100)
GREEN = (0, 255, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
SOFT_RED = (255, 150, 150)
BLUE = (0, 0, 255)
SOFT_BLUE = (150, 150, 255)
LIGHT_GREY = (210, 210, 210)
DARK_GREY = (80, 80, 80)
BLACK = (0, 0, 0)

# ---------------------------------------------------------------------------
# Screen & Canvas dimensions
# ---------------------------------------------------------------------------

# Native coordinate space for game logic, UI layouts, backgrounds, and simulation
CANVAS_WIDTH = 640
CANVAS_HEIGHT = 400

# Scaling factor (1.5 = scaled down 25% from double size: 960x600, maintaining exact 16:10 aspect ratio)
WINDOW_SCALE = 1.5

# Actual display window dimensions
WINDOW_WIDTH = int(CANVAS_WIDTH * WINDOW_SCALE)   # 960
WINDOW_HEIGHT = int(CANVAS_HEIGHT * WINDOW_SCALE) # 600

# Backward-compatibility aliases
SCREEN_WIDTH = WINDOW_WIDTH
SCREEN_HEIGHT = WINDOW_HEIGHT

# ---------------------------------------------------------------------------
# Stat categories tracked per player
# ---------------------------------------------------------------------------

STAT_CATEGORIES: list[str] = ["HO", "K", "M", "HB", "T", "FF", "FA", "G", "B", "SI", "INT", "TO", "CW", "CL", "R50", "I50", "BNC", "CP", "UP", "CM", "UM", "T50", "SPO", "SMO", "D", "DT"]

# ---------------------------------------------------------------------------
# String enums – inherit from *str* so they compare naturally with plain
# strings, which keeps backward compatibility with commentary / display code.
# ---------------------------------------------------------------------------


class Possession(str, Enum):
    HOME = "Home"
    AWAY = "Away"
    NONE = "None"

    @property
    def opposite(self) -> "Possession":
        if self is Possession.HOME:
            return Possession.AWAY
        if self is Possession.AWAY:
            return Possession.HOME
        return Possession.NONE


class TransType(str, Enum):
    CONTEST = "Contest"
    DEFENDING = "Defending"
    CARRYING = "Carrying"


class ActionType(str, Enum):
    BALL_UP = "Ball Up"
    RUCKING = "Rucking"
    KICK = "Kick"
    EFFECTIVE_KICK = "EffectiveKick"
    HANDBALL = "Handball"
    MARK = "Mark"
    TACKLE = "Tackle"
    FREE_KICK = "Free Kick"
    FREE_AGAINST = "Free Against"
    GOAL = "Goal"
    BEHIND = "Behind"
    RUN = "Run"
    LOSE_BALL = "Lose Ball"
    BALL_GET = "BallGet"
    FINDS_SPACE = "Finds Space"
    SPILLS_FREE = "Spills Free"
    DISPOSSESSION = "Dispossession"
    OUT_ON_FULL = "Out on the Full"


class CommType(str, Enum):
    RUCK_CONTEST = "Ruck Contest"
    LOOSE_BALL_GET = "Loose Ball Get"
    FREE_KICK_PAID = "Free Kick Paid"
    FREE_PAID_AGAINST = "Free Paid Against"
    HARD_BALL_GET = "Hard Ball Get"
    CONTESTED_MARK = "Contested Mark Taken"
    SPOIL = "Spoil"
    UNCONTESTED_MARK = "Uncontested Mark Taken"
    NO_MARK = "No Mark"
    RELEASING_HANDBALL = "Releasing Handball"
    BALL_SPILLS_FREE = "Ball Spills Free"
    TACKLE_LAID = "Tackle Laid"
    PLAYER_DISPOSSESSED = "Player Dispossessed"
    BREAKAWAY = "Breakaway"
    BALL_UP_FOR_GRABS = "Ball Up For Grabs"
    CHIP_FORWARDS = "Chip Forwards"
    CHIP_SIDEWAYS = "Chip Sideways"
    HANDBALL_FORWARDS = "Handball Forwards"
    HANDBALL_SIDEWAYS = "Handball Sideways"
    RUN_AND_BOUNCE = "Run and Bounce"
    LONG_BOMB = "Long Bomb"
    TORPEDO_KICK = "Torpedo Kick"
    BOUNDARY_THROW_IN = "Boundary Throw In"
    NO_SCORE = "No Score"
    GOAL_KICKED = "Goal Kicked"
    BEHIND_KICKED = "Behind Kicked"
    SMOTHERED = "Smothered"


# ---------------------------------------------------------------------------
# On-field positions (without team prefix)
# ---------------------------------------------------------------------------

FIELD_POSITIONS: list[str] = [
    "rBP", "FB", "lBP",
    "rHBF", "CHB", "lHBF",
    "rW", "C", "lW",
    "rHFF", "CHF", "lHFF",
    "rFP", "FF", "lFP",
    "RUCK", "RR", "R",
    "INT1", "INT2",
]

# Maps each on-field position to its direct opponent (prefix-free).
POSITION_MATCHUPS: dict[str, str] = {
    "rBP": "lFP", "FB": "FF", "lBP": "rFP",
    "rHBF": "lHFF", "CHB": "CHF", "lHBF": "rHFF",
    "rW": "lW", "C": "C", "lW": "rW",
    "rHFF": "lHBF", "CHF": "CHB", "lHFF": "rHBF",
    "rFP": "lBP", "FF": "FB", "lFP": "rBP",
    "RUCK": "RUCK", "RR": "RR", "R": "R",
}

# ---------------------------------------------------------------------------
# Field coordinate system
#
# The pitch is a 3×5 grid  (col ∈ {-1, 0, 1}, line ∈ {-2, -1, 0, 1, 2}).
# Home attacks towards *negative* line numbers; Away attacks towards
# *positive* line numbers.
#
# Each dict maps (col, line) → position name *for that team*.
# ---------------------------------------------------------------------------

HOME_COORD_TO_POS: dict[tuple[int, int], str] = {
    (-1, 2): "lFP",  (0, 2): "FF",   (1, 2): "rFP",
    (-1, 1): "lHFF", (0, 1): "CHF",  (1, 1): "rHFF",
    (-1, 0): "lW",   (0, 0): "C",    (1, 0): "rW",
    (-1, -1): "lHBF", (0, -1): "CHB", (1, -1): "rHBF",
    (-1, -2): "lBP",  (0, -2): "FB",  (1, -2): "rBP",
}

AWAY_COORD_TO_POS: dict[tuple[int, int], str] = {
    (-1, 2): "rBP",  (0, 2): "FB",   (1, 2): "lBP",
    (-1, 1): "rHBF", (0, 1): "CHB",  (1, 1): "lHBF",
    (-1, 0): "rW",   (0, 0): "C",    (1, 0): "lW",
    (-1, -1): "rHFF", (0, -1): "CHF", (1, -1): "lHFF",
    (-1, -2): "rFP",  (0, -2): "FF",  (1, -2): "lFP",
}

# ---------------------------------------------------------------------------
# Weather / speed look-up tables
# ---------------------------------------------------------------------------

#  weather → trans_type → speed (seconds per tick)
WEATHER_SPEED: dict[str, dict[str, int]] = {
    "Fine":   {"Contest": 4, "Defending": 3, "Carrying": 6},
    "Warm":   {"Contest": 4, "Defending": 3, "Carrying": 7},
    "Cloudy": {"Contest": 5, "Defending": 4, "Carrying": 7},
    "Rainy":  {"Contest": 6, "Defending": 5, "Carrying": 7},
}

SIM_SPEED_DELAY: dict[str, int] = {
    "Slow": 200,
    "Normal": 80,
    "Fast": 3,
}

# Head-to-head extra tracking fields
H2H_EXTRA_FIELDS: list[str] = ["Start", "End", "Outcome"]
