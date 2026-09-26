import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from qooty.paths import PROJECT_ROOT
from qooty.player_attributes import PlayerStats
from qooty.team_library import TeamLibrary, match_roster, team_from_roster
from qooty.team_selection import DuplicatePlayerNameError, load_roster


class TeamLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / 'saved_teams'
        self.library = TeamLibrary(self.directory)
        self.roster = load_roster(PROJECT_ROOT)
        self.home = team_from_roster(self.roster, 'home')
        self.away = team_from_roster(self.roster, 'away')

    def test_restart_round_trip_preserves_every_field(self):
        player = replace(self.home.players[0], name="Jose O'Neil", attributes=PlayerStats(1, 2, 3, 4, 5, 6, 7))
        team = replace(self.home, name='Team / ../ Footy', players=(player,) + self.home.players[1:])
        saved = self.library.save(team)
        restarted = TeamLibrary(self.directory)
        self.assertEqual(restarted.list_teams(), ([saved], []))
        self.assertEqual(replace(saved, team_id=None), team)
        payload = json.loads(next(self.directory.glob('*.json')).read_text(encoding='utf-8'))
        self.assertEqual(set(payload), {'schema_version', 'team_id', 'name', 'players'})
        self.assertEqual(payload['players'][0]['attributes']['aura'], 7)

    def test_non_ascii_names_rejected_in_rosters_and_saved_teams(self):
        for name in ('Café', 'Jose\u0301', '王', 'Team’s'):
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, 'please remove accents'):
                    replace(self.roster, home_team=name)
                with self.assertRaisesRegex(ValueError, 'please remove accents'):
                    replace(self.roster, away_players=[name] + self.roster.away_players[1:])
                with self.assertRaisesRegex(ValueError, 'please remove accents'):
                    self.library.save(replace(self.home, name=name))
                player = replace(self.home.players[0], name=name)
                with self.assertRaisesRegex(ValueError, 'please remove accents'):
                    self.library.save(replace(self.home, players=(player,) + self.home.players[1:]))
        self.assertFalse(self.directory.exists())

    def test_same_name_creates_independent_teams_and_update_preserves_id(self):
        first = self.library.save(self.home)
        second = self.library.save(first)
        self.assertNotEqual(first.team_id, second.team_id)
        updated = self.library.save(replace(first, name='Updated'), update_id=first.team_id)
        self.assertEqual(updated.team_id, first.team_id)
        teams, errors = self.library.list_teams()
        self.assertCountEqual(teams, [updated, second])
        self.assertFalse(errors)

    def test_swapping_sides_rewrites_only_position_prefix(self):
        roster = match_roster(self.away, self.home, 'S42', 'R03', '42')
        self.assertEqual(roster.home_players, self.roster.away_players)
        self.assertEqual(roster.home_player_stats, self.roster.away_player_stats)
        self.assertEqual(roster.home_pos_index, self.roster.home_pos_index)
        self.assertEqual((roster.season, roster.round, roster.match_id), ('S42', 'R03', '42'))
        from qooty.match_state import MatchState
        state = MatchState()
        state.load_from_roster(roster)
        self.assertEqual(state.home.player_at('RUCK'), roster.home_players[15])

    def test_cross_team_duplicate_names_rejected_before_match(self):
        with self.assertRaises(DuplicatePlayerNameError):
            match_roster(self.home, self.home)

    def test_bad_records_skipped_and_preserved(self):
        saved = self.library.save(self.home)
        path = self.directory / f'{saved.team_id}.json'
        valid = path.read_text(encoding='utf-8')
        for change in ('version', 'stats', 'players', 'position', 'id', 'json'):
            with self.subTest(change=change):
                data = json.loads(valid)
                if change == 'version': data['schema_version'] = 99
                if change == 'stats': del data['players'][0]['attributes']['aura']
                if change == 'players': data['players'] = None
                if change == 'position': data['players'][0]['position'] = []
                if change == 'id': data['team_id'] = '../escape'
                path.write_text('{' if change == 'json' else json.dumps(data), encoding='utf-8')
                before = path.read_bytes()
                teams, errors = self.library.list_teams()
                self.assertFalse(teams)
                self.assertEqual(len(errors), 1)
                self.assertIn(path.name, errors[0])
                self.assertEqual(path.read_bytes(), before)

    def test_bad_file_does_not_hide_valid_team(self):
        saved = self.library.save(self.home)
        (self.directory / 'broken.json').write_text('{', encoding='utf-8')
        teams, errors = self.library.list_teams()
        self.assertEqual(teams, [saved])
        self.assertEqual(len(errors), 1)

    def test_failed_replace_preserves_original_and_cleans_temp(self):
        saved = self.library.save(self.home)
        path = self.directory / f'{saved.team_id}.json'
        before = path.read_bytes()
        with patch('qooty.team_library.os.replace', side_effect=PermissionError('read only')):
            with self.assertRaises(PermissionError):
                self.library.save(self.away, update_id=saved.team_id)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(list(self.directory.glob('*.tmp')), [])

    def test_invalid_teams_rejected_without_creating_directory(self):
        for team in (replace(self.home, name=''), replace(self.home, players=self.home.players[:19]),
                     replace(self.home, players=(self.home.players[0],) * 20),
                     replace(self.home, players=(replace(self.home.players[0],
                         attributes=PlayerStats(101, 0, 0, 0, 0, 0, 0)),) + self.home.players[1:]),
                     replace(self.home, players=(replace(self.home.players[0],
                         attributes=PlayerStats(1.5, 0, 0, 0, 0, 0, 0)),) + self.home.players[1:])):
            with self.assertRaises(ValueError): self.library.save(team)
        self.assertFalse(self.directory.exists())

    def test_empty_library_and_stable_default_directory(self):
        self.assertEqual(self.library.list_teams(), ([], []))
        self.assertFalse(self.directory.exists())
        previous = Path.cwd()
        try:
            os.chdir(self.temp.name)
            self.assertEqual(TeamLibrary().directory, PROJECT_ROOT / 'saved_teams')
        finally:
            os.chdir(previous)


if __name__ == '__main__':
    unittest.main()
