#!/usr/bin/env python3
"""Exercise non-exiting hangs and cleanup with real local child processes."""
import http.server
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest

import console_backend_connection as connection


class Handler(http.server.BaseHTTPRequestHandler):
    code = 200
    requests = 0

    def do_GET(self):
        type(self).requests += 1
        self.send_response(self.code)
        if self.code == 302:
            self.send_header('Location', '/unexpected-redirect')
        self.end_headers()
        self.wfile.write(b'ok')

    def log_message(self, *_):
        pass


class BackendConnectionTests(unittest.TestCase):
    def test_http_error_is_responsive_and_redirects_are_not_followed(self):
        with http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                for status in [200, 503, 302]:
                    Handler.code = status
                    before = Handler.requests
                    self.assertEqual(connection.probe(server.server_port, .2), status)
                    self.assertEqual(Handler.requests, before + 1)
            finally:
                server.shutdown()

    def run_child(self, *, freeze=False, status=200):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / 'fake.py'
            fake.write_text('''import http.server, os, sys
from pathlib import Path
class Handler(http.server.BaseHTTPRequestHandler):
 def do_GET(self):
  self.send_response(int(sys.argv[2]));self.end_headers();self.wfile.write(b'ok')
 def log_message(self,*args):pass
server=http.server.HTTPServer(('127.0.0.1',0),Handler)
Path(sys.argv[1]).write_text(str(os.getpid())+' '+str(server.server_port))
server.serve_forever()
''')
            # Reserve a real port, then pass that fixed port to the fake child.
            fake.write_text(fake.read_text().replace("('127.0.0.1',0)", "('127.0.0.1',int(sys.argv[3]))"))
            with socket.socket() as listener:
                listener.bind(('127.0.0.1', 0))
                port = listener.getsockname()[1]
            marker = root / 'started'
            stop = threading.Event()
            result = []
            thread = threading.Thread(target=lambda: result.append(connection.supervise(
                [sys.executable, str(fake), str(marker), str(status), str(port)], port, stop,
                interval=.05, startup_grace=.5, failure_limit=3, probe_timeout=.05)))
            thread.start()
            pid = None
            try:
                deadline = time.monotonic() + 3
                while not marker.exists() and time.monotonic() < deadline:
                    time.sleep(.01)
                self.assertTrue(marker.exists())
                pid = int(marker.read_text().split()[0])
                time.sleep(.15)
                self.assertTrue(thread.is_alive())
                if freeze:
                    os.kill(pid, signal.SIGSTOP)
                    thread.join(5)
                    self.assertEqual(result, [75])
                else:
                    # A 503 is backend unavailability, not a reason to replace
                    # a working transport or replay any business request.
                    stop.set()
                    thread.join(2)
                    self.assertEqual(result, [0])
                with self.assertRaises(ProcessLookupError):
                    os.kill(pid, 0)
            finally:
                stop.set()
                thread.join(5)
                if thread.is_alive() and pid:
                    os.kill(pid, signal.SIGKILL)
                    thread.join(2)

    def test_live_but_frozen_child_is_detected_and_reaped(self):
        self.run_child(freeze=True)

    def test_normal_stop_reaps_the_child(self):
        self.run_child()

    def test_responding_unhealthy_backend_does_not_cause_restart(self):
        self.run_child(status=503)

    def test_successful_unexpected_child_exit_requires_restart(self):
        stop = threading.Event()
        self.assertEqual(connection.supervise([sys.executable, '-c', 'pass'], 1, stop,
            interval=.01, startup_grace=1), 1)


if __name__ == '__main__':
    unittest.main()
