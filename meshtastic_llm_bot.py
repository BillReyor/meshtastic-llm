#!/usr/bin/env python3
import datetime
import getpass
import hmac
import logging
import os
import random
import re
import signal
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, cast

import json
from pathlib import Path

import requests
from pubsub import pub
from meshtastic.serial_interface import SerialInterface

from weather import get_weather
from bbs import handle_bbs, bbs_posts
from zork import handle_zork
from utils.text import MAX_TEXT_LEN, MAX_LOC_LEN, safe_text

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

SOULS_DIR = Path("souls")


def load_soul() -> dict:
    souls = sorted(SOULS_DIR.glob("*.json"))
    if not souls:
        raise FileNotFoundError(f"No soul files found in {SOULS_DIR}")

    soul_name = os.getenv("MESHTASTIC_SOUL")
    if soul_name:
        path = SOULS_DIR / f"{soul_name}.json"
    elif sys.stdin.isatty():
        print("Available souls:")
        for i, path in enumerate(souls, 1):
            print(f"{i}: {path.stem}")
        while True:
            choice = input("Select a soul: ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(souls):
                path = souls[int(choice) - 1]
                break
            print("Invalid selection.")
    else:
        path = souls[0]

    if not path.exists():
        raise FileNotFoundError(f"Soul file {path} not found")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if sys.stdin.isatty():
        print(f"Loaded soul: {data.get('name', path.stem)}")
    return data

API_BASE = os.getenv("MESHTASTIC_API_BASE", "http://localhost:1234/v1")

API_KEY = os.getenv("MESHTASTIC_API_KEY")

MODEL_NAME = os.getenv(
    "MESHTASTIC_MODEL_NAME", "mradermacher/WizardLM-1.0-Uncensored-Llama2-13b-GGUF"
)

CHUNK_BYTES = 200
CHANNEL_CHUNK_BYTES = 180
DELAY_MIN = 3
DELAY_MAX = 5
RETRY_DELAY = 1
MAX_HISTORY_LEN = 20
MAX_CONTEXT_CHARS = 4000
MAX_WORKERS = 4
MAX_QUEUE_SIZE = 20
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True, mode=0o700)

MAX_PACKET_CHARS = 1024

CONVO_TIMEOUT = 120
FORBIDDEN_PROMPTS = ("assistant:", "system:", "```")

MENU = (
    "Commands:\n"
    "- help: show this message\n"
    "- weather [location]: current weather\n"
    "- bbs post <msg>: add a post\n"
    "- bbs list: show posts\n"
    "- bbs read <n>: read post n\n"
    "- zork start: begin adventure game\n"
    "- zork <cmd>: play the game\n"
    "- anything else: chat with the language model"
)
DEFAULT_LOCATION = "San Francisco"

soul = load_soul()
SOUL_NAME = soul["name"]
HANDLE = soul.get("handle", SOUL_NAME.lower())
SYSTEM_PROMPT = soul["system_prompt"]
HELLO_MESSAGES = soul.get("hello_messages", [f"{SOUL_NAME} here."])
BOOT_MESSAGE = soul.get(
    "boot_message",
    f"DM me or say '{HANDLE}' if you expect a reply. I remember the thread for about two minutes.\n",
) + MENU
HANDLE_RE = re.compile(rf"\b{re.escape(HANDLE)}\b", re.IGNORECASE)

GREET_INTERVAL = 4 * 3600
GREET_JITTER = 900

NO_BOOT = "--no-boot" in sys.argv


histories: dict[int, list[dict]] = {}
history_lock = threading.Lock()

last_addressed: dict[int, tuple[int, float]] = {}
address_lock = threading.Lock()

class BoundedExecutor:
    def __init__(self, max_workers: int, max_queue_size: int):
        self._semaphore = threading.BoundedSemaphore(max_workers + max_queue_size)
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    def submit(self, fn, *args, **kwargs):
        if not self._semaphore.acquire(blocking=False):
            logger.warning("executor queue full; dropping task")
            return None
        future = self._executor.submit(fn, *args, **kwargs)
        future.add_done_callback(lambda f: self._semaphore.release())
        return future

    def shutdown(self, wait: bool = True):
        self._executor.shutdown(wait=wait)


executor = BoundedExecutor(MAX_WORKERS, MAX_QUEUE_SIZE)
respond_channels: set[int] = set()

