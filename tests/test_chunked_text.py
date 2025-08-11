import os, sys, types, tempfile, shutil, atexit
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault("MESHTASTIC_API_KEY", "test")
os.environ.setdefault("MESHTASTIC_SOUL", "cipher")

BBS_DIR = tempfile.mkdtemp(prefix="bbs-test-")
os.environ["MESHTASTIC_BBS_DIR"] = BBS_DIR
atexit.register(lambda: shutil.rmtree(BBS_DIR, ignore_errors=True))

meshtastic_stub = types.ModuleType("meshtastic")
serial_stub = types.ModuleType("serial_interface")


class DummySerial:
    pass


serial_stub.SerialInterface = DummySerial
meshtastic_stub.serial_interface = serial_stub
sys.modules["meshtastic"] = meshtastic_stub
sys.modules["meshtastic.serial_interface"] = serial_stub

pubsub_stub = types.ModuleType("pubsub")
pubsub_stub.pub = types.SimpleNamespace(subscribe=lambda *a, **k: None)
sys.modules["pubsub"] = pubsub_stub

import importlib
import unittest


class FakeIface:
    def __init__(self):
        self.sent: list[str] = []

    def sendText(self, text, *args, **kwargs):
        self.sent.append(text)

    def waitForAckNak(self):
        return


class ChunkedTextTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        for m in ["meshtastic_llm_bot", "bbs"]:
            sys.modules.pop(m, None)

    def test_peer_chunks_within_limit(self):
        bot = importlib.import_module("meshtastic_llm_bot")
        bot = importlib.reload(bot)
        text = "a" * (bot.CHUNK_BYTES * 12)
        iface = FakeIface()
        with patch("meshtastic_llm_bot.time.sleep", return_value=None):
            bot.send_chunked_text(text, 1, iface, channel=False)
        total = len(iface.sent)
        self.assertTrue(total > 9)
        self.assertTrue(all(len(s.encode("utf-8")) <= bot.CHUNK_BYTES for s in iface.sent))
        self.assertTrue(iface.sent[0].startswith(f"[1/{total}] "))

    def test_channel_chunks_within_limit(self):
        bot = importlib.import_module("meshtastic_llm_bot")
        bot = importlib.reload(bot)
        text = "a" * (bot.CHANNEL_CHUNK_BYTES * 12)
        iface = FakeIface()
        with patch("meshtastic_llm_bot.time.sleep", return_value=None):
            bot.send_chunked_text(text, 1, iface, channel=True)
        total = len(iface.sent)
        self.assertTrue(total > 9)
        self.assertTrue(all(len(s.encode("utf-8")) <= bot.CHANNEL_CHUNK_BYTES for s in iface.sent))
        self.assertTrue(iface.sent[0].startswith(f"[1/{total}] "))


if __name__ == "__main__":
    unittest.main()

