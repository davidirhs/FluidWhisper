import json
import os

CONFIG_FILE = 'config.json'
DEFAULT_CONFIG = {
  "model_name": "deepdml/faster-whisper-large-v3-turbo-ct2",
  "shortcut": "alt+shift+r",
  "cancel_shortcut": "esc",
  "notify_clipboard_saving": True,
  "log_level": "WARNING",
  "language": "en",
  "device": "cuda"
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    with open(CONFIG_FILE, 'r') as f:
        config = json.load(f)
    for key, value in DEFAULT_CONFIG.items():
        if key not in config:
            config[key] = value
    return config

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
