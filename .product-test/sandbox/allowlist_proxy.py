#!/usr/bin/env python3
"""Small domain-allowlisting HTTP CONNECT proxy for disposable test containers."""

from __future__ import annotations

import ipaddress
import os
import selectors
import socket
import socketserver
import urllib.parse


ALLOWED = tuple(
    item.strip().lower().rstrip(".")
    for item in os.environ.get("ALLOWLIST", "").split(",")
    if item.strip()
)


def allowed_host(host: str) -> bool:
    host = host.lower().rstrip(".")
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return any(host == domain or host.endswith("." + domain) for domain in ALLOWED)


def relay(left: socket.socket, right: socket.socket) -> None:
    selector = selectors.DefaultSelector()
    for sock in (left, right):
        sock.setblocking(False)
        selector.register(sock, selectors.EVENT_READ)
    try:
        while True:
            events = selector.select(timeout=60)
            if not events:
                return
            for key, _ in events:
                source = key.fileobj
                target = right if source is left else left
                try:
                    data = source.recv(65536)
                except OSError:
                    return
                if not data:
                    return
                target.sendall(data)
    finally:
        selector.close()


class ProxyHandler(socketserver.StreamRequestHandler):
    timeout = 30

    def handle(self) -> None:
        first = self.rfile.readline(65537)
        if not first or len(first) > 65536:
            return
        try:
            method, target, version = first.decode("latin-1").strip().split(" ", 2)
        except ValueError:
            self.wfile.write(b"HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n")
            return

        headers: list[bytes] = []
        while True:
            line = self.rfile.readline(65537)
            if not line or line in (b"\r\n", b"\n"):
                break
            if len(line) > 65536:
                return
            headers.append(line)

        if method.upper() == "CONNECT":
            self.handle_connect(target)
            return

        parsed = urllib.parse.urlsplit(target)
        host = parsed.hostname or ""
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if not allowed_host(host):
            self.wfile.write(b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n")
            return
        path = urllib.parse.urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
        try:
            with socket.create_connection((host, port), timeout=30) as upstream:
                upstream.sendall(f"{method} {path} {version}\r\n".encode("latin-1"))
                for line in headers:
                    lower = line.lower()
                    if lower.startswith((b"proxy-connection:", b"connection:")):
                        continue
                    upstream.sendall(line)
                upstream.sendall(b"Connection: close\r\n\r\n")
                while True:
                    data = upstream.recv(65536)
                    if not data:
                        break
                    self.wfile.write(data)
        except OSError:
            self.wfile.write(b"HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\n\r\n")

    def handle_connect(self, target: str) -> None:
        if ":" not in target:
            self.wfile.write(b"HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n")
            return
        host, raw_port = target.rsplit(":", 1)
        try:
            port = int(raw_port)
        except ValueError:
            return
        if port != 443 or not allowed_host(host):
            self.wfile.write(b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n")
            return
        try:
            upstream = socket.create_connection((host, port), timeout=30)
        except OSError:
            self.wfile.write(b"HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\n\r\n")
            return
        with upstream:
            self.wfile.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            self.wfile.flush()
            relay(self.connection, upstream)


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    if not ALLOWED:
        raise SystemExit("ALLOWLIST is empty")
    with Server(("0.0.0.0", 8080), ProxyHandler) as server:
        server.serve_forever()
