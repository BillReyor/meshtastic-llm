MAX_TEXT_LEN = 1024
MAX_LOC_LEN = 256

def safe_text(s: str, max_len: int = MAX_TEXT_LEN) -> str:
    """Escape newlines and carriage returns and truncate to max_len."""
    return s.replace("\r", "\\r").replace("\n", "\\n")[:max_len]
