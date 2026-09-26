"""Drive the real setup screen with SDL's headless display and mouse events."""
import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pygame

from qooty.constants import WINDOW_SCALE
from qooty.paths import PROJECT_ROOT
from qooty.team_library import TeamLibrary, team_from_roster
from qooty.team_selection import load_roster
from qooty.team_setup import SetupClosed, TeamSetup


def click(x, y):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1,
                              pos=(round(x * WINDOW_SCALE), round(y * WINDOW_SCALE)))


class SetupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((640, 400))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.library = TeamLibrary(Path(self.temp.name))
        self.surface = pygame.Surface((640, 400))

    def drive(self, setup, frames):
        with patch.object(setup, 'events', side_effect=frames):
            return setup.run()

    def test_save_both_restart_without_csv_and_start_with_saved_allocations(self):
        setup = TeamSetup(self.surface, self.library)
        expected = setup.selected.copy()
        self.drive(setup, [[click(50, 330)], [click(400, 365)],
                           [click(370, 330)], [click(400, 365)], [click(40, 370)]])
        self.assertEqual(len(self.library.list_teams()[0]), 2)
        with patch('qooty.team_setup.load_roster', side_effect=FileNotFoundError('No CSV')):
            reopened = TeamSetup(self.surface, TeamLibrary(self.library.directory))
        teams = reopened.teams
        home_row = next(i for i, t in enumerate(teams) if t.name == expected[0].name)
        away_row = next(i for i, t in enumerate(teams) if t.name == expected[1].name)
        result = self.drive(reopened, [[click(200, 85)], [click(100, 80 + home_row * 36)],
                                       [click(515, 85)], [click(100, 80 + away_row * 36)],
                                       [click(530, 370)]])
        self.assertEqual(result.home_players, [p.name for p in expected[0].players])
        self.assertEqual(result.away_player_stats, {p.name: p.attributes for p in expected[1].players})

    def test_duplicate_selection_blocks_start_and_allows_back(self):
        setup = TeamSetup(self.surface, self.library)
        setup.selected[1] = setup.selected[0]
        with patch.object(setup, 'message') as message:
            result = self.drive(setup, [[click(530, 370)], [click(40, 370)]])
        self.assertIsNone(result)
        self.assertIn('Duplicate player', message.call_args.args[0])

    def test_update_requires_confirmation_and_preserves_identity(self):
        setup = TeamSetup(self.surface, self.library)
        target = self.library.save(setup.selected[1])
        setup.refresh()
        with patch.object(setup, 'pick', return_value=target), patch.object(setup, 'message', return_value=False):
            setup.save(0, update=True)
        self.assertEqual(self.library.list_teams()[0], [target])
        with patch.object(setup, 'pick', return_value=target), patch.object(setup, 'message', return_value=True):
            setup.save(0, update=True)
        saved = self.library.list_teams()[0][0]
        self.assertEqual(saved.team_id, target.team_id)
        self.assertEqual(saved.players, setup.selected[0].players)

    def test_save_failure_keeps_team_playable(self):
        setup = TeamSetup(self.surface, self.library)
        before = setup.selected[0]
        with patch.object(self.library, 'save', side_effect=PermissionError('read only')), patch.object(setup, 'message') as message:
            setup.save(0)
        self.assertEqual(setup.selected[0], before)
        self.assertIn('not saved', message.call_args.args[0])
        self.assertIsNotNone(self.drive(setup, [[click(530, 370)]]))

    def test_metadata_fields_and_roster_preview_paging(self):
        setup = TeamSetup(self.surface, self.library)
        result = self.drive(setup, [[click(295, 295)], [click(90, 52)],
                                    [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_x, unicode='X')],
                                    [click(530, 370)]])
        self.assertEqual(setup.pages[0], 1)
        self.assertTrue(result.season.endswith('X'))

    def test_quit_exits_setup(self):
        setup = TeamSetup(self.surface, self.library)
        pygame.event.clear()
        pygame.event.post(pygame.event.Event(pygame.QUIT))
        with self.assertRaises(SetupClosed): setup.run()

    def edit_frames(self, setup, frames):
        with patch.object(setup, 'events', side_effect=frames):
            setup.edit(0)

    def rename_frames(self, value):
        return [[click(350, 110)],
                [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, unicode='a', mod=pygame.KMOD_CTRL)],
                [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_x, unicode=value)]]

    def test_edit_saved_team_rename_reallocate_swap_and_reload(self):
        setup = TeamSetup(self.surface, self.library)
        original = self.library.save(setup.selected[0])
        setup.selected[0] = original
        self.edit_frames(setup, self.rename_frames('New player') + [
            [click(480, 140)], [click(570, 163)],
            [click(400, 334)], [click(285, 335)], [click(100, 105)],
            [click(520, 382)]])
        saved = TeamLibrary(self.library.directory).list_teams()[0][0]
        self.assertEqual(saved.team_id, original.team_id)
        self.assertEqual(saved.players[10].name, 'New player')
        self.assertEqual(saved.players[10].position, original.players[10].position)
        self.assertEqual(saved.players[0].name, original.players[10].name)
        self.assertEqual(saved.players[10].attributes.strength, original.players[0].attributes.strength - 1)
        self.assertEqual(saved.players[10].attributes.speed, original.players[0].attributes.speed + 1)
        self.assertEqual(saved, setup.selected[0])
        saved.validate()

    def test_editor_rejects_duplicate_and_blank_names(self):
        for name in ('  ' + TeamSetup(self.surface, self.library).selected[0].players[1].name.upper() + '  ', ''):
            setup = TeamSetup(self.surface, self.library)
            original = setup.selected[0]
            frames = self.rename_frames(name) if name else self.rename_frames(' ')
            self.edit_frames(setup, frames + [[click(520, 382)], [click(40, 382)]])
            self.assertEqual(setup.selected[0], original)
            self.assertFalse(self.library.list_teams()[0])

    def test_editor_displays_error_for_accented_player_and_team_names(self):
        for team_name in (False, True):
            with self.subTest(team_name=team_name):
                setup = TeamSetup(self.surface, self.library)
                original = setup.selected[0]
                frames = self.rename_frames('Café')
                if team_name:
                    frames[0] = [click(200, 50)]
                with patch.object(setup, 'text', wraps=setup.text) as rendered:
                    self.edit_frames(setup, frames + [[click(520, 382)], [click(40, 382)]])
                self.assertTrue(any('please remove accents' in str(call.args[0]) for call in rendered.call_args_list))
                self.assertEqual(setup.selected[0], original)

    def test_editor_cannot_add_above_budget_or_below_zero(self):
        from dataclasses import replace
        from qooty.player_attributes import PlayerStats
        setup = TeamSetup(self.surface, self.library)
        first = replace(setup.selected[0].players[0], attributes=PlayerStats(100, 0, 0, 0, 0, 0, 0))
        setup.selected[0] = replace(setup.selected[0], players=(first,) + setup.selected[0].players[1:])
        self.edit_frames(setup, [[click(570, 140)], [click(480, 163)], [click(520, 382)]])
        self.assertEqual(setup.selected[0].players[0], first)

    def test_editor_cancel_and_failed_save_preserve_original(self):
        setup = TeamSetup(self.surface, self.library)
        original = self.library.save(setup.selected[0])
        setup.selected[0] = original
        with patch.object(self.library, 'save', side_effect=PermissionError('read only')):
            self.edit_frames(setup, self.rename_frames('Changed') + [[click(520, 382)], [click(40, 382)]])
        self.assertEqual(setup.selected[0], original)
        self.assertEqual(self.library.list_teams()[0], [original])


if __name__ == '__main__':
    unittest.main()
