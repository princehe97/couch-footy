"""Load team rosters from TeamSelection.csv using the Python standard library."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

def _agent_log(location: str, message: str, data: dict | None = None, hypothesis_id: str = "?") -> None:
	"""Compatibility no-op for retired development diagnostics."""
	return None

CSV_NAME = "TeamSelection.csv"


from qooty.player_attributes import DEFAULT_STATS, PlayerStats


class DuplicatePlayerNameError(ValueError):
	"""Two roster entries share a player name."""


class UnsupportedNameError(ValueError):
	"""A team or player name contains unsupported non-ASCII characters."""


def validate_name_characters(name: str, label: str) -> None:
	if not name.isascii():
		raise UnsupportedNameError(
			f'{label}: please remove accents (e.g. José -> Jose), emojis and special symbols.'
		)


@dataclass(frozen=True)
class RosterData:
	home_team: str
	away_team: str
	season: str
	round: str
	match_id: str
	home_pos_index: list[str]
	home_players: list[str]
	away_pos_index: list[str]
	away_players: list[str]
	source: str
	home_player_stats: dict[str, PlayerStats] = field(default_factory=dict)
	away_player_stats: dict[str, PlayerStats] = field(default_factory=dict)


	def __post_init__(self) -> None:
		validate_name_characters(self.home_team, "Home team name")
		validate_name_characters(self.away_team, "Away team name")
		seen: dict[str, str] = {}
		for side, players in (("Home", self.home_players), ("Away", self.away_players)):
			for number, name in enumerate(players, 1):
				key = name.strip().casefold()
				location = f"{side} player {number}"
				validate_name_characters(name, location)
				if key in seen:
					raise DuplicatePlayerNameError(
						f'Duplicate player name "{name.strip()}" at {seen[key]} and {location}. '
						"Every player across both teams must have a unique name."
					)
				seen[key] = location


def _parse_stat_val(val: str, default: int) -> int:
	s = val.strip()
	if not s:
		return default
	try:
		return int(float(s))
	except ValueError:
		return default


def _extract_player_stats(row_slice: list[str], player_name: str, is_aura_tenth: bool = True) -> PlayerStats:
	if len(row_slice) < 7 or not any(c.strip() for c in row_slice[:7]):
		stats = PlayerStats()
	else:
		str_v = _parse_stat_val(row_slice[0], DEFAULT_STATS["strength"])
		spd_v = _parse_stat_val(row_slice[1], DEFAULT_STATS["speed"])
		agi_v = _parse_stat_val(row_slice[2], DEFAULT_STATS["agility"])
		skl_v = _parse_stat_val(row_slice[3], DEFAULT_STATS["skill"])
		end_v = _parse_stat_val(row_slice[4], DEFAULT_STATS["endurance"])
		prs_v = _parse_stat_val(row_slice[5], DEFAULT_STATS["pressure"])
		aur_v = _parse_stat_val(row_slice[6], DEFAULT_STATS["aura"])
		stats = PlayerStats(
			strength=str_v,
			speed=spd_v,
			agility=agi_v,
			skill=skl_v,
			endurance=end_v,
			pressure=prs_v,
			aura=aur_v,
		)
	stats.validate(player_name)
	return stats


def _parse_csv(path: Path) -> RosterData:
	try:
		with path.open(newline="", encoding="utf-8-sig") as f:
			rows = list(csv.reader(f))
	except UnicodeDecodeError as exc:
		raise UnsupportedNameError(
			f'{path.name}: some letters or symbols could not be read. '
			'Please remove accents (e.g. José -> Jose), emojis and special symbols, '
			'then save the file as CSV UTF-8.'
		) from exc

	def nonempty(r: list[str]) -> bool:
		return bool(r) and any(c.strip() for c in r)

	rows = [r for r in rows if nonempty(r) and not (r[0].strip().startswith("#"))]

	if len(rows) < 25:
		raise ValueError(
			f"{path.name}: expected season, round, 2 team lines, 1 header row, and 20 roster rows "
			f"(got {len(rows)} non-empty rows). See TeamSelection.sample.csv."
		)

	season = rows[0][1].strip() if len(rows[0]) > 1 and rows[0][1].strip() else "0"
	round_val = rows[1][1].strip() if len(rows[1]) > 1 and rows[1][1].strip() else "0"
	home_team = rows[2][1].strip() if len(rows[2]) > 1 else ""
	away_team = rows[3][1].strip() if len(rows[3]) > 1 else ""
	match_id = rows[4][1].strip() if len(rows[4]) > 1 and rows[4][1].strip() else "0"

	header = [c.strip().lower() for c in rows[5]]
	expected = [
		"home_pos",
		"home_player",
		"h_str",
		"h_spd",
		"h_agi",
		"h_skl",
		"h_end",
		"h_prs",
		"h_aur",
		"away_pos",
		"away_player",
	]
	if header[: len(expected)] != expected:
		raise ValueError(f"{path.name}: row 6 must be header {expected}, got {header[:11]}")

	body = rows[6:26]
	if len(body) != 20:
		raise ValueError(f"{path.name}: need exactly 20 roster rows after header, got {len(body)}")

	hpi, hpl, api, apl = ([] for _ in range(4))
	h_stats_map: dict[str, PlayerStats] = {}
	a_stats_map: dict[str, PlayerStats] = {}

	for i, r in enumerate(body):
		pad = r + [""] * (18 - len(r))
		h_pos = pad[0].strip()
		h_player = pad[1].strip()
		a_pos = pad[9].strip()
		a_player = pad[10].strip()

		hpi.append(h_pos)
		hpl.append(h_player)
		api.append(a_pos)
		apl.append(a_player)

		if not hpi[-1] or not api[-1]:
			raise ValueError(f"{path.name}: roster row {i + 7}: home_pos and away_pos are required.")

		h_stats = _extract_player_stats(pad[2:9], h_player)
		a_stats = _extract_player_stats(pad[11:18], a_player)
		h_stats_map[h_player] = h_stats
		a_stats_map[a_player] = a_stats

	return RosterData(
		home_team=home_team,
		away_team=away_team,
		season=season,
		round=round_val,
		match_id=match_id,
		home_pos_index=hpi,
		home_players=hpl,
		away_pos_index=api,
		away_players=apl,
		source=str(path),
		home_player_stats=h_stats_map,
		away_player_stats=a_stats_map,
	)


def load_roster(base_dir: Path | None = None) -> RosterData:
	"""
	Load roster from ``TeamSelection.csv``.

	:param base_dir: Directory containing team files (default: current working directory).
	"""
	root = base_dir or Path.cwd()
	csv_path = root / CSV_NAME
	_agent_log(
		"team_selection.load_roster",
		"enter",
		{"cwd": str(root.resolve()), "csv_exists": csv_path.is_file()},
		"H1",
	)
	try:
		if csv_path.is_file():
			r = _parse_csv(csv_path)
			_agent_log("team_selection.load_roster", "csv_ok", {"source": r.source, "home_team": r.home_team}, "H1")
			return r
		_agent_log("team_selection.load_roster", "no_team_file", {}, "H1")
		raise FileNotFoundError(
			f"No {CSV_NAME} in {root.resolve()}. "
			f"Provide {CSV_NAME} to import a roster."
		)
	except Exception as e:
		_agent_log(
			"team_selection.load_roster",
			"exception",
			{"type": type(e).__name__, "msg": str(e)[:800]},
			"H1",
		)
		raise
