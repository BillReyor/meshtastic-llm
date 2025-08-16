import datetime
import logging
from types import SimpleNamespace

import meshtastic_llm_bot as bot


class DummyIface:
    myInfo = SimpleNamespace(my_node_num=1)


def test_log_message_redacts_sensitive(tmp_path, monkeypatch):
    monkeypatch.setattr(bot, "LOG_DIR", str(tmp_path))
    text = "psk=abcd password=secret hello"
    bot.log_message("IN", 1, text)
    logfile = tmp_path / f"{datetime.date.today().isoformat()}.log"
    data = logfile.read_text()
    assert "secret" not in data
    assert "abcd" not in data
    assert "hello" not in data
    assert "[REDACTED]" in data


def test_on_receive_debug_redacts_sensitive(monkeypatch, caplog):
    monkeypatch.setattr(bot, "log_message", lambda *a, **k: None)
    monkeypatch.setattr(bot, "respond_channels", {0})
    monkeypatch.setattr(bot, "is_addressed", lambda *a, **k: True)
    monkeypatch.setattr(bot, "mark_addressed", lambda *a, **k: None)

    class DummyFuture:
        def add_done_callback(self, fn):
            pass

    monkeypatch.setattr(bot.executor, "submit", lambda *a, **k: DummyFuture())

    packet = {"decoded": {"text": "password=foo psk=bar secret"}, "channel": 0, "to": 1, "from": 2}
    caplog.set_level(logging.DEBUG)
    bot.on_receive(packet=packet, interface=DummyIface())
    logs = "\n".join(caplog.messages)
    assert "foo" not in logs
    assert "bar" not in logs
    assert "secret" not in logs
    assert "[REDACTED]" in logs
