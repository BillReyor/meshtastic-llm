import io
import threading
from contextlib import redirect_stdout
from typing import Dict

from adventure import Game
from utils.text import MAX_TEXT_LEN, safe_text

games: Dict[int, Game] = {}
_games_lock = threading.Lock()


COMMANDS_HELP = (
    "Commands:\n"
    "- 'zork north|south|east|west|up|down' to move\n"
    "- 'zork look' to look around\n"
    "- 'zork examine <item>' to inspect items\n"
    "- 'zork take <item>' or 'zork drop <item>' to pick up or drop\n"
    "- 'zork inventory' to list carried items\n"
    "- 'zork use <item> [on <object>]' to use items\n"
    "- 'zork save' or 'zork restore' to save or load\n"
    "- 'zork score' or 'zork moves' to check score or moves\n"
    "- 'zork verbose' to toggle detailed descriptions\n"
    "- 'zork quit' to end the game"
)


def handle_zork(target: int, command: str, iface, is_channel: bool, user: int | None,
                log_message, send_chunked_text) -> None:
    command = command.strip()
    key = user if user is not None else target
    with _games_lock:
        game = games.get(key)
        if not command or command == "help":
            reply = (
                "Usage: zork start|quit|<command>. Prefix every action with 'zork'.\n"
                f"{COMMANDS_HELP}"
            )
        elif command == "start":
            game = Game()
            games[key] = game
            buf = io.StringIO()
            with redirect_stdout(buf):
                game.do_look()
            room = buf.getvalue().strip()
            reply = f"{room}\n{COMMANDS_HELP}"
        elif command in ("quit", "exit"):
            if key in games:
                del games[key]
                reply = "Game over."
            else:
                reply = "No active game."
        else:
            if not game:
                reply = "No active game. Type 'zork start' to begin and prefix every command with 'zork'."
            else:
                buf = io.StringIO()
                with redirect_stdout(buf):
                    for verb, noun, prep in game.parser.parse(command):
                        game.run_command(verb, noun, prep)
                reply = buf.getvalue().strip() or "..."

    safe_reply = safe_text(reply)[:MAX_TEXT_LEN]
    log_message("OUT", target, safe_reply, channel=is_channel)
    send_chunked_text(safe_reply, target, iface, channel=is_channel)
