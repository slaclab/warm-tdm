## Config/state save + load. Root-scoped operations (SaveConfig/SaveState/
## LoadConfig) written to the session output dir. Relies on TopologyCore state
## (self.root, self._require_output). Mounted on Session.

import os
import time


class ConfigMixin:
    """Save/load hardware config + state YAMLs under the session output dir."""

    def save_config(self):
        """Save writable config to ``<sessiondir>/config_<ctime>.yml``."""
        ctime = int(time.time())
        filename = os.path.join(self._require_output(), f'config_{ctime}.yml')
        self.root.SaveConfig(filename)
        print(f'Saved config to {filename}')
        return filename

    def save_state(self):
        """Save full system state (incl. RO) to ``<sessiondir>/state_<ctime>.yml``."""
        ctime = int(time.time())
        filename = os.path.join(self._require_output(), f'state_{ctime}.yml')
        self.root.SaveState(filename)
        print(f'Saved state to {filename}')
        return filename

    def load_config(self, filename):
        """Load a hardware configuration YAML saved by save_config()."""
        if not os.path.exists(filename):
            raise FileNotFoundError(f"Configuration file '{filename}' not found.")
        self.root.LoadConfig(filename)
        print(f"Loaded configuration from {filename}")
