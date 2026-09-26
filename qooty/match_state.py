"""Match state: TeamState and MatchState hold all mutable data for a single match.

Replaces the class-level mutable state on Player / sim_game / BestOnGround
with proper instance attributes that are cleanly reset between matches.
"""

from __future__ import annotations

import random
from dataclasses import field as dc_field
from typing import Any

from qooty.constants import (
    AWAY_COORD_TO_POS,
    H2H_EXTRA_FIELDS,
    HOME_COORD_TO_POS,
    POSITION_MATCHUPS,
    STAT_CATEGORIES,
    ActionType,
    CommType,
    Possession,
    TransType,
)
from qooty.player_attributes import PlayerStats
from qooty.team_selection import RosterData


# ---------------------------------------------------------------------------
# TeamState – one per side (home / away)
# ---------------------------------------------------------------------------

class TeamState:
    """All data for one side of a match (players, positions, stats, form)."""

    def __init__(self, prefix: str) -> None:
        self.prefix: str = prefix  # "h_" or "a_"
        self.name: str = ""
        self.players: list[str] = []
        self.pos_index: list[str] = []
        self.pos_players: dict[str, str] = {}   # prefixed-pos → player name
        self.stats: dict[str, dict[str, int]] = {}  # player → {stat: count}
        self.player_form: dict[str, float] = {}     # player → BOG form score
        self.player_stats: dict[str, PlayerStats] = {}  # player → PlayerStats
        self.player_tog_seconds: dict[str, float] = {}  # player → seconds on ground

    # -- helpers --

    def pos_key(self, pos: str) -> str:
        """Return the prefixed key, e.g. ``"h_" + "RUCK" → "h_RUCK"``."""
        return f"{self.prefix}{pos}"

    def player_at(self, pos: str) -> str:
        """Player name at *pos* (un-prefixed, e.g. ``"RUCK"``)."""
        return self.pos_players[self.pos_key(pos)]

    def coord_to_pos(self) -> dict[tuple[int, int], str]:
        """Return the coordinate-to-position lookup for this team."""
        if self.prefix == "h_":
            return HOME_COORD_TO_POS
        return AWAY_COORD_TO_POS

    def opponent_pos(self, pos: str) -> str:
        """Return the un-prefixed opponent position matching *pos*."""
        return POSITION_MATCHUPS[pos]

    def nearest_on_field_player(
        self,
        coord: tuple[int, int],
        exclude: set[str] | None = None,
    ) -> tuple[str, str] | None:
        """Return ``(position, player)`` nearest to *coord*, excluding names.

        Ties are random so a fixed position does not become the universal
        fallback receiver. Followers and interchange players have no field
        coordinate and are therefore not candidates.
        """
        excluded = exclude or set()
        candidates: list[tuple[int, str, str]] = []
        for player_coord, position in self.coord_to_pos().items():
            player = self.pos_players.get(self.pos_key(position), "")
            if not player or player in excluded:
                continue
            distance = abs(player_coord[0] - coord[0]) + abs(player_coord[1] - coord[1])
            candidates.append((distance, position, player))
        if not candidates:
            return None
        nearest_distance = min(candidate[0] for candidate in candidates)
        nearest = [
            (position, player)
            for distance, position, player in candidates
            if distance == nearest_distance
        ]
        return random.choice(nearest)

    def init_stats(self) -> None:
        """Create a zeroed stat sheet for every player on the roster."""
        for player in self.players:
            self.stats[player] = dict.fromkeys(STAT_CATEGORIES, 0)
        self.player_tog_seconds = dict.fromkeys(self.players, 0.0)

    def init_form(self) -> None:
        self.player_form = dict.fromkeys(self.players, 0.0)


# ---------------------------------------------------------------------------
# MatchState – the single source of truth for a running match
# ---------------------------------------------------------------------------

