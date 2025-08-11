import io
import unittest
from contextlib import redirect_stdout

from adventure.game import Game


class UseActionTests(unittest.TestCase):
    def capture(self, func, *args):
        buf = io.StringIO()
        with redirect_stdout(buf):
            func(*args)
        return buf.getvalue()

    def test_use_lamp(self):
        g = Game()
        out = self.capture(g.do_use, "lamp", "")
        self.assertIn("lamp is now lit", out)
        self.assertTrue(g.required_items["lamp"])

    def test_use_key_unlocks_door(self):
        g = Game()
        out = self.capture(g.do_use, "key", "door")
        self.assertFalse(g.locked_doors[10]["east"])
        self.assertIn("door unlocks", out)

    def test_use_lockpick_unlocks_door(self):
        g = Game()
        out = self.capture(g.do_use, "lockpick", "door")
        self.assertFalse(g.locked_doors[10]["east"])
        self.assertIn("door unlocks", out)

    def test_use_scroll_increases_score(self):
        g = Game()
        out = self.capture(g.do_use, "scroll", "")
        self.assertEqual(g.score, 5)
        self.assertIn("score +5", out.lower())

    def test_use_hope_badge(self):
        g = Game()
        out = self.capture(g.do_use, "hope_badge", "")
        self.assertEqual(g.score, 16)
        self.assertIn("score +16", out.lower())

    def test_use_hope_schedule(self):
        g = Game()
        out = self.capture(g.do_use, "hope_schedule", "")
        self.assertEqual(g.score, 5)
        self.assertIn("score +5", out.lower())

    def test_use_unknown_item(self):
        g = Game()
        out = self.capture(g.do_use, "unknown", "")
        self.assertIn("nothing happens", out.lower())


if __name__ == "__main__":
    unittest.main()
