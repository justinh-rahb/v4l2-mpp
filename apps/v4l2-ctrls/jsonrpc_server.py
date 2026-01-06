#!/usr/bin/env python3
"""
JSON-RPC 2.0 server for Unix socket communication.

Provides a simple JSON-RPC server that listens on a Unix socket
and dispatches method calls to registered handlers.
"""

import json
import os
import socket
from typing import Any, Callable, Dict


class JSONRPCServer:
    """Simple JSON-RPC 2.0 server."""

    def __init__(self, socket_path: str):
        """Initialize server.

        Args:
            socket_path: Path to Unix socket
        """
        self.socket_path = socket_path
        self.methods: Dict[str, Callable] = {}

    def register_method(self, name: str, handler: Callable) -> None:
        """Register a JSON-RPC method handler.

        Args:
            name: Method name
            handler: Callable that takes params dict and returns result
        """
        self.methods[name] = handler

    def handle_request(self, request: Dict) -> Dict:
        """Handle a single JSON-RPC request.

        Args:
            request: JSON-RPC request dict

        Returns:
            JSON-RPC response dict
        """
        # Validate request
        if not isinstance(request, dict):
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32600,
                    "message": "Invalid Request"
                },
                "id": None
            }

        jsonrpc = request.get("jsonrpc")
        method = request.get("method")
        params = request.get("params", {})
        req_id = request.get("id")

        # Validate JSON-RPC version
        if jsonrpc != "2.0":
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32600,
                    "message": "Invalid Request: jsonrpc must be '2.0'"
                },
                "id": req_id
            }

        # Validate method
        if not isinstance(method, str):
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32600,
                    "message": "Invalid Request: method must be string"
                },
                "id": req_id
            }

        # Check if method exists
        if method not in self.methods:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                },
                "id": req_id
            }

        # Validate params
        if not isinstance(params, (dict, list, type(None))):
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32602,
                    "message": "Invalid params: must be dict, list, or null"
                },
                "id": req_id
            }

        # Convert list params to dict (positional to named)
        if isinstance(params, list):
            params = {}

        # Call method
        try:
            handler = self.methods[method]
            result = handler(params)

            # Check for application errors
            if isinstance(result, dict) and "error" in result:
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32000,
                        "message": result["error"]
                    },
                    "id": req_id
                }

            return {
                "jsonrpc": "2.0",
                "result": result,
                "id": req_id
            }

        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                },
                "id": req_id
            }

    def run(self, log_func: Callable[[str], None] = None) -> None:
        """Run the server.

        Args:
            log_func: Optional logging function
        """
        def log(msg: str):
            if log_func:
                log_func(msg)

        # Remove existing socket
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)

        # Create Unix socket
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(self.socket_path)
        sock.listen(5)
        os.chmod(self.socket_path, 0o666)

        log(f"JSON-RPC server listening on {self.socket_path}")

        try:
            while True:
                conn, _ = sock.accept()
                try:
                    # Read request
                    data = b""
                    while True:
                        chunk = conn.recv(4096)
                        if not chunk:
                            break
                        data += chunk
                        if b'\n' in data:
                            break

                    if not data:
                        continue

                    # Parse request
                    try:
                        request = json.loads(data.decode().strip())
                    except json.JSONDecodeError as e:
                        response = {
                            "jsonrpc": "2.0",
                            "error": {
                                "code": -32700,
                                "message": f"Parse error: {str(e)}"
                            },
                            "id": None
                        }
                        conn.sendall((json.dumps(response) + '\n').encode())
                        continue

                    # Handle request
                    response = self.handle_request(request)

                    # Send response
                    conn.sendall((json.dumps(response) + '\n').encode())

                except Exception as e:
                    log(f"Connection error: {e}")
                    error_response = {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32603,
                            "message": f"Internal error: {str(e)}"
                        },
                        "id": None
                    }
                    try:
                        conn.sendall((json.dumps(error_response) + '\n').encode())
                    except:
                        pass
                finally:
                    conn.close()

        finally:
            sock.close()
            if os.path.exists(self.socket_path):
                os.unlink(self.socket_path)


class JSONRPCClient:
    """Simple JSON-RPC 2.0 client for Unix sockets."""

    def __init__(self, socket_path: str):
        """Initialize client.

        Args:
            socket_path: Path to Unix socket
        """
        self.socket_path = socket_path
        self.request_id = 0

    def call(self, method: str, params: Dict = None) -> Any:
        """Make a JSON-RPC method call.

        Args:
            method: Method name
            params: Method parameters (dict)

        Returns:
            Method result

        Raises:
            Exception: If RPC call fails
        """
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": self.request_id
        }

        # Connect to server
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect(self.socket_path)

            # Send request
            sock.sendall((json.dumps(request) + '\n').encode())

            # Read response
            data = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b'\n' in data:
                    break

            # Parse response
            response = json.loads(data.decode().strip())

            # Check for errors
            if "error" in response:
                error = response["error"]
                raise Exception(f"RPC error {error.get('code')}: {error.get('message')}")

            return response.get("result")

        finally:
            sock.close()
