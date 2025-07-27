#!/usr/bin/env python3
import threading
from concurrent.futures import ThreadPoolExecutor
import time

import openai
from pubsub import pub
from meshtastic.serial_interface import SerialInterface
import requests
from urllib.parse import quote_plus

# —— CONFIG ——
openai.api_base = "http://localhost:1234/v1"
openai.api_key = "lm-studio"  # or your LM Studio API key

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


def send_chunked_text(text: str, peer: int, interface):
    """Send `text` to `peer` in numbered chunks."""
    # Reserve space for the " 1/10" suffix when chunking
    reserved = 6
    chunks = split_into_chunks(text, CHUNK_SIZE - reserved)
    total = len(chunks)
    for i, chunk in enumerate(chunks, start=1):
        suffix = f" {i}/{total}"
        interface.sendText(chunk + suffix, peer)
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

def handle_message(peer: int, text: str, interface):
    """Generate a reply to `text` from `peer` and send it back."""
    try:
        lower = text.lower()

        if lower == "help":
            reply_text = MENU
            print(f"[OUT] To {peer}: {reply_text}")
            send_chunked_text(reply_text, peer, interface)
            with menu_lock:
                menu_shown.add(peer)
            return

        with menu_lock:
            first_contact = peer not in menu_shown
            if first_contact:
                menu_shown.add(peer)

        if first_contact:
            print(f"[OUT] To {peer}: {MENU}")
            send_chunked_text(MENU, peer, interface)

        if lower.startswith("weather"):
            parts = text.split(maxsplit=1)
            location = parts[1] if len(parts) > 1 else DEFAULT_LOCATION
            weather = get_weather(location)
            reply_text = weather
            print(f"[OUT] To {peer}: {reply_text}")
            send_chunked_text(reply_text, peer, interface)
            return

        history = record_message(peer, "user", text)

        resp = openai.ChatCompletion.create(
            model=MODEL_NAME,
            messages=history,
            temperature=0.7,
            max_tokens=500,
        )
        reply_text = resp.choices[0].message.content.strip()

        record_message(peer, "assistant", reply_text)

        print(f"[OUT] To {peer}: {reply_text}")

        send_chunked_text(reply_text, peer, interface)
    except Exception as e:
        print(f"Error handling message from {peer}: {e}")

def on_receive(packet, interface):
    try:
        if packet.get("to") == interface.myInfo.my_node_num:
            peer = packet["from"]
            text = packet.get("decoded", {}).get("text", "").strip()
            if not text:
                return

            print(f"[IN]  From {peer}: {text}")

            # Use a thread pool to limit concurrent work and mitigate DoS attacks
            executor.submit(handle_message, peer, text, interface)

    except Exception as e:
        print(f"Error in on_receive: {e}")

# Subscribe to receive events
pub.subscribe(on_receive, "meshtastic.receive")

def main():
    # Connect to your first Meshtastic device
    interface = SerialInterface()

    print("Meshtastic ↔️ LLM bot running. Waiting for DMs…")
    try:
        # Keep the script alive so pubsub callbacks fire
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping bot…")
        interface.close()
        executor.shutdown(wait=False)

if __name__ == "__main__":
    main()
