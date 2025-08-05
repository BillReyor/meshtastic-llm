import requests
from urllib.parse import quote_plus

from utils.text import MAX_LOC_LEN, safe_text


def get_weather(loc: str = "") -> str:
    try:
        loc = safe_text(loc, MAX_LOC_LEN)
        url = f"https://wttr.in/{quote_plus(loc) if loc else ''}?format=3&u"
        r = requests.get(url, timeout=5, verify=True, allow_redirects=False)
        r.raise_for_status()
        if r.status_code == 200:
            return r.text.strip()
    except requests.RequestException as e:
        status = getattr(getattr(e, "response", None), "status_code", None)
        reason = getattr(getattr(e, "response", None), "reason", None)
        if status is not None:
            msg = f"HTTP {status}"
            if reason:
                msg += f" {reason}"
        else:
            msg = str(e)
        return f"Error retrieving weather: {msg}"
    except Exception as e:
        return f"Error retrieving weather: {e}"
    return "Unable to retrieve weather."
