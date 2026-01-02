#!/usr/bin/env python3

import socket
import argparse
import time
import json
import subprocess
import re
from urllib.parse import urlparse, parse_qs
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

from html_control import HTML_CONTROL

def log(msg):
    ts = time.strftime('%H:%M:%S')
    print(f"[{ts}] {msg}", flush=True)

def parse_v4l2_ctrls(ctrls_output):
    controls = {}
    ctrl_re = re.compile(r'^\s*(?P<name>\w+)\s+0x[0-9a-f]+\s+\((?P<type>\w+)\)\s*:\s*(?P<params>.*)$')
    for line in ctrls_output.strip().split('\n'):
        match = ctrl_re.match(line)
        if not match:
            continue

        data = match.groupdict()
        ctrl = {
            'name': data['name'],
            'type': data['type'],
            'value': None
        }

        params_str = data['params']

        value_match = re.search(r'value=(\S+)', params_str)
        if value_match:
            ctrl['value'] = int(value_match.group(1))

        if ctrl['type'] in ['int', 'integer']:
             min_match = re.search(r'min=(\S+)', params_str)
             max_match = re.search(r'max=(\S+)', params_str)
             step_match = re.search(r'step=(\S+)', params_str)
             if min_match: ctrl['min'] = int(min_match.group(1))
             if max_match: ctrl['max'] = int(max_match.group(1))
             if step_match: ctrl['step'] = int(step_match.group(1))

        controls[ctrl['name']] = ctrl
    return controls

def parse_v4l2_menus(menus_output, controls):
    current_ctrl = None
    menu_header_re = re.compile(r'^\s*(?P<name>\w+)\s+0x[0-9a-f]+\s+\(menu\):$')
    menu_item_re = re.compile(r'^\s*\t(?P<value>\d+):\s*(?P<label>.+)$')

    for line in menus_output.strip().split('\n'):
        header_match = menu_header_re.match(line)
        if header_match:
            name = header_match.group('name')
            if name in controls:
                current_ctrl = controls[name]
                current_ctrl['menu'] = []
            else:
                current_ctrl = None
            continue

        if current_ctrl:
            item_match = menu_item_re.match(line)
            if item_match:
                current_ctrl['menu'].append({
                    'value': int(item_match.group('value')),
                    'label': item_match.group('label').strip()
                })
    return controls

