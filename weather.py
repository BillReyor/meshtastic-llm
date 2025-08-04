import requests
from urllib.parse import quote_plus

MAX_LOC_LEN = 256


def _safe_text(s: str, max_len: int = MAX_LOC_LEN) -> str:
    return s.replace("\r", "\\r").replace("\n", "\\n")[:max_len]


def get_weather(loc: str = "") -> str:
    try:
        loc = _safe_text(loc)
        url = f"https://wttr.in/{quote_plus(loc) if loc else ''}?format=3&u"
        r = requests.get(url, timeout=5, verify=True, allow_redirects=False)
        if r.status_code == 200:
            return r.text.strip()
    except Exception as e:
        return f"Error retrieving weather: {e}"
    return "Unable to retrieve weather."
