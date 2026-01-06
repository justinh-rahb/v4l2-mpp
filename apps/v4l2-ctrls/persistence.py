#!/usr/bin/env python3
"""
Persistence for V4L2 control values.

Saves and restores control values to/from JSON files.
"""

import json
import os
from typing import Dict


class ControlPersistence:
    """Handles saving and loading control values."""

    def __init__(self, state_file: str):
        """Initialize persistence.

        Args:
            state_file: Path to JSON state file
        """
        self.state_file = state_file

    def save(self, values: Dict[str, int]) -> None:
        """Save control values to file.

        Args:
            values: Dict mapping control names to values
        """
        # Ensure directory exists
        state_dir = os.path.dirname(self.state_file)
        if state_dir and not os.path.exists(state_dir):
            os.makedirs(state_dir, exist_ok=True)

        # Write state file
        with open(self.state_file, 'w') as f:
            json.dump(values, f, indent=2)

    def load(self) -> Dict[str, int]:
        """Load control values from file.

        Returns:
            Dict mapping control names to values, or empty dict if file doesn't exist
        """
        if not os.path.exists(self.state_file):
            return {}

        try:
            with open(self.state_file, 'r') as f:
                data = json.load(f)

            # Validate data
            if not isinstance(data, dict):
                return {}

            # Ensure all values are integers
            result = {}
            for key, value in data.items():
                if isinstance(key, str) and isinstance(value, int):
                    result[key] = value

            return result

        except (json.JSONDecodeError, IOError):
            return {}

    def clear(self) -> None:
        """Remove the state file."""
        if os.path.exists(self.state_file):
            os.unlink(self.state_file)


def get_default_state_file(device: str) -> str:
    """Get default state file path for a device.

    Args:
        device: Device path (e.g., /dev/video11)

    Returns:
        Path to state file
    """
    # Use XDG_STATE_HOME if available, otherwise ~/.local/state
    state_home = os.environ.get('XDG_STATE_HOME')
    if not state_home:
        state_home = os.path.expanduser('~/.local/state')

    # Create filename from device path
    # /dev/video11 -> video11.json
    # /dev/v4l-subdev2 -> v4l-subdev2.json
    device_name = os.path.basename(device)
    filename = f"{device_name}.json"

    return os.path.join(state_home, 'v4l2-ctrls', filename)
