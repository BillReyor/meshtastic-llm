# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Python bot that bridges a local LLM (via LM Studio) with a Meshtastic mesh radio device. Users send messages over the radio network and receive AI responses back. Secondary features include a bulletin board system (BBS), weather lookups, and a text adventure game.

## Commands

**Install dependencies:**
```bash
pip install -r requirements.txt
```

**Run the bot:**
```bash
python meshtastic_llm_bot.py
```

**Run all tests:**
```bash
python -m unittest discover -s tests
```

**Run a single test file:**
```bash
python -m unittest tests.test_safe_text
```

## Architecture

### Core Message Flow

```
Meshtastic radio → on_receive() [pubsub] → is_addressed()? → executor.submit(handle_message)
  → route: help / weather / bbs / zork / reset / LLM API
  → split_into_chunks() → send_chunked_text() → Meshtastic radio
```

### Key Files

- **`meshtastic_llm_bot.py`** — Main application. Handles radio I/O (via `pypubsub`), per-peer conversation history, message routing, LLM API calls, and text chunking. `BoundedExecutor` (max 4 workers, queue 20) handles concurrency.
- **`bbs.py`** — File-backed bulletin board. JSON files in `bbs_data/{target}.json`, protected by `bbs_lock`, written atomically.
- **`weather.py`** — Calls wttr.in for weather (no API key needed).
- **`zork.py`** — Text adventure wrapper. Per-user game instances in `games` dict, protected by `_games_lock`.
- **`adventure/game.py`** + **`adventure/world.json`** — Self-contained text adventure engine with 30 rooms.
- **`utils/text.py`** — `safe_text()` (escapes control chars), `strip_llm_artifacts()`.
- **`utils/__init__.py`** — `redact_sensitive()` for log privacy (always returns `[REDACTED]`).
- **`souls/*.json`** — Bot personality profiles (name, handle, system_prompt, hello_messages, optional beacon).

### State Management

- **Conversation history**: In-memory `histories[peer_id]` dict, pruned at >20 messages or >4000 chars, protected by `history_lock`.
- **BBS posts**: `bbs_data/{target}.json` files (JSON arrays of strings), permissions 0o600.
- **Game state**: In-memory `games[user_id]`; players can `zork save` to a local `save.json`.
- **Logging**: `logs/{date}.log` (message IN/OUT) and `logs/{date}-debug.log`; user message content always redacted.

### LLM API

OpenAI-compatible endpoint. Configured via environment variables:
- `MESHTASTIC_API_BASE` (default: `http://localhost:1234/v1`)
- `MESHTASTIC_API_KEY` (default: `lm-studio`)
- `MESHTASTIC_MODEL_NAME`
- Temperature: 0.7, max_tokens: 300, timeout: 60s

### Text Chunking

Direct messages split at 200 bytes, channel messages at 180 bytes. Long responses get `[1/3]`, `[2/3]`, etc. prefixes. Chunking is UTF-8 aware (avoids splitting multi-byte characters).

### Soul Profiles

Selected via `MESHTASTIC_SOUL` env var or interactively at startup. Each JSON profile sets the bot's handle (the trigger word), system prompt, and optional greeting/beacon behavior.

### Testing Approach

Tests use `unittest` with environment variable mocking and stub modules for `meshtastic` and `pubsub` (to avoid hardware dependencies). Tests set `MESHTASTIC_API_KEY`, `MESHTASTIC_SOUL`, and `MESHTASTIC_BBS_DIR` via `os.environ` before importing the bot module.

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `MESHTASTIC_API_BASE` | `http://localhost:1234/v1` | LM Studio API base URL |
| `MESHTASTIC_API_KEY` | `lm-studio` | LLM API key |
| `MESHTASTIC_MODEL_NAME` | WizardLM-1.0-Uncensored... | Model to use |
| `MESHTASTIC_SOUL` | (interactive) | Soul profile name |
| `MESHTASTIC_BBS_DIR` | `bbs_data` | BBS storage directory |
| `MESHTASTIC_DEBUG` | — | Enable debug logging |
| `BOT_CHANNELS` | (interactive) | Preselect channels (0-4 or "all") |
| `CHUNK_BYTES` | 200 | DM chunk size in bytes |
| `CHANNEL_CHUNK_BYTES` | 180 | Channel chunk size in bytes |
| `MAX_HISTORY_LEN` | 20 | Max messages in conversation history |
| `MAX_CONTEXT_CHARS` | 4000 | Max chars in conversation history |
| `MESHTASTIC_ALLOW_NO_API_KEY` | — | Skip API key requirement (testing only) |
