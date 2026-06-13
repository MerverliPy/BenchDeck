#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import signal
import time
from typing import Any

import pexpect
import pyte


KEYS = {
    "ENTER": "\r",
    "ESC": "\x1b",
    "UP": "\x1b[A",
    "DOWN": "\x1b[B",
    "RIGHT": "\x1b[C",
    "LEFT": "\x1b[D",
    "TAB": "\t",
    "CTRL_C": "\x03",
}


def render(screen: pyte.Screen) -> str:
    return "\n".join(line.rstrip() for line in screen.display).rstrip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec-b64", required=True)
    args = parser.parse_args()
    spec = json.loads(base64.b64decode(args.spec_b64).decode())
    rows = int(spec.get("rows", 24))
    cols = int(spec.get("cols", 80))
    command = str(spec["command"])
    child = pexpect.spawn(
        "/bin/bash",
        ["-lc", command],
        encoding=None,
        dimensions=(rows, cols),
        timeout=0.25,
        env={**os.environ, "TERM": spec.get("term", "xterm-256color")},
    )
    screen = pyte.Screen(cols, rows)
    stream = pyte.Stream(screen)
    raw = bytearray()
    frames: list[dict[str, Any]] = []
    errors: list[str] = []

    def drain(duration: float = 0.15) -> None:
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            try:
                data = child.read_nonblocking(size=65536, timeout=0.05)
            except (pexpect.TIMEOUT, pexpect.EOF):
                if not child.isalive():
                    break
                continue
            raw.extend(data)
            stream.feed(data.decode("utf-8", errors="replace"))

    def frame(label: str) -> None:
        drain()
        frames.append(
            {
                "label": label,
                "rows": screen.lines,
                "cols": screen.columns,
                "screen": render(screen),
                "raw_bytes": len(raw),
            }
        )

    frame("initial")
    for index, action in enumerate(spec.get("actions", []), 1):
        kind = action.get("type")
        label = action.get("label", f"{index}:{kind}")
        if kind == "sleep":
            time.sleep(float(action.get("seconds", 0.2)))
        elif kind == "send":
            child.send(str(action.get("text", "")).encode())
        elif kind == "key":
            key = str(action.get("key", ""))
            if key not in KEYS:
                errors.append(f"unknown key: {key}")
            else:
                child.send(KEYS[key].encode())
        elif kind == "resize":
            rows = int(action["rows"])
            cols = int(action["cols"])
            child.setwinsize(rows, cols)
            screen = pyte.Screen(cols, rows)
            stream = pyte.Stream(screen)
        elif kind == "signal":
            signal_name = str(action.get("signal", "TERM"))
            sig = getattr(signal, "SIG" + signal_name)
            child.kill(sig)
        elif kind == "expect":
            expected = str(action["contains"])
            timeout = float(action.get("timeout", 3.0))
            deadline = time.monotonic() + timeout
            found = False
            while time.monotonic() < deadline:
                drain(0.1)
                if expected in render(screen):
                    found = True
                    break
            if not found:
                errors.append(f"expected screen text not found: {expected!r}")
        else:
            errors.append(f"unknown action type: {kind}")
        frame(label)

    if spec.get("terminate", True) and child.isalive():
        child.terminate(force=True)
    drain()
    frame("final")
    child.close(force=True)
    result = {
        "command": command,
        "rows": rows,
        "cols": cols,
        "actions": spec.get("actions", []),
        "frames": frames,
        "final_screen": render(screen),
        "exit_status": child.exitstatus,
        "signal_status": child.signalstatus,
        "errors": errors,
        "raw_terminal_b64": base64.b64encode(bytes(raw)).decode(),
    }
    print(json.dumps(result))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
