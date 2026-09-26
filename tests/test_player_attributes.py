import unittest

from qooty.player_attributes import PlayerStats


class FatigueTests(unittest.TestCase):
    def test_fatigue_never_increases_an_attribute(self):
        for value in (0, 1, 15, 100):
            stats = PlayerStats(value, value, value, value, 0, value, 0)
            for overtime in (0, 10, 20, 30):
                with self.subTest(value=value, overtime=overtime):
                    fatigued = stats.with_fatigue_penalty(overtime)
                    for field in ('strength', 'speed', 'agility', 'skill', 'pressure'):
                        self.assertGreaterEqual(getattr(fatigued, field), 0)
                        self.assertLessEqual(getattr(fatigued, field), value)
                    self.assertEqual(fatigued.endurance, stats.endurance)
                    self.assertEqual(fatigued.aura, stats.aura)

    def test_maximum_fatigue_halves_normal_attributes(self):
        stats = PlayerStats(20, 20, 20, 20, 0, 20, 0)
        self.assertEqual(stats.with_fatigue_penalty(30), PlayerStats(10, 10, 10, 10, 0, 10, 0))
