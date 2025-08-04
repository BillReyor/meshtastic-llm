import io
import threading
from contextlib import redirect_stdout
from typing import Dict

from adventure import Game

MAX_TEXT_LEN = 1024


def _safe_text(s: str, max_len: int = MAX_TEXT_LEN) -> str:
    return s.replace("\r", "\\r").replace("\n", "\\n")[:max_len]


games: Dict[int, Game] = {}
_games_lock = threading.Lock()


def handle_zork(target: int, command: str, iface, is_channel: bool, user: int | None,
                log_message, send_chunked_text) -> None:
    command = command.strip()
    key = user if user is not None else target
    with _games_lock:
        game = games.get(key)
        if not command or command == "help":
            reply = "Usage: zork start|quit|<command>"
        elif command == "start":
            game = Game()
            games[key] = game
            buf = io.StringIO()
            with redirect_stdout(buf):
                game.do_look()
            reply = buf.getvalue().strip()
        elif command in ("quit", "exit"):
            if key in games:
                del games[key]
                reply = "Game over."
            else:
                reply = "No active game."
        else:
            if not game:
                reply = "No active game. Type 'zork start' to begin."
            else:
                buf = io.StringIO()
                with redirect_stdout(buf):
                    for verb, noun, prep in game.parser.parse(command):
                        game.run_command(verb, noun, prep)
                reply = buf.getvalue().strip() or "..."

    reply = _safe_text(reply)
    log_message("OUT", target, reply, channel=is_channel)
    send_chunked_text(reply, target, iface, channel=is_channel)
