"""Finding windows and taking pictures of them, on the session's display.

Uses the X tools every distro has (xwininfo, ImageMagick's import and
convert) rather than a Python X binding, so there's nothing to install.
"""

import re
import socket
import subprocess
from pathlib import Path

TREE_LINE = re.compile(r'^\s*(0x[0-9a-f]+) "(.*)":.*?(\d+)x(\d+)\+-?\d+\+-?\d+\s+\+(-?\d+)\+(-?\d+)\s*$')


def windows(env):
    """Every named window: (id, name, width, height, x, y), x and y absolute."""
    out = subprocess.run(["xwininfo", "-root", "-tree"], env=env,
                         capture_output=True, text=True).stdout
    found = []
    for line in out.splitlines():
        m = TREE_LINE.match(line)
        if m:
            wid, name, w, h, x, y = m.groups()
            found.append((wid, name, int(w), int(h), int(x), int(y)))
    return found


def viewable(env, wid):
    out = subprocess.run(["xwininfo", "-id", wid], env=env,
                         capture_output=True, text=True).stdout
    return "Map State: IsViewable" in out


def find_window(env, name):
    """The biggest viewable window whose name matches `name` (a regex, matched
    in full), or None. Biggest, because toolkits often name a 1x1 helper
    window after the app too."""
    pattern = re.compile(name)
    hits = [w for w in windows(env) if pattern.fullmatch(w[1]) and w[2] > 1 and w[3] > 1]
    hits = [w for w in hits if viewable(env, w[0])]
    return max(hits, key=lambda w: w[2] * w[3]) if hits else None


def port_open(port, host="127.0.0.1"):
    with socket.socket() as s:
        s.settimeout(0.2)
        return s.connect_ex((host, port)) == 0


# PNGs that come out the same byte for byte: no metadata, no timestamps.
QUIET_PNG = ["-strip", "-define", "png:exclude-chunks=date,time"]


def capture(env, out, window=None, crop=None):
    """Screenshot the whole display, or one window, to `out` (a PNG), then
    crop it (ImageMagick geometry, WxH+X+Y, relative to what was taken)."""
    target = window[0] if window else "root"
    cmd = ["import", "-window", target]
    if crop:
        cmd += ["-crop", crop, "+repage"]
    cmd += QUIET_PNG + [str(out)]
    subprocess.run(cmd, env=env, check=True)
    return Path(out)


def montage(images, out, across=True):
    """Put images side by side (or one above another)."""
    subprocess.run(["convert", *map(str, images), "+append" if across else "-append",
                    *QUIET_PNG, str(out)], check=True)
    return Path(out)


def size_of(path):
    out = subprocess.run(["identify", "-format", "%wx%h", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return out.strip()


def compare(a, b, diff=None, fuzz="0%"):
    """How many pixels differ between two images (0 means the same): pixels
    where any channel differs by more than `fuzz`. With `diff`, also writes
    an image with the differences marked in red."""
    if size_of(a) != size_of(b):
        raise ValueError(f"not the same size: {size_of(a)} and {size_of(b)}")
    # The per-pixel difference, its largest channel, then on or off. Counted
    # by hand: compare's own AE metric weighs pixels differently from one
    # ImageMagick release to the next.
    out = subprocess.run(
        ["convert", str(a), str(b), "-alpha", "off", "-compose", "difference",
         "-composite", "-separate", "-evaluate-sequence", "max",
         "-threshold", fuzz, "-format", "%[fx:round(mean*w*h)]", "info:"],
        capture_output=True, text=True, check=True).stdout
    if diff:
        subprocess.run(["compare", "-fuzz", fuzz, "-define", "png:exclude-chunks=date,time",
                        str(a), str(b), str(diff)], capture_output=True)
    return int(out.strip())
