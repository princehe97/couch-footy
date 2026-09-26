"""Channel-independent, versioned storage for individual teams."""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from uuid import UUID, uuid4

from qooty.paths import PROJECT_ROOT
from qooty.player_attributes import PlayerStats, STAT_NAMES
from qooty.team_selection import RosterData

POSITIONS = frozenset(('rBP', 'FB', 'lBP', 'rHBF', 'CHB', 'lHBF', 'rW', 'C',
                       'lW', 'rHFF', 'CHF', 'lHFF', 'rFP', 'FF', 'lFP',
                       'RUCK', 'RR', 'R', 'INT1', 'INT2'))


@dataclass(frozen=True)
class TeamPlayer:
    name: str
    position: str
    attributes: PlayerStats


@dataclass(frozen=True)
class Team:
    name: str
    players: tuple[TeamPlayer, ...]
    team_id: str | None = None

    def validate(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError('A team name is required.')
        if len(self.players) != 20:
            raise ValueError('A team must have exactly 20 players.')
        names = set()
        for player in self.players:
            if not isinstance(player.name, str) or not player.name.strip():
                raise ValueError('Every player needs a name.')
            key = player.name.strip().casefold()
            if key in names:
                raise ValueError(f'Duplicate player name: {player.name}')
            names.add(key)
            if any(type(getattr(player.attributes, stat)) is not int for stat in STAT_NAMES):
                raise ValueError(f'{player.name}: allocations must be whole numbers.')
            player.attributes.validate(player.name)
        if {p.position for p in self.players} != POSITIONS:
            raise ValueError('A team must contain each of the 20 field positions exactly once.')


def team_from_roster(roster: RosterData, side: str) -> Team:
    positions = getattr(roster, f'{side}_pos_index')
    names = getattr(roster, f'{side}_players')
    stats = getattr(roster, f'{side}_player_stats')
    if len(positions) != len(names):
        raise ValueError('Each player needs a position.')
    team = Team(getattr(roster, f'{side}_team'), tuple(
        TeamPlayer(name, pos.removeprefix('h_').removeprefix('a_'), stats.get(name, PlayerStats()))
        for pos, name in zip(positions, names)))
    team.validate()
    return team


def match_roster(home: Team, away: Team, season='0', round_number='0', match_id='0') -> RosterData:
    home.validate()
    away.validate()
    return RosterData(
        home.name, away.name, season, round_number, match_id,
        ['h_' + p.position for p in home.players], [p.name for p in home.players],
        ['a_' + p.position for p in away.players], [p.name for p in away.players],
        'Team selection', {p.name: p.attributes for p in home.players},
        {p.name: p.attributes for p in away.players})


class TeamLibrary:
    def __init__(self, directory: Path | None = None):
        self.directory = directory if directory is not None else PROJECT_ROOT / 'saved_teams'

    def _path(self, team_id: str) -> Path:
        # Canonical UUIDs prevent user-controlled paths and ambiguous filenames.
        if str(UUID(team_id)) != team_id:
            raise ValueError('Invalid team ID.')
        return self.directory / f'{team_id}.json'

    def save(self, team: Team, *, update_id: str | None = None) -> Team:
        team.validate()
        saved = replace(team, team_id=update_id or str(uuid4()))
        destination = self._path(saved.team_id)
        if update_id is not None and not destination.is_file():
            raise ValueError('The team to update no longer exists. Save as new instead.')
        payload = dict(schema_version=1, team_id=saved.team_id, name=saved.name,
                       players=[asdict(p) for p in saved.players])
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.directory,
                                             suffix='.tmp', delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(payload, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return saved

    def load(self, path: Path) -> Team:
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or type(data.get('schema_version')) is not int or data['schema_version'] != 1:
            raise ValueError('Unsupported team file version.')
        try:
            if self._path(data['team_id']).name != path.name:
                raise ValueError('Team ID does not match the filename.')
            players = []
            for p in data['players']:
                if set(p['attributes']) != set(STAT_NAMES):
                    raise ValueError('All seven allocations are required.')
                players.append(TeamPlayer(p['name'], p['position'], PlayerStats(**p['attributes'])))
            team = Team(data['name'], tuple(players), data['team_id'])
            team.validate()
            return team
        except (KeyError, TypeError, AttributeError) as exc:
            raise ValueError('Malformed team record.') from exc

    def list_teams(self) -> tuple[list[Team], list[str]]:
        teams, errors = [], []
        try:
            paths = sorted(self.directory.glob('*.json'))
        except OSError as exc:
            return [], [f'Cannot read saved teams: {exc}']
        for path in paths:
            try:
                teams.append(self.load(path))
            except (OSError, ValueError) as exc:
                errors.append(f'{path.name}: {exc}')
        return sorted(teams, key=lambda t: (t.name.casefold(), t.team_id)), errors