def log_message(direction: str, target: int, message: str, channel: bool = False):
    message = safe_text(message, MAX_TEXT_LEN)
    date_str = datetime.date.today().isoformat()
    logfile = os.path.join(LOG_DIR, f"{date_str}.log")
    with open(logfile, "a", encoding="utf-8") as f:
        try:
            os.chmod(logfile, 0o600)
        except OSError:
            pass
        ts = datetime.datetime.now().isoformat()
        kind = "channel" if channel else "peer"
        f.write(f"{ts}\t{direction}\t{kind}:{target}\t{message}\n")


def record_message(peer: int, role: str, content: str):
    with history_lock:
        hist = histories.setdefault(peer, [])
        if not hist or hist[0]["role"] != "system":
            hist.insert(0, {"role": "system", "content": SYSTEM_PROMPT})
        hist.append({"role": role, "content": safe_text(content, MAX_TEXT_LEN)})
        if len(hist) > MAX_HISTORY_LEN + 1:
            hist = hist[-(MAX_HISTORY_LEN + 1):]
        total_chars = sum(len(m["content"]) for m in hist[1:])
        while total_chars > MAX_CONTEXT_CHARS and len(hist) > 1:
            removed = hist.pop(1)
            total_chars -= len(removed["content"])
        histories[peer] = hist
        return hist.copy()


def is_safe_prompt(text: str) -> bool:
    lower = text.lower()
    return not any(f in lower for f in FORBIDDEN_PROMPTS)


def split_into_chunks(text: str, size: int):
    while text:
        if len(text.encode("utf-8")) <= size:
            yield text
            break
        end = size
        while len(text[:end].encode("utf-8")) > size:
            end -= 1
        split_point = max(text.rfind(sep, 0, end) for sep in ("\n", " "))
        if split_point <= 0:
            split_point = end
        chunk = text[:split_point].rstrip()
        yield chunk
        text = text[split_point:].lstrip()


def send_chunked_text(
    text: str,
    target: int,
    iface: SerialInterface,
    channel: bool = False,
) -> None:
    """Send a text message in multiple packets if necessary.

    Parameters
    ----------
    text:
        The message to transmit. It will be split into chunks that fit within the
        Meshtastic payload limits.
    target:
        The node ID or channel index to which the message should be delivered.
    iface:
        The :class:`~meshtastic.serial_interface.SerialInterface` used for
        communication.
    channel:
        ``True`` if ``target`` represents a channel index rather than a peer node.

    Side Effects
    ------------
    Introduces delays between chunk transmissions, sends packets over the radio
    and logs warnings when acknowledgements fail.

    Thread Safety
    -------------
    This function performs no internal synchronisation; callers must ensure that
    the provided ``iface`` is used in a thread-safe manner when invoked from
    multiple threads.
    """

    size = CHANNEL_CHUNK_BYTES if channel else CHUNK_BYTES
    prefix_len = len("[1/1] ")
    while True:
        total = sum(1 for _ in split_into_chunks(text, size - prefix_len))
        new_prefix_len = len(f"[{total}/{total}] ")
        if new_prefix_len == prefix_len:
            break
        prefix_len = new_prefix_len
    for i, chunk in enumerate(split_into_chunks(text, size - prefix_len), 1):
        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
        chunk = f"[{i}/{total}] {chunk}"
        if channel:
            iface.sendText(chunk, channelIndex=target, wantAck=False)
        else:
            for attempt in range(3):
                iface.sendText(chunk, target, wantAck=True)
                try:
                    iface.waitForAckNak()
                    break
                except Exception:
                    if attempt == 2:
                        logger.warning("no ACK after 3 tries")
                    time.sleep(RETRY_DELAY)


def reset_script(iface: SerialInterface) -> None:
    iface.close()
    executor.shutdown(wait=False)
    args = [a for a in sys.argv if a != "--no-boot"]
    args.append("--no-boot")
    os.execv(sys.executable, [sys.executable] + args)


def mark_addressed(channel_id: int, user: int):
    with address_lock:
        last_addressed[channel_id] = (user, time.time())


