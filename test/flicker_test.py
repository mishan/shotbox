#!/usr/bin/env python3
"""shotbox.flicker.watch() on frames made by hand, at exact times, from
what each of flicker's rules says: no display. test/flicker_test.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
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

for case, frames in [
    ("no frames", []),
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

sys.exit(bool(fails))
