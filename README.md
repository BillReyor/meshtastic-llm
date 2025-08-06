# Meshtastic LLM Bot

This repository contains a small Python script that bridges a local language model running in LM Studio with a Meshtastic radio. It listens for direct messages and for messages on user-chosen channel(s) 0–4 (or all), replying with completions from the selected model and occasionally posting a hacker-themed note to those channels. 

## Requirements

- Python 3.9+
- A Meshtastic device connected via USB
- LM Studio running an API server (default: `http://localhost:1234/v1`)

Install Python dependencies with:

```bash
pip install -r requirements.txt
```

The `requirements.txt` file pins exact versions of the core dependencies
(`meshtastic==2.2.15`, `pypubsub==4.0.3`, and `requests==2.31.0`) to ensure
they work together.

## Usage

1. Start LM Studio and load the desired model. The script defaults to `mradermacher/WizardLM-1.0-Uncensored-Llama2-13b-GGUF`, but you can change this in `meshtastic_llm_bot.py`.
2. Connect your Meshtastic radio.
3. Run the bot:

```bash
python meshtastic_llm_bot.py
```

When started, the program prompts for which channel(s) (0–4 or *all*) it should respond on. It always answers direct messages. The bot sends back the LLM's response in numbered chunks, prefixed like `[1/3]`, for easy ordering and occasionally broadcasts a random hacker message for users to reply to on the selected channels.

### Commands

- `help` – display the list of commands.
- `weather [location]` – show the current weather using the wttr.in service. If no location is given, a default location is used.
- `bbs post <msg>` – add a post to the simple bulletin board.
- `bbs list` – show posts on the board.
- `bbs read <n>` – read post *n*.
- `zork start` – begin the text adventure.
- `zork <cmd>` – play the game.
- Any other text will be answered by the language model.

BBS posts are stored on disk in a directory named `bbs_data` (or the path given by the `MESHTASTIC_BBS_DIR` environment variable) so they persist across restarts. Files are created with restrictive permissions for security.

The command menu is shown only on your first message to the bot or whenever you send `help`.
When it is displayed automatically, the menu is sent as its own message before the bot replies to your request.

## Text Adventure Module

A small Zork-like text adventure engine is available in the `adventure` package. Run it with:

```bash
python -m adventure.game
```

The game loads a 30-room world from JSON data, supports standard adventure commands, scoring, and save/restore.

### Customizing

 - Set the environment variables `MESHTASTIC_API_BASE`, `MESHTASTIC_API_KEY`, and
   `MESHTASTIC_MODEL_NAME` to override the LM Studio API base URL, API key, and
   model name. They default to `http://localhost:1234/v1`, `lm-studio`, and
   `mradermacher/WizardLM-1.0-Uncensored-Llama2-13b-GGUF` respectively.
 - Modify `CHUNK_BYTES`, `CHANNEL_CHUNK_BYTES`, or the `DELAY_MIN`/`DELAY_MAX`
   values to fit your setup or preferences.
 - `MAX_HISTORY_LEN` controls how many messages per peer are kept in memory.
 - `MAX_WORKERS` limits how many threads can handle messages concurrently.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
