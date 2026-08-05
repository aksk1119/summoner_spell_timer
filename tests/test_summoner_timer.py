import unittest

from summoner_timer import CountdownTimer, adjusted_cooldown, format_time


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


class CountdownTimerTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.timer = CountdownTimer(300, self.clock)

    def test_start_counts_down_from_deadline(self):
        self.timer.start()
        self.assertEqual(300, self.timer.remaining_seconds)

        self.clock.now += 61.2

        self.assertEqual(239, self.timer.remaining_seconds)
        self.assertTrue(self.timer.is_running)

    def test_expired_timer_stops_at_zero(self):
        self.timer.start()
        self.clock.now += 301

        self.assertEqual(0, self.timer.remaining_seconds)
        self.assertFalse(self.timer.is_running)

    def test_reset_clears_timer(self):
        self.timer.start()
        self.timer.reset()

        self.assertEqual(0, self.timer.remaining_seconds)
        self.assertFalse(self.timer.is_running)

    def test_format_time(self):
        self.assertEqual("05:00", format_time(300))
        self.assertEqual("01:01", format_time(61))
        self.assertEqual("00:00", format_time(-1))

    def test_cosmic_insight_applies_summoner_spell_haste(self):
        self.assertAlmostEqual(254.237, adjusted_cooldown(300, True), places=3)
        self.assertEqual(300, adjusted_cooldown(300, False))


if __name__ == "__main__":
    unittest.main()