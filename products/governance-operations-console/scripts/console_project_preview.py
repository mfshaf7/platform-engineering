"""Serve the current admitted project from an isolated Windows loopback origin."""
from __future__ import annotations

from contextlib import nullcontext
from http.client import HTTPConnection, HTTPException
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import threading

from console_artifact_recovery import RecoveryDeferred

REQUEST_BYTES = 1024 * 1024
RESPONSE_BYTES = 16 * 1024 * 1024
SOCKET_TIMEOUT = 5
REQUEST_HEADERS = ("Accept", "Accept-Language", "Content-Type", "Cookie", "If-None-Match", "If-Modified-Since")
RESPONSE_HEADERS = {"content-type", "content-language", "content-encoding", "etag", "last-modified", "content-disposition"}
CONTENT_POLICY = (
    "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; "
    "form-action 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; worker-src 'none'"
)


class PreviewServer(ThreadingHTTPServer):
    def __init__(self, port, owner):
        self.owner = owner
        self.capacity = threading.BoundedSemaphore(8)
        super().__init__(("127.0.0.1", port), PreviewRequest)

    def process_request(self, request, client_address):
        if not self.capacity.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.capacity.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.capacity.release()


class PreviewRequest(BaseHTTPRequestHandler):
    def setup(self):
        self.request.settimeout(SOCKET_TIMEOUT)
        super().setup()

    def log_message(self, *_args):
        pass

    def _reply(self, status, body=b"", forwarded=()):
        self.send_response_only(status)
        self.send_header("Content-Security-Policy", CONTENT_POLICY)
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        for name, value in forwarded:
            self.send_header(name, value)
        try:
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)
        except (ConnectionError, TimeoutError):
            # Browser navigation can cancel a resource without a runtime failure.
            pass

    def _forward(self):
        owner = self.server.owner
        route = owner.route(self.headers.get_all("Host", []))
        if route is None:
            return self._reply(421, b"Preview unavailable")
        if not self.path.startswith("/") or self.path.startswith("//") or "\\" in self.path:
            return self._reply(400, b"Invalid preview path")
        origin = self.headers.get("Origin")
        site = self.headers.get("Sec-Fetch-Site")
        direct_navigation = self.command in {"GET", "HEAD"} and self.headers.get("Sec-Fetch-Mode") == "navigate"
        if (origin is not None and origin != f"http://{route[1]}") or (
                site in {"same-site", "cross-site"} and not direct_navigation) or (
                self.command not in {"GET", "HEAD"} and origin != f"http://{route[1]}"):
            return self._reply(403, b"Preview origin refused")
        counts = self.headers.get_all("Content-Length", [])
        if self.headers.get("Transfer-Encoding") is not None or len(counts) > 1:
            return self._reply(400, b"Unsupported preview request")
        size = counts[0] if counts else "0"
        if not size.isascii() or not size.isdecimal() or len(size) > 8 or int(size) > REQUEST_BYTES:
            return self._reply(413, b"Preview input is too large")
        try:
            body = self.rfile.read(int(size))
            if len(body) != int(size):
                return self._reply(400, b"Incomplete preview request")
            target = owner.target(route)
            if target is None or not owner.current(route):
                return self._reply(503, b"Run no longer available")
            address, port = target
            upstream = HTTPConnection(str(ipaddress.ip_address(address)), port, timeout=SOCKET_TIMEOUT)
            headers = {header: self.headers[header] for header in REQUEST_HEADERS if header in self.headers}
            headers["Host"] = route[1]
            try:
                upstream.request(self.command, self.path, body=body if size != "0" else None, headers=headers)
                response = upstream.getresponse()
                result = response.read(RESPONSE_BYTES + 1)
                forwarded = []
                for name, value in response.getheaders():
                    key = name.lower()
                    if any(ord(char) < 32 or ord(char) == 127 for char in value):
                        continue
                    if key in RESPONSE_HEADERS or (key == "location" and value.startswith("/") and
                            not value.startswith("//") and "\\" not in value) or (
                            key == "set-cookie" and not any(attr.partition("=")[0].strip().lower() == "domain"
                                for attr in value.split(";")[1:])):
                        forwarded.append((name, value))
                if len(result) > RESPONSE_BYTES or not owner.current(route):
                    return self._reply(503, b"Run no longer available or output exceeds the preview limit")
                return self._reply(response.status, result, forwarded)
            finally:
                upstream.close()
        except (HTTPException, OSError, ValueError):
            return self._reply(502, b"Run could not be reached")

    do_GET = do_HEAD = do_POST = do_PUT = do_PATCH = do_DELETE = _forward


class ProjectPreview:
    """Own one live browser route in the existing provider process."""
    def __init__(self, port, *, owner_guard=nullcontext):
        self.port = port
        self.owner_guard = owner_guard
        self._lock = threading.Lock()
        self._server = None
        self._active = None

    def expose(self, scope_digest, operation, resolve):
        with self._lock:
            if self._server is None:
                self._server = PreviewServer(self.port, self)
                threading.Thread(target=self._server.serve_forever, daemon=True).start()
            host = f"project-{scope_digest[7:55]}.localhost:{self._server.server_port}"
            if self._active is None or self._active[:2] != (operation, host):
                self._active = (operation, host, resolve)
            return f"http://{host}/"

    def withdraw(self, operation):
        with self._lock:
            if self._active is not None and self._active[0] == operation:
                self._active = None

    def route(self, hosts):
        with self._lock:
            return self._active if self._active is not None and hosts == [self._active[1]] else None

    def current(self, route):
        with self._lock:
            return self._active is route

    def target(self, route):
        try:
            with self.owner_guard():
                return route[2]()
        except (RecoveryDeferred, ValueError):
            return None

    def close(self):
        with self._lock:
            server, self._server, self._active = self._server, None, None
        if server is not None:
            server.shutdown()
            server.server_close()
