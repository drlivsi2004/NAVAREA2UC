import unittest

import main


class ConsoleProgressTests(unittest.TestCase):
    def test_interactive_progress_has_viewing_delay(self):
        self.assertEqual(main.ConsoleProgress.MIN_VISIBLE_SECONDS, 12.0)

    def test_animation_interval_remains_short(self):
        self.assertLess(main.ConsoleProgress.ANIMATION_INTERVAL_SECONDS, 0.5)

    def test_finishing_phase_has_multiple_stages(self):
        self.assertGreaterEqual(len(main.ConsoleProgress.FINISHING_STAGES), 3)
        self.assertGreater(main.ConsoleProgress.FINISHING_STAGE_SECONDS, 0)


if __name__ == "__main__":
    unittest.main()