class MatchState:
    """Holds *all* mutable state for one match simulation."""

    def __init__(self) -> None:
        # Teams
        self.home = TeamState("h_")
        self.away = TeamState("a_")

        # Clock
        self.game_minutes: int = 0
        self.game_seconds: int = 0
        self.qtr: int = 1
        self.q_lengths: list[int] = [0, 0, 0, 0]
        self.stoppage_time: int = 5
        self.speed: int = 4

        # Scores
        self.home_goals: int = 0
        self.home_behinds: int = 0
        self.home_score: int = 0
        self.away_goals: int = 0
        self.away_behinds: int = 0
        self.away_score: int = 0

        # Field
        self.last_play_pos_line: int = 0
        self.play_pos_line: int = 0
        self.play_pos_col: int = 0
        self.congestion_limiter: int = 0

        # Play state
        self.possession: Possession = Possession.NONE
        self.trans_type: TransType = TransType.CONTEST
        self.action_type: ActionType = ActionType.BALL_UP
        self.comm_type: CommType = CommType.RUCK_CONTEST

        # Flags
        self.left_throw_in: bool = False
        self.right_throw_in: bool = False
        self.play_restart: bool = True
        self.boundary_throw_in: bool = False
        self.center_bounce: bool = False
        self.sim_running: bool = False
        self.sim_run_speed_delay: int = 40

        # Current player tracking
        self.current_player: str = ""
        self.current_oppo: str = ""
        self.prev_player: str = ""
        self.follow_with_ball: bool = False
        self.current_chain: list[str] = []

        # Records
        self.scoreboard_log: list[str] = []
        self.h2h: list[tuple[str, str]] = []
        self.h2h_data: dict[tuple[str, str], dict[str, Any]] = {}

        # Display
        self.commentary_text: str = ""
        self.display_time: str = "0:00"
        self.match_status: str = "In Progress"

        # Interchange tracking (transient per-event, replaces globals)
        self.key_on: str = ""
        self.key_off: str = ""

        # Metadata
        self.season: str = ""
        self.round: str = ""
        self.match_id: str = ""
        self.roster_fingerprint: str = ""

    # -- convenience accessors --

    def active_team(self) -> TeamState:
        return self.home if self.possession is Possession.HOME else self.away

    def defending_team(self) -> TeamState:
        return self.away if self.possession is Possession.HOME else self.home

    def total_elapsed_minutes(self) -> int:
        """Cumulative minutes elapsed across finished quarters + current clock."""
        return self.game_minutes + sum(self.q_lengths)

    def recalc_scores(self) -> None:
        self.home_score = self.home_goals * 6 + self.home_behinds
        self.away_score = self.away_goals * 6 + self.away_behinds

    # -- initialisation from roster --

    def load_from_roster(self, r: RosterData) -> None:
        """Populate both teams from a RosterData."""
        self.home.name = r.home_team
        self.away.name = r.away_team
        self.home.players = list(r.home_players)
        self.away.players = list(r.away_players)
        self.home.pos_index = list(r.home_pos_index)
        self.away.pos_index = list(r.away_pos_index)
        self.season = r.season
        self.round = r.round
        self.match_id = r.match_id

        self.home.pos_players = dict(zip(self.home.pos_index, self.home.players))
        self.away.pos_players = dict(zip(self.away.pos_index, self.away.players))

        # Reset clock and scores for new match
        self.game_minutes = 0
        self.game_seconds = 0
        self.qtr = 1
        self.q_lengths = [0, 0, 0, 0]
        self.stoppage_time = 5
        self.home_goals = 0
        self.home_behinds = 0
        self.home_score = 0
        self.away_goals = 0
        self.away_behinds = 0
        self.away_score = 0
        self.play_pos_line = 0
        self.play_pos_col = 0
        self.congestion_limiter = 0
        self.possession = Possession.NONE
        self.trans_type = TransType.CONTEST
        self.action_type = ActionType.BALL_UP
        self.comm_type = CommType.RUCK_CONTEST
        self.play_restart = True
        self.boundary_throw_in = False
        self.center_bounce = False
        self.current_player = ""
        self.current_oppo = ""
        self.prev_player = ""
        self.follow_with_ball = False
        self.current_chain = []
        self.scoreboard_log = []

        # stat sheets & form
        self.home.init_stats()
        self.away.init_stats()
        self.home.init_form()
        self.away.init_form()
        self.home.player_stats = dict(r.home_player_stats)
        self.away.player_stats = dict(r.away_player_stats)

        # head-to-head initial matchups (first 18 = on-field positions)
        self._init_h2h()

    def get_player_stats(self, player_name: str) -> PlayerStats:
        """Look up PlayerStats by player name across home and away teams."""
        if player_name in self.home.player_stats:
            return self.home.player_stats[player_name]
        if player_name in self.away.player_stats:
            return self.away.player_stats[player_name]
        return PlayerStats()

    def is_clutch_time(self, player_aura: int = 10) -> bool:
        """Check if clutch aura conditions are active for a given player's aura rating:
        - Quarter 4
        - Score margin <= 18 points (3 goals)
        - game_minutes >= max(0, 20 - (player_aura / 100) * 20)
        """
        if self.qtr != 4:
            return False
        if abs(self.home_score - self.away_score) > 18:
            return False
        activation_minute = max(0.0, 20.0 - (player_aura / 100.0) * 20.0)
        return self.game_minutes >= activation_minute

    def get_player_tog_minutes(self, player_name: str) -> float:
        """Get accumulated on-ground minutes for a player."""
        if player_name in self.home.player_tog_seconds:
            return self.home.player_tog_seconds[player_name] / 60.0
        if player_name in self.away.player_tog_seconds:
            return self.away.player_tog_seconds[player_name] / 60.0
        return 0.0

    def get_effective_stats(self, player_name: str, opponent_name: str) -> PlayerStats:
        """Return player's stats, applying aura override or fatigue penalty as appropriate."""
        p_stats = self.get_player_stats(player_name)
        o_stats = self.get_player_stats(opponent_name)

        # 1. Aura override in clutch time takes precedence
        if p_stats.aura > o_stats.aura and self.is_clutch_time(p_stats.aura):
            return p_stats.with_aura_override()

        # 2. Check endurance fatigue threshold (if TOG exceeds max fresh minutes)
        tog_mins = self.get_player_tog_minutes(player_name)
        fresh_mins = p_stats.max_fresh_minutes()
        if tog_mins > fresh_mins:
            overtime = tog_mins - fresh_mins
            return p_stats.with_fatigue_penalty(overtime)

        return p_stats

    def _init_h2h(self) -> None:
        self.h2h = []
        self.h2h_data = {}
        for pos_key in self.home.pos_index[:18]:
            # strip prefix to get bare position
            bare = pos_key.removeprefix(self.home.prefix)
            home_player = self.home.pos_players[pos_key]
            oppo_bare = POSITION_MATCHUPS.get(bare, bare)
            away_key = self.away.pos_key(oppo_bare)
            away_player = self.away.pos_players[away_key]
            matchup = (home_player, away_player)
            self.h2h.append(matchup)
            self.h2h_data[matchup] = dict.fromkeys(H2H_EXTRA_FIELDS, 0)
