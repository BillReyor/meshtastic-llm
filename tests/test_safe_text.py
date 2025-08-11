import os, sys, types, tempfile, shutil, atexit

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault("MESHTASTIC_API_KEY", "test")
os.environ.setdefault("MESHTASTIC_SOUL", "cipher")

BBS_DIR = tempfile.mkdtemp(prefix="bbs-test-")
os.environ["MESHTASTIC_BBS_DIR"] = BBS_DIR
atexit.register(lambda: shutil.rmtree(BBS_DIR, ignore_errors=True))


import unittest

from utils.text import safe_text


class SafeTextTests(unittest.TestCase):
    def test_escapes_control_chars(self):
        raw = "hello\nworld\r\x00\x1b!"
        expected = "hello\\nworld\\r\\x00\\x1b!"
        self.assertEqual(safe_text(raw), expected)


if __name__ == "__main__":
    unittest.main()

