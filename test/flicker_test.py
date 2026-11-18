#!/usr/bin/env python3
"""shotbox.flicker.watch(), and flicker --from, on frames made by hand,
at exact times, from what each of flicker's rules says: no display.
test/flicker_test.py SHOTBOX."""

import json
import os
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shotbox import flicker  # noqa: E402
from shotbox.flicker import watch  # noqa: E402

fails = 0
W, H, T = 64, 32, 16
BLACK, GREEN, WHITE, GRAY = (0, 0, 0), (0, 0x99, 0), (255, 255, 255), (0x80, 0x80, 0x80)


def check(ok, what):
    global fails
    print(("ok    " if ok else "FAIL  ") + what)
    fails += not ok


def frame(back=WHITE, boxes=()):
    """A W x H picture of `back`, each (x, y, w, h, color) of `boxes` on it."""
    data = bytearray(bytes(back) * W * H)
    for x, y, w, h, color in boxes:
        for j in range(y, y + h):
            data[(j * W + x) * 3:(j * W + x + w) * 3] = bytes(color) * w
    return bytes(data)


def lines(dy):
    """Lines of strokes 15 pixels apart on white, scrolled up `dy` pixels:
    text."""
    data = bytearray(bytes(WHITE) * W * H)
    for j in range(H):
        row = (j + dy) % 15
        for i in range(W):
            if 3 <= row <= 8 and (i * 5 + row * row) % 7 < 3:
                data[(j * W + i) * 3:(j * W + i + 1) * 3] = bytes(BLACK)
    return bytes(data)


def strip(color):
    """The tile at 16, 0 in `color`."""
    return frame(boxes=[(16, 0, T, T, color)])


def flips(holds, start=0.0):
    """The strip switching black and green, held `holds` seconds each in
    turn, from `start`: (at, rgb) a frame."""
    out, at = [], start
    for i, hold in enumerate(holds):
        out.append((round(at, 6), strip(GREEN if i % 2 else BLACK)))
        at += hold
    return out


def said(frames, seconds=2.0, **kw):
    found, taken, changed = watch(frames, (W, H), seconds, **kw)
    return [(f["kind"], f["box"], f["changes"], round(f["every"], 4), round(f["at"], 4),
             f["looks"]) for f in found]


# Flicker: a look held no longer than brief (100 ms), changing at least
# times (8): said with its box (whole tiles), how many changes, the mean
# brief hold, and when its first change was.
flicker30 = said(flips([0.03] * 60))
check(flicker30 and flicker30[0][:5] == ("flicker", "16x16+16+0", 59, 0.03, 0.03),
      f"a strip switching every 30 ms: flicker, every 30 ms, its tile ({flicker30})")
check(flicker30 and set(flicker30[0][5]) == {"#000000", "#009900"},
      f"said in its two looks ({flicker30})")

# A picture missed holds one look 60 ms: still brief, so still one run.
# Every is the mean of the brief holds after the first look (the last is
# held to the end of the watch, not brief).
missed = said(flips([0.03] * 20 + [0.06] + [0.03] * 20))
check(missed and missed[0][:4] == ("flicker", "16x16+16+0", 40, round((0.03 * 38 + 0.06) / 39, 4)),
      f"a picture missed: one flicker, its hold among the rest ({missed})")

# Uneven pacing, 20 and 40 ms in turn: every is their mean.
uneven = said(flips([0.02, 0.04] * 20))
check(uneven and uneven[0][:5] == ("flicker", "16x16+16+0", 39, 0.03, 0.02),
      f"uneven pacing: flicker, every 30 ms ({uneven})")

# Fewer changes than times isn't flicker; times is. Neither 2, a flash.
for n, want in ((7, []), (8, ["flicker"])):
    holds = [0.5] + [0.03] * (n - 1) + [0.5]
    got = said(flips(holds), seconds=sum(holds))
    check([k for k, *_ in got] == want, f"{n} changes, with times 8: {want or 'none'} ({got})")

# A flash: A, then B for one picture, then A, A held longer than brief
# either side.
flash = [(0.0, strip(BLACK)), (1.0, strip(GREEN)), (1.03, strip(BLACK))]
got = said(flash)
check(got and got[0][:5] == ("flash", "16x16+16+0", 2, 0.03, 1.0),
      f"a flash of one picture: 30 ms, at 1 s ({got})")
# Two different pictures, three changes: neither flicker nor a flash.
two = [(0.0, strip(BLACK)), (1.0, strip(GREEN)), (1.03, strip(GRAY)), (1.06, strip(BLACK))]
check(said(two) == [], f"a flash of two different pictures: none ({said(two)})")

# A caret's half-second blink is no flicker.
blink = said(flips([0.5] * 4))
check(blink == [], f"a 500 ms blink: none ({blink})")

# Text scrolled half a line a picture, as GTK 4 scrolls by fractions of
# a pixel: rows the same every other picture, but each the other moved.
scroll = [(round(i * 0.03, 6), lines(i % 2 * 7)) for i in range(60)]
got = said(scroll)
check(got == [], f"text scrolled half a line a picture: none ({got})")