class CameraHandler(BaseHTTPRequestHandler):
    devices = {}
    stream_url_base = ''

    def log_message(self, format, *args):
        log(f"HTTP {self.address_string()} - {format % args}")

    def do_GET(self):
        log(f"Request: {self.path} from {self.address_string()}")
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        if path == '/control':
            self.handle_control()
        elif path == '/api/v4l2/ctrls':
            self.handle_api_v4l2_ctrls()
        elif path == '/api/v4l2/info':
            self.handle_api_v4l2_info()
        else:
            self.send_error(404, 'Not Found')
        log(f"Request done: {self.path}")

    def do_POST(self):
        log(f"POST: {self.path} from {self.address_string()}")
        path = urlparse(self.path).path
        if path == '/api/v4l2/set':
            self.handle_api_v4l2_set()
        else:
            self.send_error(404, 'Not Found')
        log(f"POST done: {self.path}")

    def send_html(self, html):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Content-Length', len(html))
        self.end_headers()
        self.wfile.write(html.encode())

    def send_json_response(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(data))
        self.end_headers()
        self.wfile.write(data)

    def handle_control(self):
        if not self.devices:
            self.send_error(503, 'No V4L2 devices specified')
            return

        # Inject the base URL into the HTML template
        html = HTML_CONTROL.replace('%%STREAM_URL_BASE%%', self.stream_url_base)
        self.send_html(html)

    def handle_api_v4l2_info(self):
        query_components = parse_qs(urlparse(self.path).query)
        cam_id = query_components.get('cam', ['1'])[0]

        if not self.devices:
            self.send_json_response(503, {'error': 'No V4L2 devices specified'})
            return

        device = self.devices.get(cam_id)
        if not device:
            self.send_json_response(404, {'error': f'Camera {cam_id} not found'})
            return

        try:
            result = subprocess.run(
                ['v4l2-ctl', '-d', device, '-D'],
                capture_output=True, text=True, check=True
            )
            self.send_json_response(200, {'info': result.stdout})
        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to get device info: {e.stderr}"
            log(error_msg)
            self.send_json_response(500, {'error': error_msg})
        except Exception as e:
            error_msg = f"An unexpected error occurred: {str(e)}"
            log(error_msg)
            self.send_json_response(500, {'error': error_msg})

    def handle_api_v4l2_ctrls(self):
        query_components = parse_qs(urlparse(self.path).query)
        cam_id = query_components.get('cam', ['1'])[0]

        if not self.devices:
            self.send_json_response(503, {'error': 'No V4L2 devices specified'})
            return

        device = self.devices.get(cam_id)
        if not device:
            self.send_json_response(404, {'error': f'Camera {cam_id} not found'})
            return

        try:
            # Get controls
            ctrls_result = subprocess.run(
                ['v4l2-ctl', '-d', device, '--list-ctrls'],
                capture_output=True, text=True, check=True
            )
            controls = parse_v4l2_ctrls(ctrls_result.stdout)

            # Get menus
            menus_result = subprocess.run(
                ['v4l2-ctl', '-d', device, '--list-ctrls-menus'],
                capture_output=True, text=True, check=True
            )
            controls = parse_v4l2_menus(menus_result.stdout, controls)

            # Sort controls by priority
            priority = [
                'focus_auto', 'focus_absolute', 'exposure_auto', 'exposure_absolute',
                'white_balance_temperature_auto', 'white_balance_temperature',
                'brightness', 'contrast', 'saturation', 'sharpness', 'gain'
            ]

            sorted_controls = sorted(
                controls.values(),
                key=lambda x: priority.index(x['name']) if x['name'] in priority else len(priority)
            )

            self.send_json_response(200, sorted_controls)

        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to execute v4l2-ctl: {e.stderr}"
            log(error_msg)
            self.send_json_response(500, {'error': error_msg})
        except Exception as e:
            error_msg = f"An unexpected error occurred: {str(e)}"
            log(error_msg)
            self.send_json_response(500, {'error': error_msg})

    def handle_api_v4l2_set(self):
        query_components = parse_qs(urlparse(self.path).query)
        cam_id = query_components.get('cam', ['1'])[0]

        if not self.devices:
            self.send_json_response(503, {'error': 'No V4L2 devices specified'})
            return

        device = self.devices.get(cam_id)
        if not device:
            self.send_json_response(404, {'error': f'Camera {cam_id} not found'})
            return

        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode()
            settings = json.loads(body)

            # Get the list of available controls to build an allowlist
            ctrls_result = subprocess.run(
                ['v4l2-ctl', '-d', device, '--list-ctrls'],
                capture_output=True, text=True, check=True
            )
            available_ctrls = parse_v4l2_ctrls(ctrls_result.stdout)
            allowed_ctrls = set(available_ctrls.keys())

            # Validate and build the command
            set_ctrls = []
            for key, value in settings.items():
                if key in allowed_ctrls:
                    if not isinstance(value, int):
                        raise ValueError(f"Control '{key}' must be an integer.")
                    set_ctrls.append(f"{key}={value}")
                else:
                    raise ValueError(f"Control '{key}' is not recognized or allowed.")

            if not set_ctrls:
                self.send_json_response(400, {'error': 'No valid controls to set.'})
                return

            # Apply the settings
            command = ['v4l2-ctl', '-d', device, f'--set-ctrl={",".join(set_ctrls)}']
            result = subprocess.run(command, capture_output=True, text=True)

            if result.returncode != 0:
                raise subprocess.CalledProcessError(result.returncode, command, output=result.stdout, stderr=result.stderr)

            self.send_json_response(200, {
                'ok': True,
                'applied': settings,
                'stdout': result.stdout,
                'stderr': result.stderr
            })

        except json.JSONDecodeError:
            self.send_json_response(400, {'error': 'Invalid JSON.'})
        except ValueError as e:
            self.send_json_response(400, {'error': str(e)})
        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to set controls: {e.stderr}"
            log(error_msg)
            self.send_json_response(500, {'error': error_msg})
        except Exception as e:
            error_msg = f"An unexpected error occurred: {str(e)}"
            log(error_msg)
            self.send_json_response(500, {'error': error_msg})

def main():
    parser = argparse.ArgumentParser(description='V4L2-MPP Control Server')
    parser.add_argument('-p', '--port', type=int, default=8080, help='HTTP port')
    parser.add_argument('--bind', default='0.0.0.0', help='Bind address')
    parser.add_argument('--device', action='append', help='V4L2 device path (e.g., --device 1=/dev/video0)')
    parser.add_argument('--stream-url-base', default='', help='Base URL for video streams')
    args = parser.parse_args()

    if args.device:
        for device_map in args.device:
            cam_id, dev_path = device_map.split('=', 1)
            CameraHandler.devices[cam_id] = dev_path

    CameraHandler.stream_url_base = args.stream_url_base

    server = ThreadingHTTPServer((args.bind, args.port), CameraHandler)
    log(f"Server running on http://{args.bind}:{args.port}")
    log(f"  /control - V4L2 control interface")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("Shutting down...")

if __name__ == '__main__':
    main()
