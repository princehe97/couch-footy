"""Exercise shutdown using real SDL events without opening a visible window."""
import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import importlib
import unittest
from unittest.mock import patch

import pygame


class WindowCloseTests(unittest.TestCase):
    def load_engine(self):
        # Importing the legacy engine installs scaling hooks; keep these tests isolated.
        update, flip, mouse = pygame.display.update, pygame.display.flip, pygame.mouse.get_pos
        self.engine = importlib.reload(importlib.import_module('qooty.engine'))
        pygame.display.update, pygame.display.flip, pygame.mouse.get_pos = update, flip, mouse

    def setUp(self):
        pygame.init()
        pygame.display.set_mode((960, 600))
        pygame.event.clear()
        self.load_engine()
        self.addCleanup(pygame.quit)

    def close_event(self):
        pygame.event.post(pygame.event.Event(pygame.QUIT))

    def assert_closed(self):
        self.assertFalse(self.engine.run)
        self.assertFalse(self.engine.state.sim_running)
        self.assertFalse(self.engine.playing_match)
        self.assertFalse(pygame.get_init())

    def test_main_menu_close_is_not_discarded(self):
        self.close_event()
        self.engine.main()
        self.assert_closed()

    def test_close_from_settings_instructions_and_post_match(self):
        for screen in ('settings', 'instructions', 'post_match'):
            with self.subTest(screen=screen):
                pygame.init()
                pygame.display.set_mode((960, 600))
                pygame.event.clear()
                self.load_engine()
                def navigate():
                    self.engine.on_main_menu = False
                    setattr(self.engine, screen, True)
                draw = {'settings': 'open_settings', 'instructions': 'open_instructions', 'post_match': 'ShowPostMatchScreen'}[screen]
                original = getattr(self.engine, draw)
                def close_during_screen():
                    self.close_event()
                    original()
                with patch.object(self.engine, 'main_menu', side_effect=navigate), patch.object(self.engine, draw, side_effect=close_during_screen):
                    self.engine.main()
                self.assert_closed()

    def test_match_close_unwinds_before_next_frame(self):
        engine = self.engine
        def navigate():
            engine.on_main_menu = False
            engine.playing_match = True
        with patch.object(engine, 'main_menu', side_effect=navigate), \
             patch.object(engine.Player, 'Initiate'), \
             patch.object(engine.Player, 'StartIntLog'), \
             patch.object(engine.BestOnGround, 'MakeLists'), \
             patch.object(engine.sim_game, 'Comm_MatchStart'), \
             patch.object(engine.sim_game, 'RandomWeather', side_effect=self.close_event), \
             patch.object(engine.sim_game, 'GamePlayTime') as advance:
            engine.main()
        advance.assert_not_called()
        self.assert_closed()

    def test_keyboard_events_remain_available(self):
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_TAB))
        events = self.engine._poll_events()
        self.assertTrue(any(event.type == pygame.KEYDOWN and event.key == pygame.K_TAB for event in events))