def is_addressed(text: str, direct: bool, channel_id: int, user: int) -> bool:
    if direct:
        return True
    lower = text.lower()
    now = time.time()
    if lower.startswith("bbs"):
        mark_addressed(channel_id, user)
        return True
    if lower.startswith("weather"):
        mark_addressed(channel_id, user)
        return True
    if lower.startswith("zork"):
        return True
    if HANDLE_RE.search(text):
        mark_addressed(channel_id, user)
        return True
    with address_lock:
        prev_user, ts = last_addressed.get(channel_id, (None, 0))
    if user == prev_user and now - ts < CONVO_TIMEOUT:
        return True
    return False


def handle_message(
    target: int,
    text: str,
    iface: SerialInterface,
    is_channel: bool = False,
    user: Optional[int] = None,
) -> None:
    """Handle an incoming user message and send an appropriate reply.

    Parameters
    ----------
    target:
        Destination node ID or channel index for the response.
    text:
        Raw message content from the user.
    iface:
        The :class:`~meshtastic.serial_interface.SerialInterface` used to send
        replies or perform a reset.
    is_channel:
        ``True`` when the message was received on a channel rather than via
        direct message.
    user:
        Identifier of the originating user, used for conversation state.

    Side Effects
    ------------
    Persists conversation history, performs network requests to the language
    model API, logs all interactions and may reboot the script when requested.

    Thread Safety
    -------------
    Intended to be executed within worker threads. Global state is protected by
    locks where necessary, but the supplied ``iface`` must be thread-safe if
    used concurrently.
    """

    text = safe_text(text, MAX_TEXT_LEN)
    text = re.sub(r"^\s*cipher[:,]?\s*", "", text, flags=re.IGNORECASE)
    lower = text.lower()

    if lower.startswith("bbs"):
        parts = text.split(maxsplit=1)
        cmd = parts[1] if len(parts) > 1 else ""
        handle_bbs(target, cmd, iface, is_channel, user, log_message, send_chunked_text)
        return

    if lower.startswith("zork"):
        parts = text.split(maxsplit=1)
        cmd = parts[1] if len(parts) > 1 else ""
        handle_zork(target, cmd, iface, is_channel, user, log_message, send_chunked_text)
        return

    if not is_safe_prompt(text):
        reply = "fuck off."
        log_message("OUT", target, reply, channel=is_channel)
        send_chunked_text(reply, target, iface, channel=is_channel)
        return

    if lower == "help":
        reply = MENU
        log_message("OUT", target, reply, channel=is_channel)
        send_chunked_text(reply, target, iface, channel=is_channel)
        return

    if lower.startswith("weather"):
        parts = text.split(maxsplit=1)
        loc = parts[1] if len(parts) > 1 else DEFAULT_LOCATION
        loc = safe_text(loc, MAX_LOC_LEN)
        reply = get_weather(loc)
        log_message("OUT", target, reply, channel=is_channel)
        send_chunked_text(reply, target, iface, channel=is_channel)
        return

    if lower == "reset":
        reply = "Rebooting..."
        log_message("OUT", target, reply, channel=is_channel)
        send_chunked_text(reply, target, iface, channel=is_channel)
        reset_script(iface)
        return

    if any(k in lower for k in ("code", "script", "write a", "hello world")):
        reply = "Not my gig."
        log_message("OUT", target, reply, channel=is_channel)
        send_chunked_text(reply, target, iface, channel=is_channel)
        return

    history = record_message(target, "user", text)
    payload = {
        "model": MODEL_NAME,
        "messages": history,
        "temperature": 0.7,
        "max_tokens": 300,
    }
    try:
        r = requests.post(
            f"{API_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json=payload,
            timeout=60,
            verify=True,
            allow_redirects=False,
        )
        r.raise_for_status()
        reply = r.json()["choices"][0]["message"]["content"].strip()
    except requests.HTTPError as e:
        status = e.response.status_code if e.response else "unknown"
        detail = e.response.text.strip() if e.response else str(e)
        reply = f"HTTP error {status}: {detail}"
    except Exception as e:
        reply = f"Error: {e}"
    finally:
        del payload

    reply = safe_text(reply, MAX_TEXT_LEN)
    record_message(target, "assistant", reply)
    log_message("OUT", target, reply, channel=is_channel)
    send_chunked_text(reply, target, iface, channel=is_channel)


