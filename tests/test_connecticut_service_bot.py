import os, sys, types, tempfile, shutil, atexit
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault("MESHTASTIC_API_KEY", "test")
os.environ["MESHTASTIC_SOUL"] = "connecticut-service-bot"
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

import unittest
import meshtastic_llm_bot as bot
import zork


class ConnecticutSoulTests(unittest.TestCase):
    def setUp(self):
        bot.histories.clear()
        bot.last_addressed.clear()
        bot.bbs_posts.clear()
        zork.games.clear()

    def test_is_addressed_with_ctbot_prefix(self):
        peer = 1
        channel = 0
        self.assertTrue(bot.is_addressed("ctbot status", False, channel, peer))

    def test_handle_message_weather_with_ctbot_prefix(self):
        outputs = {}

        def fake_get_weather(loc):
            outputs["loc"] = loc
            return f"Weather for {loc}"

        def fake_send_chunked(text, target, iface, channel=False):
            outputs["reply"] = text

        orig_get_weather = bot.get_weather
        orig_send_chunked = bot.send_chunked_text
        orig_log_message = bot.log_message
        bot.get_weather = fake_get_weather
        bot.send_chunked_text = fake_send_chunked
        bot.log_message = lambda *a, **k: None
        try:
            bot.handle_message(1, "ctbot weather Hartford", object(), True)
        finally:
            bot.get_weather = orig_get_weather
            bot.send_chunked_text = orig_send_chunked
            bot.log_message = orig_log_message

        self.assertEqual(outputs.get("loc"), "Hartford")
        self.assertEqual(outputs.get("reply"), "Weather for Hartford")

    def test_boot_message_reflects_connecticut_soul(self):
        self.assertIn("Connecticut mesh", bot.BOOT_MESSAGE)
        self.assertIn("ctbot help", bot.BOOT_MESSAGE)


if __name__ == "__main__":
    unittest.main()
