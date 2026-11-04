#!/usr/bin/env python3
"""Supervise one existing loopback tunnel, including a live-but-stalled child."""
from __future__ import annotations

import argparse
import os
import re
import signal
import subprocess
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


def probe(port: int, timeout: float = 2) -> int | None:
    """Probe transport, not readiness; an HTTP error is still a responding peer."""
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        request = Request(f"http://127.0.0.1:{port}/healthz", headers={"Connection": "close"})
        with opener.open(request, timeout=timeout) as response:
            response.read(4097)
            return response.status
    except HTTPError as error:
        # Do not recycle a working tunnel because its backend reports an
        # unhealthy state or redirects. Do not follow the redirect or log data.
        error.close()
        return error.code
    except (OSError, URLError, TimeoutError):
        return None


def stop_child(child: subprocess.Popen, timeout: float = 3) -> None:
    if child.poll() is not None:
        return
    try:
        os.killpg(child.pid, signal.SIGTERM)
        try:
            child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=timeout)
    except ProcessLookupError:
        child.wait(timeout=timeout)


def supervise(command: list[str], port: int, stop: threading.Event, *,
              interval: float = 10, startup_grace: float = 20,
              failure_limit: int = 3, probe_timeout: float = 2) -> int:
    child = subprocess.Popen(command, start_new_session=True)
    grace_until = time.monotonic() + startup_grace
    next_probe = time.monotonic()
    failures = 0
    try:
        while not stop.is_set():
            if child.poll() is not None:
                print("Backend tunnel exited; supervised reconnect required.", flush=True)
                return 1
            now = time.monotonic()
            if now >= next_probe:
                status = probe(port, probe_timeout)
                if status is not None:
                    failures = 0
                    grace_until = 0
                elif time.monotonic() >= grace_until:
                    failures += 1
                    if failures >= failure_limit:
                        print("Backend tunnel is unresponsive; recycling only this connection.", flush=True)
                        return 75
                next_probe = time.monotonic() + interval
            stop.wait(min(interval, 1))
        return 0
    finally:
        stop_child(child)


def dns_label(value: str) -> str:
    if len(value) > 63 or not re.fullmatch(r"[a-z0-9](?:[-a-z0-9]*[a-z0-9])?", value):
        raise argparse.ArgumentTypeError("expected a Kubernetes DNS label")
    return value


def port_number(value: str) -> int:
    try:
        port = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("expected a TCP port") from None
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("expected a TCP port")
    return port


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--k3s", required=True)
    parser.add_argument("--namespace", required=True, type=dns_label)
    parser.add_argument("--service", required=True, type=dns_label)
    parser.add_argument("--local-port", required=True, type=port_number)
    parser.add_argument("--remote-port", required=True, type=port_number)
    args = parser.parse_args()
    stop = threading.Event()
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda *_: stop.set())
    command = [args.k3s, "kubectl", "-n", args.namespace, "port-forward",
               f"service/{args.service}", f"{args.local_port}:{args.remote_port}",
               "--address", "127.0.0.1"]
    return supervise(command, args.local_port, stop)


if __name__ == "__main__":
    raise SystemExit(main())
