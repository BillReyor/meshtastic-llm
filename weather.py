import requests
from urllib.parse import quote_plus

from utils.text import MAX_LOC_LEN, safe_text


def get_weather(loc: str = "") -> str:
    try:
        loc = safe_text(loc, MAX_LOC_LEN)
        url = f"https://wttr.in/{quote_plus(loc) if loc else ''}?format=3&u"
        r = requests.get(url, timeout=5, verify=True, allow_redirects=False)
        if r.status_code == 200:
            return r.text.strip()
    except Exception as e:
        return f"Error retrieving weather: {e}"
    return "Unable to retrieve weather."
