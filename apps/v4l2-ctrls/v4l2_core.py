#!/usr/bin/env python3
"""
Core V4L2 control operations.

Handles device interaction, control parsing, and value management.
"""

import glob
import re
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


CONTROL_ORDER = [
    "focus_auto",
    "focus_automatic_continuous",
    "focus_absolute",
    "exposure_auto",
    "exposure_absolute",
    "exposure_time_absolute",
    "white_balance_temperature_auto",
    "white_balance_temperature",
    "brightness",
    "contrast",
    "saturation",
    "sharpness",
    "gain",
]


@dataclass
class Control:
    """Represents a V4L2 control."""
    name: str
    type: str
    min: Optional[int]
    max: Optional[int]
    step: Optional[int]
    value: Optional[int]
    menu: List[Dict[str, any]]


def run_v4l2(args: List[str], timeout: float = 3.0) -> Tuple[int, str, str]:
    """Execute v4l2-ctl command and return result."""
    try:
        result = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired as exc:
        return 124, "", f"Timeout running {' '.join(args)}: {exc}"


def detect_devices(limit: int = 8) -> List[str]:
    """Auto-detect V4L2 devices."""
    devices: List[str] = []
    code, out, err = run_v4l2(["v4l2-ctl", "--list-devices"], timeout=2.0)
    if code == 0:
        devices = parse_listed_devices(out)

    if not devices:
        subdevs = sorted(glob.glob("/dev/v4l-subdev*"))
        videos = sorted(glob.glob("/dev/video*"))
        devices = subdevs + videos

    # Prioritize subdevices
    subdevs = [device for device in devices if "/dev/v4l-subdev" in device]
    others = [device for device in devices if device not in subdevs]
    devices = subdevs + others

    # Prefer /dev/v4l-subdev2
    preferred = "/dev/v4l-subdev2"
    if preferred in devices:
        devices.remove(preferred)
        devices.insert(0, preferred)

    return devices[:limit]


def parse_listed_devices(output: str) -> List[str]:
    """Parse v4l2-ctl --list-devices output."""
    devices = []
    for line in output.splitlines():
        line = line.strip()
        if not line.startswith("/dev/"):
            continue
        devices.append(line.split()[0])
    return devices


def normalize_type(ctrl_type: Optional[str]) -> str:
    """Normalize control type string."""
    if not ctrl_type:
        return "unknown"
    if ctrl_type == "bool":
        return "bool"
    if ctrl_type.startswith("int"):
        return "int"
    if ctrl_type == "menu":
        return "menu"
    return ctrl_type


def get_int_from_parts(parts: List[str], field: str) -> Optional[int]:
    """Extract integer value from control line parts."""
    token = next((p for p in parts if p.startswith(f"{field}=")), None)
    if not token:
        return None
    try:
        return int(token.split("=", 1)[1])
    except ValueError:
        return None


def parse_ctrls(output: str) -> List[Dict]:
    """Parse v4l2-ctl --list-ctrls output."""
    controls = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("Error"):
            continue

        # Skip section headers (lines without hex codes)
        if "0x" not in line:
            continue

        parts = line.split()
        if not parts:
            continue

        name = parts[0]
        type_start = line.find("(")
        type_end = line.find(")")
        ctrl_type = None
        if type_start != -1 and type_end != -1:
            ctrl_type = line[type_start + 1 : type_end].strip()

        controls.append(
            {
                "name": name,
                "type": normalize_type(ctrl_type),
                "min": get_int_from_parts(parts, "min"),
                "max": get_int_from_parts(parts, "max"),
                "step": get_int_from_parts(parts, "step"),
                "value": get_int_from_parts(parts, "value"),
                "menu": [],
            }
        )
    return controls


def parse_ctrl_menus(output: str) -> Dict[str, List[Dict[str, str]]]:
    """Parse v4l2-ctl --list-ctrls-menus output.

    Example output format:
    power_line_frequency 0x00980918 (menu)   : min=0 max=2 default=1 value=1 (50 Hz)
        0: Disabled
        1: 50 Hz
        2: 60 Hz
    """
    menus: Dict[str, List[Dict[str, str]]] = {}
    current = None

    for line in output.splitlines():
        if not line.strip():
            continue

        stripped = line.strip()

        # Skip section headers
        if stripped in ["User Controls", "Camera Controls", "Video Controls", "Image Controls"]:
            continue

        # Menu items: start with a number followed by colon
        if stripped and stripped[0].isdigit() and ":" in stripped:
            if current is None:
                continue
            parts = stripped.split(":", 1)
            try:
                value = int(parts[0].strip())
                label = parts[1].strip()
                menus[current].append({"value": value, "label": label})
            except (ValueError, IndexError):
                continue
        # Control name lines: contain hex code like "0x00980918"
        elif "0x" in stripped:
            name = stripped.split()[0]
            current = name
            menus.setdefault(current, [])

    return menus


