# Utility modules for meshtastic LLM project

from __future__ import annotations

import re


_REDACT_PATTERNS = [
    re.compile(r"(?i)password=[^\s&]+"),
    re.compile(r"(?i)psk=[^\s&]+"),
    re.compile(r"(?i)message=[^\s&]+"),
]


def redact_sensitive(text: str) -> str:
    """Mask potentially sensitive text before logging.

    Replaces common credential patterns such as ``password=`` and ``psk`` with a
    ``[REDACTED]`` marker and suppresses any message content entirely.

    Parameters
    ----------
    text: str
        The text to sanitize.

    Returns
    -------
    str
        A redacted version of *text* safe for logging.
    """

    if not text:
        return text

    redacted = text
    for pat in _REDACT_PATTERNS:
        redacted = pat.sub(lambda m: m.group(0).split("=")[0] + "=[REDACTED]", redacted)

    # Never log actual message content
    return "[REDACTED]"

