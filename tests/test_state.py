import os, sys, types
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault("MESHTASTIC_API_KEY", "test")

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

class StateTests(unittest.TestCase):
    def setUp(self):
        bot.histories.clear()
        bot.last_addressed.clear()
        bot.bbs_posts.clear()
        zork.games.clear()

    def test_split_into_chunks(self):
        text = "a" * 500
        chunks = list(bot.split_into_chunks(text, 100))
        self.assertTrue(all(len(c.encode("utf-8")) <= 100 for c in chunks))
        self.assertEqual("".join(chunks), text)

    def test_record_message_prunes(self):
        peer = 1
        for i in range(bot.MAX_HISTORY_LEN + 5):
            bot.record_message(peer, "user", f"m{i}")
        self.assertLessEqual(len(bot.histories[peer]), bot.MAX_HISTORY_LEN + 1)

    def test_is_addressed_regex(self):
        peer = 1
        channel = 0
        self.assertFalse(bot.is_addressed("hello", False, channel, peer))
        self.assertTrue(bot.is_addressed("hey smudge", False, channel, peer))

    def test_is_addressed_weather(self):
        peer = 1
        channel = 0
        self.assertTrue(bot.is_addressed("weather Paris", False, channel, peer))

    def test_is_addressed_bbs(self):
        peer = 1
        channel = 0
        self.assertTrue(bot.is_addressed("bbs list", False, channel, peer))

    def test_is_addressed_zork(self):
        peer = 1
        channel = 0
        self.assertTrue(bot.is_addressed("zork start", False, channel, peer))

    def test_weather_command_with_handle(self):
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
            bot.handle_message(1, "smudge weather Paris", object(), True)
        finally:
            bot.get_weather = orig_get_weather
            bot.send_chunked_text = orig_send_chunked
            bot.log_message = orig_log_message

        self.assertEqual(outputs.get("loc"), "Paris")
        self.assertEqual(outputs.get("reply"), "Weather for Paris")

    def test_get_weather_uses_fahrenheit(self):
        called = {}

        class DummyResp:
            status_code = 200
            text = "Weather"

        def fake_get(url, timeout=0, verify=True, allow_redirects=False):
            called["url"] = url
            return DummyResp()

        orig_get = bot.requests.get
        bot.requests.get = fake_get
        try:
            bot.get_weather("Vegas")
        finally:
            bot.requests.get = orig_get

        self.assertIn("format=3&u", called.get("url", ""))

    def test_bbs_post_and_list(self):
        outputs = []

        def fake_send_chunked(text, target, iface, channel=False):
            outputs.append(text)

        orig_send = bot.send_chunked_text
        orig_log = bot.log_message
        bot.send_chunked_text = fake_send_chunked
        bot.log_message = lambda *a, **k: None
        try:
            bot.handle_message(0, "bbs post hello", object(), True, user=42)
            bot.handle_message(0, "bbs list", object(), True, user=42)
        finally:
            bot.send_chunked_text = orig_send
            bot.log_message = orig_log
            bot.bbs_posts.clear()

        self.assertEqual(outputs[0], "Post #1 recorded.")
        self.assertIn("1. 42: hello", outputs[1])
        self.assertEqual(bot.histories, {})

    def test_zork_start_and_move(self):
        outputs = []

        def fake_send(text, target, iface, channel=False):
            outputs.append(text)

        orig_send = bot.send_chunked_text
        orig_log = bot.log_message
        bot.send_chunked_text = fake_send
        bot.log_message = lambda *a, **k: None
        try:
            bot.handle_message(0, "zork start", object(), True, user=42)
            bot.handle_message(0, "zork east", object(), True, user=42)
        finally:
            bot.send_chunked_text = orig_send
            bot.log_message = orig_log
            zork.games.clear()

        self.assertIn("Room 1", outputs[0])
        self.assertIn("Room 2", outputs[1])

if __name__ == "__main__":
    unittest.main()