# What's ignored isn't watched.
got = said(flips([0.03] * 60), ignore=[(T, T, 16, 0)])
check(got == [], f"the strip ignored: none ({got})")

# How many were taken and kept: a frame the same as the one before is
# dropped, but counted as taken.
dup = flips([0.03] * 4)
dup.insert(2, (0.045, dup[1][1]))
_, taken, changed = watch(dup, (W, H), 1.0)
check((taken, changed) == (5, 4), f"a frame the same as the one before: taken, not kept ({taken}, {changed})")

# The last picture can be taken a little past the watch's end, as one
# started before it ends after it; no other.
late = flips([0.03] * 4)
late.append((2.01, strip(BLACK)))
check(watch(late, (W, H), 2.0)[2] == 5, "the last frame a little past the end: taken")

for case, frames in [
    ("no frames", []),
    ("a frame past the end, then another", [(2.01, strip(BLACK)), (2.02, strip(GREEN))]),
    ("a time not after the one before, which was dropped",
     [(0.0, strip(BLACK)), (1.0, strip(BLACK)), (0.5, strip(GREEN))]),
    ("pixels that aren't bytes", [(0.0, "x" * (W * H * 3))]),
    ("a time below 0", [(-0.1, strip(BLACK))]),
    ("a time not after the one before", [(0.1, strip(BLACK)), (0.1, strip(GREEN))]),
    ("a time that isn't a number", [("0", strip(BLACK))]),
    ("a time that's a bool", [(True, strip(BLACK))]),
    ("a time that isn't finite", [(float("nan"), strip(BLACK))]),
    ("the wrong number of bytes", [(0.0, b"\0" * 10)]),
]:
    try:
        watch(frames, (W, H), 1.0)
        check(False, f"watch(): {case}: no error")
    except ValueError as e:
        check(True, f"watch(): {case}: {e}")
# Pixels as any bytes-like, counted in bytes: a memoryview of 2-byte items.
wide = [(at, memoryview(rgb).cast("H")) for at, rgb in flips([0.03] * 60)]
check(said(wide) == flicker30, "pixels as a memoryview of 2-byte items, counted in bytes")

for case, size, kw in [
    ("a size of none", (0, 5), {}), ("a size that isn't whole", (W + 0.5, H), {}),
    ("a size that's one number", 5, {}),
    ("no seconds", (W, H), {"seconds": 0}), ("a tile of none", (W, H), {"tile": 0}),
    ("a box to ignore as written", (W, H), {"ignore": ["16x16+16+0"]}),
]:
    try:
        watch(flips([0.03] * 2), size, **{"seconds": 1.0, **kw})
        check(False, f"watch(): {case}: no error")
    except ValueError as e:
        check(True, f"watch(): {case}: {e}")

# flicker --from a directory written by hand: what --frames keeps.
sb = sys.argv[1]
tmp = Path(tempfile.mkdtemp())
CONVERT = ["magick"] if subprocess.run(["sh", "-c", "command -v magick"],
                                       capture_output=True).returncode == 0 else ["convert"]


def kept(frames, seconds=2.0, taken=None, manifest=None, size=(W, H)):
    """A directory holding `frames`, (at, rgb), and a frames.json saying
    them, or `manifest` in its place."""
    d = Path(tempfile.mkdtemp(dir=tmp))
    for n, (_, rgb) in enumerate(frames, 1):
        subprocess.run([*CONVERT, "-size", f"{size[0]}x{size[1]}", "-depth", "8", "rgb:-",
                        str(d / f"f{n}.png")], input=rgb, check=True)
    (d / "frames.json").write_text(manifest if manifest is not None else json.dumps(
        {"version": 1, "seconds": seconds, "taken": len(frames) if taken is None else taken,
         "size": list(size), "frames": [{"file": f"f{n}.png", "at": at}
                                        for n, (at, _) in enumerate(frames, 1)]}))
    return d


def cli(d, *args):
    r = subprocess.run([sb, "flicker", "--from", str(d), *args], capture_output=True, text=True,
                       env={"PATH": os.environ["PATH"]})
    return r.returncode, r.stdout.splitlines(), r.stderr


STRIP = flips([0.03] * 60)
# As --frames keeps it: its own PNGs and manifest.
d = Path(tempfile.mkdtemp(dir=tmp))
flicker.keep(d, [(at, zlib.compress(rgb)) for at, rgb in STRIP], (W, H), 2.0, 600)
st, out, err = cli(d)
check((st, out) == (1, ["flicker: 16x16+16+0, 59 changes, every 30 ms, #000000 and #009900, "
                        "from 0.030s", "watched 2 s, 600 pictures, 300 a second, 60 changed"]),
      f"flicker --from: a watch as --frames keeps it ({st}, {out}, {err!r})")
st, out, err = cli(kept(STRIP, taken=600))
check((st, out, err) == (1, ["flicker: 16x16+16+0, 59 changes, every 30 ms, #000000 and #009900, "
                              "from 0.030s", "watched 2 s, 600 pictures, 300 a second, 60 changed"],
                         ""), f"flicker --from: a kept strip flickering ({st}, {out}, {err!r})")
