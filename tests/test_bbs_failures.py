import os, sys, tempfile, shutil, atexit, json
from unittest.mock import patch
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
BBS_DIR = tempfile.mkdtemp(prefix="bbs-test-")
os.environ["MESHTASTIC_BBS_DIR"] = BBS_DIR
atexit.register(lambda: shutil.rmtree(BBS_DIR, ignore_errors=True))

import bbs


class SaveBoardFailureTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        sys.modules.pop("bbs", None)

    def setUp(self):
        for f in os.listdir(BBS_DIR):
            try:
                os.remove(os.path.join(BBS_DIR, f))
            except FileNotFoundError:
                pass

    def test_json_dump_failure_removes_temp_and_logs(self):
        with patch("bbs.json.dump", side_effect=OSError("fail")):
            with self.assertLogs("bbs", level="ERROR") as cm:
                bbs._save_board(1, ["post"])
            self.assertTrue(any("Failed to write board" in m for m in cm.output))
        self.assertEqual(os.listdir(BBS_DIR), [])

    def test_replace_failure_removes_temp_and_logs(self):
        with patch("bbs.os.replace", side_effect=OSError("fail")):
            with self.assertLogs("bbs", level="ERROR") as cm:
                bbs._save_board(1, ["post"])
            self.assertTrue(any("Failed to replace" in m for m in cm.output))
        self.assertEqual(os.listdir(BBS_DIR), [])

    def test_chmod_failure_logs(self):
        with patch("bbs.os.chmod", side_effect=OSError("fail")):
            with self.assertLogs("bbs", level="ERROR") as cm:
                bbs._save_board(1, ["post"])
            self.assertTrue(any("Failed to chmod" in m for m in cm.output))
        board_path = os.path.join(BBS_DIR, "1.json")
        self.assertTrue(os.path.exists(board_path))
        with open(board_path, "r", encoding="utf-8") as f:
            self.assertEqual(json.load(f), ["post"])


if __name__ == "__main__":
    unittest.main()
