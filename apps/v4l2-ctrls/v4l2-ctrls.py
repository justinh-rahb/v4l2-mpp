#!/usr/bin/env python3
"""
V4L2 Controls JSON-RPC Service.

A backend-only service that exposes camera controls via JSON-RPC over Unix socket.
Focuses on a single device and handles persistence of settings.

Usage:
  v4l2-ctrls.py --device /dev/video11 --socket /tmp/v4l2-ctrls.sock

JSON-RPC Methods:
  - list: Get all available controls with metadata
  - get: Read current control values
  - set: Change control values
  - info: Get device information

Requires:
  - v4l2-ctl in PATH
"""

import argparse
import sys
import time
from typing import Dict

from jsonrpc_server import JSONRPCServer
from persistence import ControlPersistence, get_default_state_file
from v4l2_core import (
    detect_devices,
    get_control_values,
    get_device_info,
    list_controls,
    set_controls,
)


def log(msg: str) -> None:
    """Log a message with timestamp."""
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


class V4L2ControlService:
    """V4L2 control service with JSON-RPC interface."""

    def __init__(self, device: str, persistence: ControlPersistence):
        """Initialize service.

        Args:
            device: V4L2 device path
            persistence: Persistence handler
        """
        self.device = device
        self.persistence = persistence

    def handle_list(self, params: Dict) -> Dict:
        """List all controls.

        Returns:
            {
                "controls": [
                    {
                        "name": "brightness",
                        "type": "int",
                        "min": 0,
                        "max": 255,
                        "step": 1,
                        "value": 128,
                        "menu": []
                    },
                    ...
                ]
            }
        """
        return list_controls(self.device)

    def handle_get(self, params: Dict) -> Dict:
        """Get control values.

        Args:
            params: {
                "controls": ["brightness", "contrast", ...]  # optional
            }

        Returns:
            {
                "values": {
                    "brightness": 128,
                    "contrast": 100,
                    ...
                }
            }
        """
        control_names = params.get("controls")
        return get_control_values(self.device, control_names)

    def handle_set(self, params: Dict) -> Dict:
        """Set control values.

        Args:
            params: {
                "controls": {
                    "brightness": 150,
                    "contrast": 110,
                    ...
                }
            }

        Returns:
            {
                "ok": true,
                "applied": {
                    "brightness": 150,
                    "contrast": 110
                }
            }
        """
        controls = params.get("controls", {})

        if not isinstance(controls, dict):
            return {"error": "controls must be a dict"}

        # Apply changes
        result = set_controls(self.device, controls)

        # If successful, persist the new values
        if result.get("ok"):
            # Get all current values and save
            current = get_control_values(self.device)
            if "values" in current:
                try:
                    self.persistence.save(current["values"])
                    log(f"Persisted {len(current['values'])} control values")
                except Exception as e:
                    log(f"Warning: Failed to persist values: {e}")

        return result

    def handle_info(self, params: Dict) -> Dict:
        """Get device information.

        Returns:
            {
                "info": "Device info text..."
            }
        """
        return get_device_info(self.device)

    def restore_settings(self) -> None:
        """Restore saved control values from persistence."""
        saved = self.persistence.load()

        if not saved:
            log("No saved settings to restore")
            return

        log(f"Restoring {len(saved)} saved control values...")

        result = set_controls(self.device, saved)

        if result.get("ok"):
            applied = result.get("applied", {})
            log(f"Successfully restored {len(applied)} controls")
        else:
            error = result.get("error", "Unknown error")
            log(f"Failed to restore settings: {error}")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="V4L2 Controls JSON-RPC Service",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
JSON-RPC Methods:
  list    - Get all available controls
  get     - Read control values
  set     - Change control values
  info    - Get device information

Examples:
  # Start service for a specific device
  v4l2-ctrls.py --device /dev/video11 --socket /tmp/v4l2-ctrls.sock

  # Auto-detect device
  v4l2-ctrls.py --socket /tmp/v4l2-ctrls.sock

  # Specify custom state file location
  v4l2-ctrls.py --device /dev/video11 --socket /tmp/v4l2.sock --state /tmp/v4l2-state.json
        """
    )
    parser.add_argument(
        "--device",
        help="V4L2 device path (if not specified, auto-detects)",
    )
    parser.add_argument(
        "--socket",
        required=True,
        help="Unix socket path for JSON-RPC communication",
    )
    parser.add_argument(
        "--state",
        help="State file path for persistence (default: ~/.local/state/v4l2-ctrls/<device>.json)",
    )
    parser.add_argument(
        "--no-restore",
        action="store_true",
        help="Don't restore saved settings on startup",
    )

    args = parser.parse_args()

    # Determine device
    if args.device:
        device = args.device
        log(f"Using specified device: {device}")
    else:
        devices = detect_devices()
        if not devices:
            log("ERROR: No V4L2 devices found")
            sys.exit(1)
        device = devices[0]
        log(f"Auto-detected device: {device}")

    # Setup persistence
    state_file = args.state or get_default_state_file(device)
    persistence = ControlPersistence(state_file)
    log(f"State file: {state_file}")

    # Create service
    service = V4L2ControlService(device, persistence)

    # Restore saved settings
    if not args.no_restore:
        service.restore_settings()

    # Create JSON-RPC server
    server = JSONRPCServer(args.socket)
    server.register_method("list", service.handle_list)
    server.register_method("get", service.handle_get)
    server.register_method("set", service.handle_set)
    server.register_method("info", service.handle_info)

    log(f"Starting V4L2 control service for {device}")
    log(f"JSON-RPC methods: list, get, set, info")

    # Run server
    try:
        server.run(log_func=log)
    except KeyboardInterrupt:
        log("Shutting down...")
    except Exception as e:
        log(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
