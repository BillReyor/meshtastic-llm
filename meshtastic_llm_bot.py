#!/usr/bin/env python3
import threading
from concurrent.futures import ThreadPoolExecutor
import time

from pubsub import pub
from meshtastic.serial_interface import SerialInterface
import requests
from urllib.parse import quote_plus

# —— CONFIG ——
API_BASE = "http://localhost:1234/v1"
API_KEY = "lm-studio"  # or your LM Studio API key
MODEL_NAME = "mradermacher/WizardLM-1.0-Uncensored-Llama2-13b-GGUF"
SYSTEM_PROMPT = (
    "You are an intelligent assistant. "
    "Provide concise, well-reasoned answers that are correct and helpful."
)

# Maximum characters per Meshtastic message (tweak if needed)
CHUNK_SIZE = 100
# Delay between chunks (seconds)
CHUNK_DELAY = 0.2
# Maximum chat history items per peer
MAX_HISTORY_LEN = 20
# Maximum number of worker threads
MAX_WORKERS = 4
# Channel to listen and occasionally post hacker messages on
EMERALD_CHANNEL_NAME = "Emerald"
# How often to post a hacker message to the Emerald channel (seconds)
HACKER_INTERVAL = 3600
# —— END CONFIG ——

MENU = (
    "Commands:\n"
    "- help: show this message\n"
    "- weather [location]: current weather\n"
    "- anything else: chat with the language model"
)

# Track which peers have already been shown the menu
menu_shown = set()
menu_lock = threading.Lock()

DEFAULT_LOCATION = "San Francisco"

# Maintain per-peer chat histories
histories = {}
history_lock = threading.Lock()

# Thread pool for handling incoming messages
executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
emerald_channel = None

def record_message(peer: int, role: str, content: str):
    """Append a message to a peer's history and return a copy."""
    with history_lock:
        history = histories.setdefault(peer, [{"role": "system", "content": SYSTEM_PROMPT}])
        history.append({"role": role, "content": content})
        # Trim history to the most recent messages
        if len(history) > MAX_HISTORY_LEN + 1:  # include system prompt
            histories[peer] = history[-(MAX_HISTORY_LEN + 1):]
            history = histories[peer]
        return history.copy()


def split_into_chunks(text: str, size: int):
    """Split text into chunks of at most `size` characters."""
    return [text[i:i+size] for i in range(0, len(text), size)]


def send_chunked_text(text: str, target: int, interface, channel: bool = False):
    """Send `text` to `target` (peer or channel) in numbered chunks."""
    reserved = 6  # Reserve space for the " 1/10" suffix when chunking
    chunks = split_into_chunks(text, CHUNK_SIZE - reserved)
    total = len(chunks)
    for i, chunk in enumerate(chunks, start=1):
        suffix = f" {i}/{total}"
        if channel:
            interface.sendText(chunk + suffix, channelIndex=target)
        else:
            interface.sendText(chunk + suffix, target)
        time.sleep(CHUNK_DELAY)


def get_weather(location: str = "") -> str:
    """Fetch current weather for `location` using wttr.in."""
    try:
        loc = quote_plus(location) if location else ""
        url = f"https://wttr.in/{loc}?format=3"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return resp.text.strip()
    except Exception as e:
        return f"Error retrieving weather: {e}"
    return "Unable to retrieve weather information."


def generate_hacker_message() -> str:
    """Use the LLM to craft a short hacker-style note about EmeraldCon."""
    try:
        prompt = (
            "Share a brief, playful hacker-style message about EmeraldCon "
            "at the Hackers on Planet Earth conference in NYC."
        )
        url = f"{API_BASE}/chat/completions"
        headers = {"Authorization": f"Bearer {API_KEY}"}
        payload = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 1.0,
            "max_tokens": 60,
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"Error generating hacker message: {e}"

def handle_message(target: int, text: str, interface, is_channel: bool = False):
    """Generate a reply to `text` and send it back to `target`."""
    try:
        lower = text.lower()

        if lower == "help":
            reply_text = MENU
            print(f"[OUT] To {target}: {reply_text}")
            send_chunked_text(reply_text, target, interface, channel=is_channel)
            with menu_lock:
                menu_shown.add(target)
            return

        with menu_lock:
            first_contact = target not in menu_shown
            if first_contact:
                menu_shown.add(target)

        if first_contact:
            print(f"[OUT] To {target}: {MENU}")
            send_chunked_text(MENU, target, interface, channel=is_channel)

        if lower.startswith("weather"):
            parts = text.split(maxsplit=1)
            location = parts[1] if len(parts) > 1 else DEFAULT_LOCATION
            weather = get_weather(location)
            reply_text = weather
            print(f"[OUT] To {target}: {reply_text}")
            send_chunked_text(reply_text, target, interface, channel=is_channel)
            return

        history = record_message(target, "user", text)

        url = f"{API_BASE}/chat/completions"
        headers = {"Authorization": f"Bearer {API_KEY}"}
        payload = {
            "model": MODEL_NAME,
            "messages": history,
            "temperature": 0.7,
            "max_tokens": 500,
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        reply_text = resp.json()["choices"][0]["message"]["content"].strip()

        record_message(target, "assistant", reply_text)

        print(f"[OUT] To {target}: {reply_text}")

        send_chunked_text(reply_text, target, interface, channel=is_channel)
    except Exception as e:
        print(f"Error handling message for {target}: {e}")

def on_receive(packet, interface):
    try:
        channel = packet.get("channel")
        if channel is None:
            channel = packet.get("channelIndex") or packet.get("channel_index")
        to = packet.get("to")
        text = packet.get("decoded", {}).get("text", "").strip()
        if not text:
            return

        is_dm = to == interface.myInfo.my_node_num
        is_emerald = emerald_channel is not None and channel == emerald_channel
        if not (is_dm or is_emerald):
            return

        source = packet.get("from")
        if source == interface.myInfo.my_node_num:
            return
        target = source if is_dm else channel
        print(f"[IN]  From {source}: {text}")

        executor.submit(handle_message, target, text, interface, not is_dm)

    except Exception as e:
        print(f"Error in on_receive: {e}")


# Subscribe to receive events
pub.subscribe(on_receive, "meshtastic.receive")


def find_channel_index(interface, name: str):
    try:
        for i, ch in enumerate(interface.radioConfig.channels):
            ch_name = getattr(ch.settings, "name", "")
            if ch_name and ch_name.lower() == name.lower():
                return i
    except Exception:
        pass
    return None


def hacker_sender(interface):
    while True:
        time.sleep(HACKER_INTERVAL)
        if emerald_channel is not None:
            message = generate_hacker_message()
            send_chunked_text(message, emerald_channel, interface, channel=True)


def main():
    global emerald_channel
    interface = SerialInterface()  # Connect to your first Meshtastic device
    emerald_channel = find_channel_index(interface, EMERALD_CHANNEL_NAME)

    threading.Thread(target=hacker_sender, args=(interface,), daemon=True).start()

    print("Meshtastic ↔️ LLM bot running. Listening for DMs and Emerald channel…")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping bot…")
        interface.close()
        executor.shutdown(wait=False)


if __name__ == "__main__":
    main()
