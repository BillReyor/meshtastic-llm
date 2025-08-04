import threading
from typing import Dict, List


MAX_TEXT_LEN = 1024


def _safe_text(s: str, max_len: int = MAX_TEXT_LEN) -> str:
    return s.replace("\r", "\\r").replace("\n", "\\n")[:max_len]


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
        board = bbs_posts.setdefault(target, [])
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
            reply = f"Post #{len(board)} recorded."

    log_message("OUT", target, reply, channel=is_channel)
    send_chunked_text(reply, target, iface, channel=is_channel)
