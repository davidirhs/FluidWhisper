from PySide6.QtCore import QSettings

# Define default configuration values.
DEFAULT_CONFIG = {
    "shortcut": "alt+shift+r",
    "cancel_shortcut": "esc",
    "notify_clipboard_saving": True,
    "log_level": "WARNING",
    "language": "en",
    "device": "cuda"
}

def load_config():
    settings = QSettings("davidirhs", "FluidWhisper")
    config = {}
    # Retrieve each value with a fallback to the default.
    for key, default in DEFAULT_CONFIG.items():
        config[key] = settings.value(key, default)
    return config

def save_config(config):
    settings = QSettings("davidirhs", "FluidWhisper")
    for key in DEFAULT_CONFIG:
        settings.setValue(key, config.get(key, DEFAULT_CONFIG[key]))
