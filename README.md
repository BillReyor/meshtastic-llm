# Meshtastic LLM Bot

This repository contains a small Python script that bridges a local language model running in LM Studio with a Meshtastic radio. It listens for direct messages and replies with completions from the selected model.

## Requirements

- Python 3.9+
- A Meshtastic device connected via USB
- LM Studio running an API server (default: `http://localhost:1234/v1`)

Install Python dependencies with:

```bash
pip install -r requirements.txt
```

## Usage

1. Start LM Studio and load the desired model. The script defaults to `mradermacher/WizardLM-1.0-Uncensored-Llama2-13b-GGUF`, but you can change this in `meshtastic_llm_bot.py`.
2. Connect your Meshtastic radio.
3. Run the bot:

```bash
python meshtastic_llm_bot.py
```

The program will wait for direct messages on the radio and send back the LLM's response in numbered chunks for easy ordering.

### Commands

- `help` – display the list of commands.
- `weather [location]` – show the current weather using the wttr.in service. If no location is given, a default location is used.
- Any other text will be answered by the language model.

The command menu is shown only on your first message to the bot or whenever you send `help`.

### Customizing

- Update `openai.api_base` if your LM Studio server is running on a different host or port.
- Modify `MODEL_NAME`, `CHUNK_SIZE`, or `CHUNK_DELAY` to fit your setup or preferences.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
