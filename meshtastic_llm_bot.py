#!/usr/bin/env python3
import threading
import time

import openai
from pubsub import pub
from meshtastic.serial_interface import SerialInterface

# —— CONFIG ——
openai.api_base = "http://localhost:1234/v1"
openai.api_key = "lm-studio"  # or your LM Studio API key

MODEL_NAME = "mradermacher/WizardLM-1.0-Uncensored-Llama2-13b-GGUF"
SYSTEM_PROMPT = (
    "You are an intelligent assistant. "
    "Always provide well-reasoned answers that are both correct and helpful."
)

# Maximum characters per Meshtastic message (tweak if needed)
CHUNK_SIZE = 100
# Delay between chunks (seconds)
CHUNK_DELAY = 0.2
# —— END CONFIG ——

# Maintain per-peer chat histories
histories = {}
history_lock = threading.Lock()

def get_history(peer: int):
    with history_lock:
        if peer not in histories:
            histories[peer] = [{"role": "system", "content": SYSTEM_PROMPT}]
        return histories[peer]

def split_into_chunks(text: str, size: int):
    """Split text into chunks of at most `size` characters."""
    return [text[i:i+size] for i in range(0, len(text), size)]

def on_receive(packet, interface):
    try:
        # Only handle direct-to-us text messages
        if packet.get("to") == interface.myInfo.my_node_num:
            peer = packet["from"]
            text = packet.get("decoded", {}).get("text", "").strip()
            if not text:
                return

            print(f"[IN]  From {peer}: {text}")

            # Build up the conversation history
            history = get_history(peer)
            history.append({"role": "user", "content": text})

            # Generate a response via your local LM Studio API
            resp = openai.ChatCompletion.create(
                model=MODEL_NAME,
                messages=history,
                temperature=0.7,
                max_tokens=500
            )
            reply_text = resp.choices[0].message.content.strip()
            print(f"[OUT] To {peer}: {reply_text}")

            # Append assistant's reply to history
            history.append({"role": "assistant", "content": reply_text})

            # Send it back over Meshtastic in chunks
            for chunk in split_into_chunks(reply_text, CHUNK_SIZE):
                interface.sendText(chunk, peer)
                time.sleep(CHUNK_DELAY)

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

if __name__ == "__main__":
    main()
