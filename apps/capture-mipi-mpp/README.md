# capture-mipi-mpp

V4L2 capture application for MIPI CSI cameras with Rockchip MPP hardware encoding.

Captures raw video frames (YUYV, NV12, etc.) from MIPI cameras and encodes to JPEG/H264 using MPP. Outputs via Unix sockets for streaming consumers.

## Features

- Multi-planar V4L2 capture support
- Hardware JPEG encoding (MPP)
- Hardware H264 encoding (MPP)
- Unix socket output for JPEG snapshots, MJPEG streams, and H264 streams
- Configurable resolution, FPS, bitrate, and quality
