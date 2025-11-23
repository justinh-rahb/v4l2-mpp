#!/usr/bin/env python3

import socket
import argparse
import time
from urllib.parse import urlparse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

def log(msg):
    ts = time.strftime('%H:%M:%S')
    print(f"[{ts}] {msg}", flush=True)

def read_socket(sock_path, chunk_size=65536):
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(sock_path)
    try:
        while True:
            chunk = sock.recv(chunk_size)
            if not chunk:
                break
            yield chunk
    finally:
        sock.close()

def read_h264_from_keyframe(sock_path, chunk_size=65536):
    for chunk in read_socket(sock_path, chunk_size):
        yield chunk

def read_jpeg_frames(sock_path, chunk_size=65536):
    buf = b''
    for chunk in read_socket(sock_path, chunk_size):
        buf += chunk
        while True:
            start = buf.find(b'\xff\xd8')
            if start == -1:
                buf = buf[-1:] if buf else b''
                break
            end = buf.find(b'\xff\xd9', start + 2)
            if end == -1:
                buf = buf[start:]
                break
            yield buf[start:end + 2]
            buf = buf[end + 2:]

class CameraHandler(BaseHTTPRequestHandler):
    jpeg_sock = None
    mjpeg_sock = None
    h264_sock = None

    def log_message(self, format, *args):
        log(f"HTTP {self.address_string()} - {format % args}")

    def do_GET(self):
        log(f"Request: {self.path} from {self.address_string()}")
        path = urlparse(self.path).path
        if path == '/snapshot.jpg':
            self.handle_snapshot()
        elif path == '/stream.mjpg':
            self.handle_mjpeg_stream()
        elif path == '/stream.h264':
            self.handle_h264_stream()
        elif path == '/player':
            self.handle_player()
        elif path == '/':
            self.handle_index()
        else:
            self.send_error(404, 'Not Found')
        log(f"Request done: {self.path}")

    def handle_index(self):
        html = '''<!DOCTYPE html>
<html>
<head><title>Camera Stream</title></head>
<body>
<h1>Camera Stream</h1>
<p><a href="snapshot.jpg">JPEG Snapshot</a></p>
<p><a href="stream.mjpg">MJPEG Stream</a></p>
<p><a href="stream.h264">H264 Stream (raw)</a></p>
<p><a href="player">H264 Player</a></p>
</body>
</html>'''
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Content-Length', len(html))
        self.end_headers()
        self.wfile.write(html.encode())

    def handle_snapshot(self):
        if not self.jpeg_sock:
            self.send_error(503, 'Snapshot not available')
            return
        self.send_response(200)
        self.send_header('Content-Type', 'image/jpeg')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.end_headers()
        try:
            total = 0
            for chunk in read_socket(self.jpeg_sock):
                self.wfile.write(chunk)
                total += len(chunk)
            log(f"JPEG sent {total} bytes")
        except (BrokenPipeError, ConnectionResetError) as e:
            log(f"JPEG client disconnected: {e}")
        except (FileNotFoundError, IOError, OSError) as e:
            log(f"JPEG error: {e}")

    def handle_mjpeg_stream(self):
        if not self.mjpeg_sock:
            self.send_error(503, 'MJPEG stream not available')
            return
        self.send_response(200)
        self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.end_headers()
        log(f"Connecting to MJPEG socket: {self.mjpeg_sock}")
        frame_count = 0
        try:
            for frame in read_jpeg_frames(self.mjpeg_sock):
                self.wfile.write(b'--frame\r\nContent-Type: image/jpeg\r\n\r\n')
                self.wfile.write(frame)
                self.wfile.write(b'\r\n')
                self.wfile.flush()
                frame_count += 1
                if frame_count % 30 == 0:
                    log(f"MJPEG sent {frame_count} frames")
            log("MJPEG socket EOF")
        except (BrokenPipeError, ConnectionResetError) as e:
            log(f"MJPEG client disconnected: {e}")
        except (IOError, OSError) as e:
            log(f"MJPEG stream error: {e}")

    def handle_h264_stream(self):
        if not self.h264_sock:
            self.send_error(503, 'H264 stream not available')
            return
        self.send_response(200)
        self.send_header('Content-Type', 'video/h264')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.end_headers()
        log(f"Connecting to H264 socket: {self.h264_sock}")
        try:
            total_bytes = 0
            last_bytes = 0
            for chunk in read_h264_from_keyframe(self.h264_sock):
                self.wfile.write(chunk)
                self.wfile.flush()
                total_bytes += len(chunk)
                last_bytes += len(chunk)
                if last_bytes >= (1024 * 1024):
                    log(f"H264 sent {total_bytes // 1024}KB")
                    last_bytes = 0
            log("H264 socket EOF")
        except (BrokenPipeError, ConnectionResetError) as e:
            log(f"H264 client disconnected: {e}")
        except (IOError, OSError) as e:
            log(f"H264 stream error: {e}")

    def handle_player(self):
        html = '''<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Camera</title>
<script src="https://cdn.jsdelivr.net/npm/jmuxer@2.0.5/dist/jmuxer.min.js"></script>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body { width: 100%; height: 100%; background: #000; overflow: hidden; }
video, img { width: 100%; height: 100%; object-fit: contain; display: block; }
#snapshot { display: none; }
#fps { display: none; position: fixed; bottom: 10px; right: 10px; color: #fff; font: 14px monospace; background: rgba(0,0,0,0.5); padding: 4px 8px; border-radius: 4px; }
</style>
</head>
<body>
<video id="player" muted autoplay playsinline></video>
<img id="snapshot">
<div id="fps"></div>
<script>
let jmuxer = null;
let reader = null;

async function startH264() {
    try {
        jmuxer = new JMuxer({
            node: 'player',
            mode: 'video',
            flushingTime: 0,
            fps: 30,
            debug: false
        });

        const response = await fetch('stream.h264');
        if (!response.body || !response.body.getReader) {
            throw new Error('Streaming not supported');
        }
        reader = response.body.getReader();

        while (true) {
            const {value, done} = await reader.read();
            if (done) break;
            jmuxer.feed({video: value});
        }
    } catch (e) {
        fallbackToSnapshots();
    }
}

function fallbackToSnapshots() {
    if (reader) { reader.cancel().catch(() => {}); reader = null; }
    if (jmuxer) { jmuxer.destroy(); jmuxer = null; }

    document.getElementById('player').style.display = 'none';
    const img = document.getElementById('snapshot');
    const fpsEl = document.getElementById('fps');
    img.style.display = 'block';
    fpsEl.style.display = 'block';

    let frameCount = 0;
    let lastTime = performance.now();

    img.onload = () => {
        frameCount++;
        const now = performance.now();
        if (now - lastTime >= 1000) {
            fpsEl.textContent = frameCount + ' fps';
            frameCount = 0;
            lastTime = now;
        }
        img.src = 'snapshot.jpg?t=' + Date.now();
    };
    img.onerror = () => { setTimeout(() => { img.src = 'snapshot.jpg?t=' + Date.now(); }, 200); };
    img.src = 'snapshot.jpg?t=' + Date.now();
}

startH264();
</script>
</body>
</html>'''
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Content-Length', len(html))
        self.end_headers()
        self.wfile.write(html.encode())

def main():
    parser = argparse.ArgumentParser(description='V4L2-MPP HTTP Server')
    parser.add_argument('-p', '--port', type=int, default=8080, help='HTTP port')
    parser.add_argument('--bind', default='0.0.0.0', help='Bind address')
    parser.add_argument('--jpeg-sock', required=True, help='JPEG snapshot socket')
    parser.add_argument('--mjpeg-sock', required=True, help='MJPEG stream socket')
    parser.add_argument('--h264-sock', required=True, help='H264 stream socket')
    args = parser.parse_args()

    CameraHandler.jpeg_sock = args.jpeg_sock
    CameraHandler.mjpeg_sock = args.mjpeg_sock
    CameraHandler.h264_sock = args.h264_sock

    server = ThreadingHTTPServer((args.bind, args.port), CameraHandler)
    log(f"Server running on http://{args.bind}:{args.port}")
    log(f"  /snapshot.jpg - JPEG snapshot")
    log(f"  /stream.mjpg  - MJPEG stream")
    log(f"  /stream.h264  - H264 stream")
    log(f"  /player       - H264 player")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("Shutting down...")

if __name__ == '__main__':
    main()
