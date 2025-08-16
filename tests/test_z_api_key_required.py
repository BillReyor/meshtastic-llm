import sys
import types
import importlib
import tempfile
import shutil

import pytest


def import_bot():
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

    if "meshtastic_llm_bot" in sys.modules:
        del sys.modules["meshtastic_llm_bot"]
    sys.modules.pop("bbs", None)
    return importlib.import_module("meshtastic_llm_bot")


def test_api_key_required(monkeypatch):
    tmp_dir = tempfile.mkdtemp(prefix="bbs-test-")
    monkeypatch.setenv("MESHTASTIC_BBS_DIR", tmp_dir)
    monkeypatch.delenv("MESHTASTIC_API_KEY", raising=False)
    monkeypatch.delenv("MESHTASTIC_ALLOW_NO_API_KEY", raising=False)
    monkeypatch.setenv("MESHTASTIC_SOUL", "cipher")

    bot = import_bot()
    with pytest.raises(SystemExit):
        bot.check_api_key()

    monkeypatch.setenv("MESHTASTIC_ALLOW_NO_API_KEY", "1")
    bot = import_bot()
    bot.check_api_key()
    del sys.modules["meshtastic_llm_bot"]
    sys.modules.pop("bbs", None)
    shutil.rmtree(tmp_dir, ignore_errors=True)

