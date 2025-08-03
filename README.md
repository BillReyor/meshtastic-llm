# Meshtastic LLM Bot

This repository contains a small Python script that bridges a local language model running in LM Studio with a Meshtastic radio. It listens for direct messages and for messages on user-chosen channel(s) 0–3 (or all), replying with completions from the selected model and occasionally posting a hacker-themed note to those channels.

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

When started, the program prompts for which channel(s) (0–3 or *all*) it should respond on. It always answers direct messages. The bot sends back the LLM's response in numbered chunks for easy ordering and occasionally broadcasts a random hacker message for users to reply to on the selected channels.

### Commands

- `help` – display the list of commands.
- `weather [location]` – show the current weather using the wttr.in service. If no location is given, a default location is used.
- Any other text will be answered by the language model.

The command menu is shown only on your first message to the bot or whenever you send `help`.
When it is displayed automatically, the menu is sent as its own message before the bot replies to your request.

### Customizing

 - Update `API_BASE` if your LM Studio server is running on a different host or port.
 - Modify `MODEL_NAME`, `CHUNK_SIZE`, or `CHUNK_DELAY` to fit your setup or preferences.
 - `MAX_HISTORY_LEN` controls how many messages per peer are kept in memory.
 - `MAX_WORKERS` limits how many threads can handle messages concurrently.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
