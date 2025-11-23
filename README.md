# v4l2-mpp

V4L2 camera capture and streaming tools with Rockchip MPP hardware encoding for ARM64 Linux.

## Applications

| App | Description |
|-----|-------------|
| capture-mipi-mpp | V4L2 capture for MIPI CSI cameras with MPP hardware encoding (JPEG/H264) |
| capture-usb-mpp | V4L2 capture for USB cameras (MJPEG input) with MPP transcoding to H264 |
| stream-http | HTTP server for camera streaming (snapshots, MJPEG, H264, browser player) |
| stream-mqtt | Snapmaker U1 camera interface (timelapse, monitoring, MQTT control) |

## Building

```sh
./deps/compile_mpp.sh
cd apps/capture-mipi-mpp && make
cd apps/capture-usb-mpp && make
```

Python apps (stream-http, stream-mqtt) require no compilation.

## Dependencies

- Rockchip MPP library
- Python 3 with paho-mqtt (for stream-mqtt)
- ffmpeg (for timelapse video generation)

## License

GPL-3.0-or-later
