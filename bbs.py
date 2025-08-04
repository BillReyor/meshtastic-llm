import json
import os
import tempfile
import threading
from typing import Dict, List


MAX_TEXT_LEN = 1024
BBS_DIR = os.path.abspath(os.getenv("MESHTASTIC_BBS_DIR", "bbs_data"))
os.makedirs(BBS_DIR, exist_ok=True, mode=0o700)
try:
    os.chmod(BBS_DIR, 0o700)
except OSError:
    pass


def _safe_text(s: str, max_len: int = MAX_TEXT_LEN) -> str:
    return s.replace("\r", "\\r").replace("\n", "\\n")[:max_len]


def _board_path(target: int) -> str:
    return os.path.join(BBS_DIR, f"{target}.json")


def _load_board(target: int) -> List[str]:
    path = _board_path(target)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return [str(x) for x in data]
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return []


def _save_board(target: int, board: List[str]) -> None:
    path = _board_path(target)
    fd, tmp_path = tempfile.mkstemp(dir=BBS_DIR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(board, f)
        os.replace(tmp_path, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    finally:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass


bbs_posts: Dict[int, List[str]] = {}

bbs_lock = threading.Lock()


def handle_bbs(
    target: int,
    command: str,
    iface,
    is_channel: bool,
    user: int | None,
    log_message,
    send_chunked_text,
) -> None:
    command = command.strip()
    with bbs_lock:
        board = bbs_posts.get(target)
        if board is None:
            board = _load_board(target)
            bbs_posts[target] = board
        if not command or command == "list":
            if not board:
                reply = "No posts."
            else:
                lines = [f"{i+1}. {p}" for i, p in enumerate(board)]
                reply = "Posts:\n" + "\n".join(lines)
        elif command.startswith("read"):
            parts = command.split(maxsplit=1)
            if len(parts) == 2 and parts[1].isdigit():
                idx = int(parts[1]) - 1
                if 0 <= idx < len(board):
                    reply = board[idx]
                else:
                    reply = "No such post."
            else:
                reply = "Usage: bbs read <n>"
        else:
            content = command[5:].strip() if command.startswith("post ") else command
            content = _safe_text(content)
            entry = f"{user}: {content}" if user is not None else content
            board.append(entry)
            _save_board(target, board)
            reply = f"Post #{len(board)} recorded."

    log_message("OUT", target, reply, channel=is_channel)
    send_chunked_text(reply, target, iface, channel=is_channel)
