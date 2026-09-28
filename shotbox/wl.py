"""Finding windows and taking pictures of them, in a Wayland session under
sway: what x.py does for X11.

Windows come from sway's IPC socket ($SWAYSOCK), which speaks JSON over a
Unix socket, and pictures from grim, which speaks wlr-screencopy. Nothing
to install beyond those two.
"""

import hashlib
import json
import re
import socket
import struct
import subprocess
from pathlib import Path

from .x import QUIET_PNG

MAGIC = b"i3-ipc"
RUN_COMMAND, GET_OUTPUTS, GET_TREE, GET_VERSION = 0, 3, 4, 7


def ipc(env, kind, payload=""):
    """Ask sway one thing over its IPC socket; the reply, decoded."""
    data = payload.encode()
    with socket.socket(socket.AF_UNIX) as s:
        s.settimeout(5)
        s.connect(env["SWAYSOCK"])
        s.sendall(MAGIC + struct.pack("<II", len(data), kind) + data)
        head = _read(s, len(MAGIC) + 8)
        size, _ = struct.unpack("<II", head[len(MAGIC):])
        return json.loads(_read(s, size))


def _read(s, n):
    buf = b""
    while len(buf) < n:
        got = s.recv(n - len(buf))
        if not got:
            raise OSError("sway closed its IPC socket")
        buf += got
    return buf


def windows(env):
    """Every window, Wayland and X alike: (id, name, width, height, x, y,
    visible), x and y absolute."""
    found = []

    def walk(node):
        if node.get("pid") is not None:
            r = node["rect"]
            found.append((node["id"], node.get("name") or "", r["width"], r["height"],
                          r["x"], r["y"], node.get("visible", False)))
        for child in node.get("nodes", []) + node.get("floating_nodes", []):
            walk(child)

    walk(ipc(env, GET_TREE))
    return found


def find_window(env, name):
    """The biggest visible window whose name (its title) matches `name`, a
    regex matched in full, or None. The same rule as x.find_window, less
    the 1x1 helpers, which Wayland doesn't have."""
    pattern = re.compile(name)
    hits = [w[:6] for w in windows(env) if w[6] and pattern.fullmatch(w[1])]
    return max(hits, key=lambda w: w[2] * w[3]) if hits else None


def _region(window):
    return ["-g", f"{window[4]},{window[5]} {window[2]}x{window[3]}"] if window else []


def capture(env, out, window=None, crop=None):
    """Screenshot the whole output, or one window, to `out` (a PNG), then
    crop it (WxH+X+Y, relative to what was taken). grim takes it and
    ImageMagick writes it, so the PNG has no timestamps."""
    shot = subprocess.run(["grim", *_region(window), "-t", "ppm", "-"], env=env,
                          capture_output=True, check=True).stdout
    cmd = ["convert", "ppm:-"]
    if crop:
        cmd += ["-crop", crop, "+repage"]
    subprocess.run(cmd + QUIET_PNG + [str(out)], input=shot, check=True)
    return Path(out)


def fingerprint(env, window=None):
    """A digest of what's on the output, or in one window, or None if it
    couldn't be taken."""
    r = subprocess.run(["grim", *_region(window), "-t", "ppm", "-"], env=env,
                       capture_output=True)
    if r.returncode or not r.stdout:
        return None
    return hashlib.sha256(r.stdout).digest()
