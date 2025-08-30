import os
import sys
import types
import unittest
import importlib
import datetime
from unittest.mock import patch


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


def load_bot(soul: str):
    os.environ["MESHTASTIC_SOUL"] = soul
    if "meshtastic_llm_bot" in sys.modules:
        importlib.reload(sys.modules["meshtastic_llm_bot"])
    else:
        import meshtastic_llm_bot  # noqa: F401
    bot = sys.modules["meshtastic_llm_bot"]
    bot.respond_channels = {0}
    return bot


class StandardSchedulingTests(unittest.TestCase):
    def setUp(self):
        self.bot = load_bot("sentinel")

    def test_greeting_loop_interval(self):
        captured = {}

        def fake_sleep(sec):
            captured["sleep"] = sec

        def fake_send(msg, ch, iface, channel=False):
            captured["msg"] = msg
            raise RuntimeError

        with patch("meshtastic_llm_bot.random.uniform", return_value=0), \
            patch("meshtastic_llm_bot.random.choice", return_value="hi"), \
            patch("meshtastic_llm_bot.time.sleep", side_effect=fake_sleep), \
            patch("meshtastic_llm_bot.send_chunked_text", side_effect=fake_send):
            with self.assertRaises(RuntimeError):
                self.bot.greeting_loop(object())

        self.assertEqual(captured["sleep"], self.bot.GREET_INTERVAL)
        self.assertEqual(captured["msg"], "hi")

    def test_reminder_loop_interval(self):
        captured = {}

        def fake_sleep(sec):
            captured["sleep"] = sec

        def fake_send(msg, ch, iface, channel=False):
            captured["msg"] = msg
            raise RuntimeError

        with patch("meshtastic_llm_bot.random.uniform", return_value=0), \
            patch("meshtastic_llm_bot.time.sleep", side_effect=fake_sleep), \
            patch("meshtastic_llm_bot.send_chunked_text", side_effect=fake_send), \
            patch("meshtastic_llm_bot.safe_text", lambda x, y: x):
            with self.assertRaises(RuntimeError):
                self.bot.reminder_loop(object())

        self.assertEqual(captured["sleep"], self.bot.REMINDER_INTERVAL)
        self.assertEqual(captured["msg"], self.bot.EVENT_REMINDER)


class ConnecticutSchedulingTests(unittest.TestCase):
    def setUp(self):
        self.bot = load_bot("connecticut-service-bot")

    def test_beacon_at_configured_hour(self):
        captured = {}
        fake_now = datetime.datetime(2024, 1, 1, 4, 0, 0)

        class FakeDateTime(datetime.datetime):
            @classmethod
            def now(cls, tz=None):
                return fake_now

        def fake_send(msg, ch, iface, channel=False):
            captured["msg"] = msg
            raise RuntimeError

        with patch("meshtastic_llm_bot.datetime.datetime", FakeDateTime), \
            patch("meshtastic_llm_bot.time.sleep") as mock_sleep, \
            patch("meshtastic_llm_bot.send_chunked_text", side_effect=fake_send):
            with self.assertRaises(RuntimeError):
                self.bot.greeting_loop(object())

        mock_sleep.assert_called_once()
        self.assertEqual(mock_sleep.call_args[0][0], 3600)
        self.assertEqual(captured["msg"], self.bot.BEACON_MESSAGE)

    def test_reminder_loop_disabled(self):
        with patch("meshtastic_llm_bot.send_chunked_text") as mock_send, \
            patch("meshtastic_llm_bot.time.sleep") as mock_sleep:
            self.bot.reminder_loop(object())
            mock_send.assert_not_called()
            mock_sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()

