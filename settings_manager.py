import os
import json
from default_config import get_default_config

CONFIG_FILE = "config.json"

class SettingsManager:
    def __init__(self):
        self.config = self.load_config()

    def load_config(self):
        if not os.path.exists(CONFIG_FILE):
            default_cfg = get_default_config()
            self.save_config(default_cfg)
            return default_cfg
        try:
            with open(CONFIG_FILE, 'r') as f:
                loaded_config = json.load(f)
                default_config = get_default_config()
                for key, value in default_config.items():
                    if key not in loaded_config:
                        loaded_config[key] = value
                return loaded_config
        except (json.JSONDecodeError, IOError):
            return get_default_config()

    def save_config(self, config_data):
        self.config = config_data.copy()
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config_data, f, indent=4)
        except IOError as e:
            print(f"Could not write to '{CONFIG_FILE}': {e}")

    def get(self, key):
        return self.config.get(key, get_default_config().get(key))