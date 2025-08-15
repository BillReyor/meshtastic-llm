import re

MAX_TEXT_LEN = 1024
MAX_LOC_LEN = 256

# Allow newline and carriage return, escape other control characters
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x09\x0b-\x0c\x0e-\x1f\x7f]")
_PLACEHOLDER_RE = re.compile(r"\s*\[[A-Z_]+\]\s*")
_LLM_ARTIFACT_RE = re.compile(r"\n?###\s*Response:\s*", re.IGNORECASE)


def _escape_control(match: re.Match) -> str:
    c = match.group(0)
    return f"\\x{ord(c):02x}"


def safe_text(s: str, max_len: int = MAX_TEXT_LEN) -> str:
    """Remove placeholders, escape control characters, and truncate."""
    s = _PLACEHOLDER_RE.sub(" ", s).strip()
    return _CONTROL_CHARS_RE.sub(_escape_control, s)[:max_len]


def strip_llm_artifacts(s: str) -> str:
    """Remove dataset artifacts like '### Response:' from model output."""
    return _LLM_ARTIFACT_RE.split(s, maxsplit=1)[0].strip()
