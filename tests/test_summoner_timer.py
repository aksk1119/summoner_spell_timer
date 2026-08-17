import tkinter as tk
import unittest

from summoner_timer import (
    CountdownTimer,
    GameClock,
    OverlayWindow,
    SummonerTimerApp,
    adjusted_cooldown,
    format_time,
)


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


class GameClockTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.game_clock = GameClock(self.clock)

    def test_not_running_before_start(self):
        self.assertFalse(self.game_clock.is_running)
        self.assertEqual(0, self.game_clock.elapsed_seconds)

    def test_elapsed_increases_after_start(self):
        self.game_clock.start()
        self.assertTrue(self.game_clock.is_running)
        self.clock.now += 75.9
        self.assertEqual(75, self.game_clock.elapsed_seconds)

    def test_start_is_idempotent(self):
        self.game_clock.start()
        self.clock.now += 10
        self.game_clock.start()  # second call must not reset the origin
        self.assertEqual(10, self.game_clock.elapsed_seconds)

    def test_reset_stops_clock(self):
        self.game_clock.start()
        self.clock.now += 30
        self.game_clock.reset()
        self.assertFalse(self.game_clock.is_running)
        self.assertEqual(0, self.game_clock.elapsed_seconds)


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


class OverlayShortcutTests(unittest.TestCase):
    def test_overlay_shortcuts_are_bound_to_overlay_when_main_window_is_hidden(self):
        root = tk.Tk()
        try:
            app = SummonerTimerApp(root)
            app.root.withdraw()
            overlay = OverlayWindow(app)
            self.assertNotEqual("", overlay.bind("<Control-Key-g>"))
            self.assertNotEqual("", overlay.bind("<Alt-Key-g>"))
            overlay.destroy()
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()