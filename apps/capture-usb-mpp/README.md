# capture-usb-mpp

V4L2 capture application for USB cameras (MJPEG input) with Rockchip MPP transcoding.

Captures MJPEG frames from USB cameras, decodes with MPP, and re-encodes to H264 for streaming. Passes through MJPEG directly for JPEG/MJPEG outputs.

## Features

- USB camera MJPEG capture
- Hardware JPEG decoding (MPP)
- Hardware H264 encoding (MPP)
- Unix socket output for JPEG snapshots, MJPEG streams, and H264 streams
- Configurable resolution, FPS, and bitrate
