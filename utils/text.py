import re

MAX_TEXT_LEN = 1024
MAX_LOC_LEN = 256

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")


def _escape_control(match: re.Match) -> str:
    c = match.group(0)
    if c == "\n":
        return "\\n"
    if c == "\r":
        return "\\r"
    return f"\\x{ord(c):02x}"


def safe_text(s: str, max_len: int = MAX_TEXT_LEN) -> str:
    """Escape control characters and truncate to max_len."""
    return _CONTROL_CHARS_RE.sub(_escape_control, s)[:max_len]
