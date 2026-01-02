# v4l2-ctrls

A web-based interface for controlling V4L2 camera settings.

This application provides a standalone web server that allows you to control the settings of one or more V4L2 cameras using `v4l2-ctl`. It is designed to be used in conjunction with a separate streaming server, such as `stream-http`, and can embed video streams from it.

## Dependencies

- Python 3
- `v4l-utils` (provides the `v4l2-ctl` command)

## Usage

To run the server, you need to specify the port and the V4L2 device(s) you want to control. You can also specify the base URL for the streaming server to enable the video preview.

```sh
./main.py --port 8081 \
          --device 1=/dev/video0 \
          --device 2=/dev/video2 \
          --stream-url-base http://localhost:8080
```

- `--port`: The port to run the web server on.
- `--device`: The mapping of a camera ID to a V4L2 device path. You can specify this argument multiple times for multiple cameras.
- `--stream-url-base`: The base URL of the `stream-http` server. This is used to construct the URLs for the video previews.

The control interface will be available at `http://localhost:8081/control`.
