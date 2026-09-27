"""Player attributes data model and calculation helpers for contest & skill resolution."""

from __future__ import annotations

from dataclasses import dataclass

STAT_NAMES: list[str] = ["strength", "speed", "agility", "skill", "endurance", "pressure", "aura"]

DEFAULT_STATS: dict[str, int] = {
    "strength": 15,
    "speed": 15,
    "agility": 15,
    "skill": 15,
    "endurance": 15,
    "pressure": 15,
    "aura": 10,
}

MAX_TOTAL_POINTS: int = 100


class SkillAllocationError(ValueError):
    """A player's skill values break the roster allocation rules."""


@dataclass(frozen=True)
class PlayerStats:
    """Immutable stat block for an individual player."""

    strength: int = 15
    speed: int = 15
    agility: int = 15
    skill: int = 15
    endurance: int = 15
    pressure: int = 15
    aura: int = 10

    def total(self) -> int:
        """Return the sum of all 7 stat points."""
        return (
            self.strength
            + self.speed
            + self.agility
            + self.skill
            + self.endurance
            + self.pressure
            + self.aura
        )

    def validate(self, player_name: str = "Player") -> None:
        """Validate that stats are non-negative and do not exceed the point budget."""
        for stat in STAT_NAMES:
            val = getattr(self, stat)
            if val < 0:
                raise SkillAllocationError(
                    f"Invalid stat for {player_name}: {stat} cannot be negative (got {val})."
                )

        tot = self.total()
        if tot > MAX_TOTAL_POINTS:
            raise SkillAllocationError(
                f"Stat allocation exceeded for {player_name}: total is {tot} (max allowed {MAX_TOTAL_POINTS})."
            )

    def get_stat_value(self, stat_name: str) -> int:
        """Get the integer value of a named stat."""
        return getattr(self, stat_name.lower())

    def contest_probability(self, my_stat_name: str, opponent_stat_value: int) -> float:
        """Return a 30-70% contest chance; two zero ratings give equal odds."""
        my_val = max(0, self.get_stat_value(my_stat_name))
        opp_val = max(0, opponent_stat_value)

        total = my_val + opp_val
        if total == 0:
            return 0.50

        prob = (my_val / total) * 0.40 + 0.30
        return max(0.30, min(0.70, prob))

    def composite_contest_probability(
        self,
        stat_names: tuple[str, str],
        opponent_stats: "PlayerStats",
    ) -> float:
        """Combine two stats multiplicatively; two zero ratings give equal odds."""
        stat1, stat2 = stat_names
        my_val1 = max(0, self.get_stat_value(stat1))
        my_val2 = max(0, self.get_stat_value(stat2))
        opp_val1 = max(0, opponent_stats.get_stat_value(stat1))
        opp_val2 = max(0, opponent_stats.get_stat_value(stat2))

        my_rating = my_val1 * my_val2
        opp_rating = opp_val1 * opp_val2

        total = my_rating + opp_rating
        if total == 0:
            return 0.50

        prob = (my_rating / total) * 0.40 + 0.30
        return max(0.30, min(0.70, prob))

    def skill_probability(self) -> float:
        """Return the chance of a successful disposal, independent of an opponent."""
        val = max(0, min(100, self.skill))
        return 0.50 + val * 0.0015

    def interchange_weight(self) -> int:
        """Lower endurance makes a player more likely to be substituted off."""
        return max(1, 101 - self.endurance)

    def max_fresh_minutes(self) -> float:
        """Return on-ground minutes before fatigue starts."""
        if self.endurance >= 100:
            return 140.0
        elif self.endurance <= 0:
            return 60.0
        elif self.endurance <= 50:
            return 60.0 + 48.0 * (self.endurance / 50.0)
        else:
            return 108.0 + 32.0 * ((self.endurance - 50.0) / 50.0)

    def with_fatigue_penalty(self, overtime_minutes: float = 0.0) -> "PlayerStats":
        """Reduce physical stats, skill and pressure; leave endurance and aura unchanged."""
        penalty = min(0.50, 0.10 + max(0.0, overtime_minutes) * 0.015)
        mult = 1.0 - penalty
        return PlayerStats(
            strength=max(0, int(round(self.strength * mult))),
            speed=max(0, int(round(self.speed * mult))),
            agility=max(0, int(round(self.agility * mult))),
            skill=max(0, int(round(self.skill * mult))),
            endurance=self.endurance,
            pressure=max(0, int(round(self.pressure * mult))),
            aura=self.aura,
        )

    def with_aura_override(self) -> "PlayerStats":
        """Return an overpowered copy with on-field stats set to 100, keeping aura unchanged."""
        return PlayerStats(
            strength=100,
            speed=100,
            agility=100,
            skill=100,
            endurance=100,
            pressure=100,
            aura=self.aura,
        )
