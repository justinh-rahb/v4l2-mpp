# v4l2-ctrls

A backend-only JSON-RPC service that exposes V4L2 camera controls over Unix sockets. Designed for clean separation of concerns and integration with `stream-http`.

## Architecture

The refactored architecture follows a **one-way data flow**:

```
stream-http → stream-webrtc → v4l2-ctrls
    ↓
  (Web UI)
```

**Benefits:**
- No circular dependencies
- Single responsibility per component
- Unified web interface through `stream-http`
- Extensible to support multiple control backends (v4l2, libcamera, etc.)

## Components

### Core Modules

- **`v4l2_core.py`**: Core V4L2 operations (device detection, control parsing, value management)
- **`jsonrpc_server.py`**: JSON-RPC 2.0 server and client implementation
- **`persistence.py`**: Control value persistence (save/restore to JSON files)
- **`v4l2-ctrls.py`**: Main service entry point

### JSON-RPC Methods

The service exposes four methods:

#### `list`
Get all available controls with metadata.

**Parameters:** None

**Returns:**
```json
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
    }
  ]
}
```

#### `get`
Read current control values.

**Parameters:**
```json
{
  "controls": ["brightness", "contrast"]
}
```

**Returns:**
```json
{
  "values": {
    "brightness": 128,
    "contrast": 100
  }
}
```

#### `set`
Change control values and persist them.

**Parameters:**
```json
{
  "controls": {
    "brightness": 150,
    "contrast": 110
  }
}
```

**Returns:**
```json
{
  "ok": true,
  "applied": {
    "brightness": 150,
    "contrast": 110
  }
}
```

#### `info`
Get device information.

**Parameters:** None

**Returns:**
```json
{
  "info": "Driver Info: ..."
}
```

## Requirements

- Python 3.7+
- `v4l2-ctl` in PATH
- Unix socket support

## Usage

### Start the Service

```bash
# For a specific device
./v4l2-ctrls.py --device /dev/video11 --socket /tmp/v4l2-ctrls.sock

# Auto-detect device (uses first available, prefers /dev/v4l-subdev2)
./v4l2-ctrls.py --socket /tmp/v4l2-ctrls.sock

# Custom state file location
./v4l2-ctrls.py --device /dev/video11 --socket /tmp/v4l2.sock --state /tmp/v4l2-state.json

# Don't restore saved settings on startup
./v4l2-ctrls.py --device /dev/video11 --socket /tmp/v4l2.sock --no-restore
```

### Integration with stream-http

The `stream-http` component serves the camera controls UI and forwards JSON-RPC requests:

```bash
# Start v4l2-ctrls service
./v4l2-ctrls.py --device /dev/video11 --socket /tmp/v4l2-ctrls.sock &

# Start stream-http with control integration
./stream-http/main.py \
  --port 8080 \
  --jpeg-sock /tmp/snap.sock \
  --mjpeg-sock /tmp/mjpeg.sock \
  --h264-sock /tmp/h264.sock \
  --webrtc-sock /tmp/webrtc.sock \
  --control-sock /tmp/v4l2-ctrls.sock
```

Access the controls UI at: `http://localhost:8080/control/`

## Persistence

Control values are automatically saved when changed via the `set` method. On startup, the service restores previously saved values.

**Default state file location:**
```
$XDG_STATE_HOME/v4l2-ctrls/<device>.json
~/.local/state/v4l2-ctrls/<device>.json  (if XDG_STATE_HOME not set)
```

**Example state file:**
```json
{
  "brightness": 128,
  "contrast": 100,
  "saturation": 128,
  "sharpness": 3
}
```

## JSON-RPC Client Example

```python
from jsonrpc_server import JSONRPCClient

client = JSONRPCClient('/tmp/v4l2-ctrls.sock')

# List all controls
controls = client.call('list')
print(controls['controls'])

# Get specific control values
values = client.call('get', {'controls': ['brightness', 'contrast']})
print(values['values'])

# Set control values
result = client.call('set', {
    'controls': {
        'brightness': 150,
        'contrast': 110
    }
})
print(result['applied'])

# Get device info
info = client.call('info')
print(info['info'])
```

## Migration from Old Flask-Based Version

### What Changed

1. **Removed Flask web server** - Now JSON-RPC over Unix socket only
2. **Single device focus** - Uses `--device` parameter or auto-detects one device
3. **Backend persistence** - Values saved automatically, no frontend localStorage
4. **No multi-camera support** - Run multiple instances for multiple devices
5. **Web UI moved to stream-http** - Access via `/control/` on stream-http

### Old Command
```bash
python3 v4l2-ctrls.py --device /dev/video11 --device /dev/video12 --port 5001
```

### New Command
```bash
# Device 1
./v4l2-ctrls.py --device /dev/video11 --socket /tmp/v4l2-dev1.sock &

# Device 2
./v4l2-ctrls.py --device /dev/video12 --socket /tmp/v4l2-dev2.sock &

# stream-http (serves unified UI)
./stream-http/main.py --control-sock /tmp/v4l2-dev1.sock ...
```

## Design Principles

1. **Separation of concerns**: Control logic separate from web presentation
2. **Single responsibility**: One device per service instance
3. **Persistence**: Settings survive restarts
4. **Clean interfaces**: JSON-RPC for machine-to-machine communication
5. **No circular dependencies**: Unidirectional data flow