def sort_controls(controls: List[Dict]) -> List[Dict]:
    """Sort controls by predefined order."""
    order_map = {name: idx for idx, name in enumerate(CONTROL_ORDER)}
    indexed = list(enumerate(controls))

    def sort_key(item: Tuple[int, Dict]) -> Tuple[int, int]:
        original_idx, ctrl = item
        idx = order_map.get(ctrl["name"], len(CONTROL_ORDER))
        return (idx, original_idx)

    return [ctrl for _, ctrl in sorted(indexed, key=sort_key)]


def list_controls(device: str) -> Dict:
    """List all controls for a device.

    Returns:
        {
            "controls": [...],
            "error": "..." (if failed)
        }
    """
    # Get basic control list
    code1, out1, err1 = run_v4l2(["v4l2-ctl", "-d", device, "--list-ctrls"])
    if code1 != 0:
        return {"error": err1 or out1 or "Failed to list controls"}

    controls = parse_ctrls(out1)

    # Get menu options
    code2, out2, err2 = run_v4l2(["v4l2-ctl", "-d", device, "--list-ctrls-menus"])
    if code2 == 0:
        menus = parse_ctrl_menus(out2)
        # Merge menu data into controls
        for ctrl in controls:
            ctrl_name = ctrl["name"]
            if ctrl_name in menus and menus[ctrl_name]:
                ctrl["menu"] = menus[ctrl_name]
                ctrl["type"] = "menu"

    controls = sort_controls(controls)
    return {"controls": controls}


def get_control_values(device: str, control_names: List[str] = None) -> Dict:
    """Get current values for specific controls or all controls.

    Args:
        device: Device path
        control_names: Optional list of control names to get. If None, gets all.

    Returns:
        {
            "values": {"control_name": value, ...},
            "error": "..." (if failed)
        }
    """
    code, out, err = run_v4l2(["v4l2-ctl", "-d", device, "--list-ctrls"])
    if code != 0:
        return {"error": err or out or "Failed to get control values"}

    controls = parse_ctrls(out)
    values = {}

    for ctrl in controls:
        if control_names is None or ctrl["name"] in control_names:
            if ctrl["value"] is not None:
                values[ctrl["name"]] = ctrl["value"]

    return {"values": values}


def set_controls(device: str, changes: Dict[str, int]) -> Dict:
    """Set control values.

    Args:
        device: Device path
        changes: Dict mapping control names to new values

    Returns:
        {
            "ok": bool,
            "applied": {"control_name": value, ...},
            "error": "..." (if failed)
        }
    """
    if not changes:
        return {"error": "No controls provided"}

    # Validate controls exist and values are in range
    code, out, err = run_v4l2(["v4l2-ctl", "-d", device, "--list-ctrls"])
    if code != 0:
        return {"error": err or out or "Failed to list controls"}

    controls = parse_ctrls(out)
    control_map = {ctrl["name"]: ctrl for ctrl in controls}
    allowlist = set(control_map.keys())

    validated = {}
    for key, value in changes.items():
        if key not in allowlist:
            return {"error": f"Unknown control: {key}"}

        if not isinstance(value, int):
            return {"error": f"Value for {key} must be integer"}

        ctrl_def = control_map.get(key)
        if ctrl_def:
            min_val = ctrl_def.get("min")
            max_val = ctrl_def.get("max")
            if min_val is not None and max_val is not None:
                if not (min_val <= value <= max_val):
                    return {
                        "error": f"{key}={value} out of range [{min_val}, {max_val}]"
                    }

        validated[key] = value

    # Apply changes
    set_parts = [f"{key}={value}" for key, value in validated.items()]
    cmd = ["v4l2-ctl", "-d", device, f"--set-ctrl={','.join(set_parts)}"]
    code, out, err = run_v4l2(cmd)

    if code != 0:
        return {"ok": False, "error": err or out or "Failed to set controls"}

    return {"ok": True, "applied": validated}


def get_device_info(device: str) -> Dict:
    """Get device information.

    Returns:
        {
            "info": "...",
            "error": "..." (if failed)
        }
    """
    code, out, err = run_v4l2(["v4l2-ctl", "-d", device, "-D"])
    if code != 0:
        return {"error": err or out or "Failed to fetch device info"}

    return {"info": out}