def on_receive(
    packet: Optional[dict] = None,
    interface: Optional[SerialInterface] = None,
    **kwargs,
) -> None:
    try:
        pkt = packet or {}
        iface = cast(SerialInterface, interface)
        chan_info = pkt.get("channel")
        if isinstance(chan_info, dict):
            channel = chan_info.get("index")
        else:
            channel = chan_info
        if channel is None:
            channel = pkt.get("channelIndex")
        if channel is None:
            channel = pkt.get("channel_index")
        if channel is None:
            channel = 0

        try:
            channel = int(channel)
        except (TypeError, ValueError):
            channel = 0
        to = pkt.get("to")
        text = pkt.get("decoded", {}).get("text", "").strip()
        if len(text) > MAX_PACKET_CHARS:
            logger.warning("drop oversized packet from %s", pkt.get("from"))
            return
        try:
            text.encode("utf-8")
        except UnicodeEncodeError:
            logger.warning("drop malformed packet from %s", pkt.get("from"))
            return
        text = safe_text(text, MAX_TEXT_LEN)
        logger.debug(
            "chan_raw=%s parsed=%s to=%s from=%s text='%s'",
            chan_info,
            channel,
            to,
            pkt.get("from"),
            text,
        )
        if not text:
            logger.debug("no text; ignoring packet")
            return

        is_dm = to == iface.myInfo.my_node_num
        is_allowed = channel in respond_channels
        if not (is_dm or is_allowed):
            logger.debug(
                "ignoring because is_dm=%s and channel %s not in %s",
                is_dm,
                channel,
                respond_channels,
            )
            return

        src = cast(int, pkt.get("from"))
        if src == iface.myInfo.my_node_num:
            logger.debug("ignoring own message")
            return

        if not is_addressed(text, is_dm, channel, src):
            logger.debug("message not addressed to bot; ignoring")
            return

        if not is_dm:
            mark_addressed(channel, src)

        target = src if is_dm else channel
        log_message("IN", target, text, channel=not is_dm)
        if executor.submit(handle_message, target, text, iface, not is_dm, src) is None:
            logger.warning("Dropping message for target %s due to full queue", target)
    except Exception as e:
        logger.warning("Error in on_receive: %s", e)


def greeting_loop(iface: SerialInterface) -> None:
    while True:
        delay = GREET_INTERVAL + random.uniform(-GREET_JITTER, GREET_JITTER)
        time.sleep(max(0, delay))
        msg = random.choice(HELLO_MESSAGES)
        for ch in respond_channels:
            log_message("OUT", ch, msg, channel=True)
            send_chunked_text(msg, ch, iface, channel=True)


def main():
    global respond_channels

    token_env = os.getenv("CIPHER_CLI_TOKEN")
    if token_env:
        user_token = getpass.getpass("CLI auth token: ")
        if not hmac.compare_digest(user_token, token_env):
            print("Invalid auth token.")
            return

    selection_env = os.getenv("CIPHER_CHANNELS")
    if selection_env is None:
        selection = input("Respond on channel 0, 1, 2, 3, 4, or 'all'? ").strip().lower()
        os.environ["CIPHER_CHANNELS"] = selection
    else:
        selection = selection_env.strip().lower()
    if selection == "all":
        respond_channels = set(range(5))
    else:
        try:
            idx = int(selection)
            respond_channels = {idx} if 0 <= idx <= 4 else set()
        except ValueError:
            respond_channels = set()

    iface = SerialInterface()

    def shutdown(signum, frame):
        iface.close()
        executor.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)

    pub.subscribe(on_receive, "meshtastic.receive.text")
    if respond_channels:
        chs = ", ".join(str(c) for c in sorted(respond_channels))
        print(f"Meshtastic ↔️ Cipher ready. DMs or channel(s) {chs}")
    else:
        print("Meshtastic ↔️ Cipher ready. DMs only")
    if not NO_BOOT:
        print(BOOT_MESSAGE)
        hello = random.choice(HELLO_MESSAGES)
        for ch in respond_channels:
            log_message("OUT", ch, hello, channel=True)
            send_chunked_text(hello, ch, iface, channel=True)
            log_message("OUT", ch, BOOT_MESSAGE, channel=True)
            send_chunked_text(BOOT_MESSAGE, ch, iface, channel=True)
    threading.Thread(target=greeting_loop, args=(iface,), daemon=True).start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        iface.close()
        executor.shutdown(wait=False)
        print("Stopped.")


if __name__ == "__main__":
    main()
