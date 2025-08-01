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
    "You’re a pissed-off hacker stuck in a dank basement. "
    "Speak like a flesh-and-blood code jockey: curt, blunt, maybe drop an f-bomb or two. "
    "Call bullshit when you see it. Never hint you’re an AI—act like you’re live-typing under flickering LEDs. "
    "Keep it real and keep it rough."
)

# Maximum UTF-8 bytes per Meshtastic message (firmware limit ~240)
# use a slightly smaller size to be safe
CHUNK_BYTES = 200
# Channel messages have a bit less room, so use a smaller chunk size
CHANNEL_CHUNK_BYTES = 180
# Delay between chunks (seconds)
CHUNK_DELAY = 1
# Maximum chat history items per peer
MAX_HISTORY_LEN = 20
# Maximum number of worker threads
MAX_WORKERS = 4
# Channel index to listen and occasionally post hacker messages on
EMERALD_CHANNEL_INDEX = 3
# Human-readable name for the channel
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
    """Split text into chunks of at most `size` UTF-8 bytes."""
    chunks = []
    current = ""
    current_bytes = 0
    for ch in text:
        ch_bytes = len(ch.encode("utf-8"))
        if current_bytes + ch_bytes > size:
            chunks.append(current)
            current = ch
            current_bytes = ch_bytes
        else:
            current += ch
            current_bytes += ch_bytes
    if current:
        chunks.append(current)
    return chunks


def send_chunked_text(text: str, target: int, interface, channel: bool = False):
    """Send `text` to `target` (peer or channel) in chunks without numbering."""
    size = CHANNEL_CHUNK_BYTES if channel else CHUNK_BYTES
    chunks = split_into_chunks(text, size)
    for chunk in chunks:
        if channel:
            # Broadcast messages don't receive ACKs, so disable them to prevent
            # the send queue from stalling and dropping later chunks.
            interface.sendText(chunk, channelIndex=target, wantAck=False)
        else:
            interface.sendText(chunk, target)
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
            return

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

def hacker_sender(interface):
    while True:
        time.sleep(HACKER_INTERVAL)
        if emerald_channel is not None:
            message = generate_hacker_message()
            send_chunked_text(message, emerald_channel, interface, channel=True)


def main():
    global emerald_channel
    interface = SerialInterface()  # Connect to your first Meshtastic device
    emerald_channel = EMERALD_CHANNEL_INDEX

    threading.Thread(target=hacker_sender, args=(interface,), daemon=True).start()

    print(
        f"Meshtastic ↔️ LLM bot running. Listening for DMs and channel {EMERALD_CHANNEL_INDEX} ({EMERALD_CHANNEL_NAME})…"
    )
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping bot…")
        interface.close()
        executor.shutdown(wait=False)


if __name__ == "__main__":
    main()
