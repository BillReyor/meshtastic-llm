import re

MAX_TEXT_LEN = 1024
MAX_LOC_LEN = 256

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")
_PLACEHOLDER_RE = re.compile(r"\s*\[[A-Z_]+\]\s*")


def _escape_control(match: re.Match) -> str:
    c = match.group(0)
    if c == "\n":
        return "\\n"
    if c == "\r":
        return "\\r"
    return f"\\x{ord(c):02x}"


def safe_text(s: str, max_len: int = MAX_TEXT_LEN) -> str:
    """Remove placeholders, escape control characters, and truncate."""
    s = _PLACEHOLDER_RE.sub(" ", s).strip()
    return _CONTROL_CHARS_RE.sub(_escape_control, s)[:max_len]