st, out, err = cli(kept(flips([0.5] * 4), taken=4))
check(st == 0 and out == ["watched 2 s, 4 pictures, 2 a second, 4 changed"]
      and "fewer than two to 100 ms" in err and "too few to hold 8 changes" in err,
      f"flicker --from: too few pictures, said ({st}, {out}, {err!r})")
d = kept(STRIP, taken=600)
st, out, err = cli(d, "--save", str(tmp / "sheets"))
check(st == 1 and out[0].endswith(f"shown in {tmp / 'sheets'}/1-flicker-16x16+16+0.png")
      and (tmp / "sheets" / "1-flicker-16x16+16+0.png").exists(),
      f"flicker --from --save: its sheet, with no session ({st}, {out}, {err!r})")
st, out, err = cli(d, "--ignore", "16x16+16+0")
check(st == 0, f"flicker --from --ignore: the strip left out ({st}, {out})")

GOOD = {"version": 1, "seconds": 2.0, "taken": 2, "size": [W, H],
        "frames": [{"file": "f1.png", "at": 0.0}, {"file": "f2.png", "at": 0.03}]}
TWO = flips([0.03] * 2)
for case, kw, said in [
    ("no frames.json", {"manifest": None}, "can't read"),
    ("not JSON", {"manifest": "{"}, "isn't what flicker --frames writes"),
    ("another version", {"manifest": json.dumps(dict(GOOD, version=2))}, "isn't what"),
    ("seconds not finite", {"manifest": json.dumps(GOOD).replace("2.0", "Infinity", 1)}, "isn't what"),
    ("a size that isn't one", {"manifest": json.dumps(dict(GOOD, size=[W, 0]))}, "isn't what"),
    ("fewer taken than frames", {"manifest": json.dumps(dict(GOOD, taken=1))}, "isn't what"),
    ("no frames", {"manifest": json.dumps(dict(GOOD, frames=[]))}, "isn't what"),
    ("a time that's a bool", {"manifest": json.dumps(dict(GOOD, frames=[
        {"file": "f1.png", "at": True}]))}, "isn't what"),
    ("a time too big for a float", {"manifest": json.dumps(dict(GOOD, frames=[
        {"file": "f1.png", "at": 10 ** 400}]))}, "isn't what"),
    ("a picture named as ImageMagick's own", {"manifest": json.dumps(dict(GOOD, frames=[
        {"file": "xc:red", "at": 0.0}]))}, "isn't what"),
    ("a picture that isn't there", {"manifest": json.dumps(dict(GOOD, frames=[
        {"file": "none.png", "at": 0.0}]))}, "isn't a 64x32 picture"),
    ("a picture of another size", {"manifest": json.dumps(dict(GOOD, size=[W, H + 1]))},
     "isn't a 64x33 picture"),
    ("times not in order", {"manifest": json.dumps(dict(GOOD, frames=GOOD["frames"][::-1]))},
     "after the one before"),
]:
    d = kept(TWO, **kw) if kw["manifest"] is not None else kept(TWO)
    if kw["manifest"] is None:
        (d / "frames.json").unlink()
    st, out, err = cli(d)
    check(st == 2 and not out and said in err and "Traceback" not in err,
          f"flicker --from: {case}, said ({st}, {err!r})")

# A manifest that can't be put in place leaves no part of one behind.
d = Path(tempfile.mkdtemp(dir=tmp))
(d / "frames.json").mkdir()
try:
    flicker.keep(d, [(0.0, zlib.compress(strip(BLACK)))], (W, H), 1.0, 1)
    check(False, "a manifest that can't be put in place: no error")
except OSError:
    check(not (d / "frames.json.part").exists(), "a manifest that can't be put in place: no part left")

# --save inside --frames is refused before either is touched past being
# made, so --frames stays empty to try again.
d = Path(tempfile.mkdtemp(dir=tmp))
try:
    flicker.ready([], save=d / "sheets", frames=d)
    check(False, "--save in --frames: no error")
except ValueError as e:
    check(not any(d.iterdir()) and "isn't --frames'" in str(e),
          f"--save in --frames: refused, --frames left empty ({e}, {list(d.iterdir())})")
r = subprocess.run([sb, "flicker", "--from", ""], capture_output=True, text=True,
                   env={"PATH": os.environ["PATH"]})
check(r.returncode == 2 and "can't read" in r.stderr and "session" not in r.stderr,
      f"flicker --from '': read, not a live watch ({r.stderr!r})")
st, out, err = cli(kept(TWO), "--ignore", "big")
check(st == 2 and "what to ignore is WIDTHxHEIGHT+X+Y" in err, f"flicker --from: a bad --ignore ({err!r})")
for flag in (["--window", "w"], ["--window", ""], ["--crop", ""], ["--crop", "1x1+0+0"],
             ["--seconds", "1"], ["--frames", str(tmp / "f")]):
    st, out, err = cli(kept(TWO), *flag)
    check(st == 2 and "takes no --window, --crop, --seconds or --frames" in err,
          f"flicker --from: no {flag[0]} ({err!r})")

sys.exit(bool(fails))
