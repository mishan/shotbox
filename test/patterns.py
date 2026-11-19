"""flicker's test patterns, 200x120 each, drawn the same live (test/window.py
TITLE NAME ARGS) and offline (test/flicker_test.py): PATTERNS[NAME](ARGS) is
(tick, draw), `draw(cr, ms)` painting the pattern as it is `ms` whole
milliseconds after it started, and `tick` how often, in ms, it can change.
What it shows is the time's alone, so drawn at the same time live or
offline, it's the same picture."""

import random

W, H = 200, 120
LETTERS = "abcdefghijklmnopqrstuvwxyz-./ "


def flip(args):
    # A square that turns green and black, and back, every MS milliseconds.
    ms_ = int(args[0])
    return ms_, lambda cr, ms: (cr.set_source_rgb(0, 0.6 if ms // ms_ % 2 else 0, 0), cr.paint())


def flash(args):
    # A green square that goes black for MS milliseconds, every second.
    long = int(args[0])

    def draw(cr, ms):
        cr.set_source_rgb(0, 0 if ms >= 1000 and ms % 1000 < long else 0.6, 0)
        cr.paint()
    return _gcd(1000, long), draw


def scene(args):
    # bzflag's strip, as it was: black every other 30 ms, and between, a
    # scene that's moved on everywhere, as a turning tank's view has.
    def draw(cr, ms):
        n = ms // 30
        cr.set_source_rgb(0, 0, 0)
        cr.paint()
        if not n % 2:
            for x in range(0, W, 8):
                for y in range(0, H, 8):
                    v = ((x * 7 + y * 13 + n * 29) % 97) / 97
                    cr.set_source_rgb(0.1 * v, 0.4 + 0.5 * v, 0.1)
                    cr.rectangle(x, y, 8, 8)
                    cr.fill()
    return 30, draw


def band(args, noisy=False):
    # bzflag's strip as narrow as it was: WIDTH (3) columns at a tile's
    # edge, black every other 30 ms, and between, a scene that's moved on,
    # dimmer by DARK; text that doesn't change beside it. noisy: the whole
    # window, its black a dark gray with noise in it, as an uncleared
    # buffer's might be.
    wide = int(args[0]) if args and not noisy else 3
    dim = float(args[1]) if len(args) > 1 else 1.0

    def draw(cr, ms):
        n = ms // 30
        black = n % 2
        cr.set_source_rgb(0.95, 0.95, 0.95)
        cr.paint()
        cr.set_source_rgb(0.1, 0.1, 0.1)
        for line in range(8):
            cr.move_to(4, 14 + line * 14)
            cr.show_text("still text, beside the band")
        if noisy:
            for x in range(0, W, 4):
                for y in range(0, H, 4):
                    v = ((x * 7 + y * 13 + n * 29) % 97) / 97
                    if black:
                        g = 0.12 + 0.04 * (((x * 31 + y * 17 + n * 53) % 9) - 4) / 4
                        cr.set_source_rgb(g, g, g)
                    else:
                        cr.set_source_rgb(0.1 * v, 0.4 + 0.5 * v, 0.1)
                    cr.rectangle(x, y, 4, 4)
                    cr.fill()
            return
        for y in range(0, H, 4):
            v = ((y * 13 + n * 29) % 97) / 97
            cr.set_source_rgb(*((0, 0, 0) if black else
                                (0.1 * v * dim, (0.4 + 0.5 * v) * dim, 0.1 * dim)))
            cr.rectangle(192 - wide, y, wide, 4)
            cr.fill()
    return 30, draw


def panel(args):
    # A gray panel with a word in it, white for 40 ms every second, beside
    # a caret that blinks every half second and a spinner that turns: a
    # flash, with what changes beside it something else.
    def draw(cr, ms):
        n = ms // 30
        cr.set_source_rgb(0.5, 0.5, 0.5)
        cr.paint()
        if ms >= 1000 and ms % 1000 < 40:
            cr.set_source_rgb(1, 1, 1)
        else:
            cr.set_source_rgb(0.3, 0.3, 0.3)
        cr.rectangle(32, 32, 64, 64)
        cr.fill()
        cr.set_source_rgb(0, 0, 0)
        cr.move_to(36, 46)
        cr.show_text("Hi")
        if n // 17 % 2:
            cr.rectangle(98, 40, 2, 14)
            cr.fill()
        cr.arc(124, 64, 8, n * 0.5, n * 0.5 + 4)
        cr.stroke()
    return 10, draw


def text(args):
    # A terminal's listing scrolling a line every 30 ms, as winterm's
    # `ls -lR` does: lines of other text, long and short and empty, over
    # a plain background, so a tile goes blank and back to text that
    # isn't the text it had.
    def draw(cr, ms):
        n = ms // 30
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.paint()
        cr.set_source_rgb(0, 0, 0.44)
        for line in range(9):
            r = random.Random(n + line)
            cr.move_to(4, 12 + line * 14)
            cr.show_text("".join(r.choice(LETTERS) for _ in range(r.choice((0, 3, 8, 20, 32)))))
    return 30, draw


def sharp(cr):
    import cairo
    options = cairo.FontOptions()
    options.set_antialias(cairo.ANTIALIAS_NONE)
    cr.set_font_options(options)


def pages(args):
    # A terminal jump-scrolling, as winterm's `ls -lR` does: a page of new
    # lines, long and short, in a font not smoothed, every other 40 ms, a
    # blank between.
    def draw(cr, ms):
        n = ms // 40
        sharp(cr)
        cr.set_source_rgb(0, 0, 0.44)
        cr.paint()
        cr.set_source_rgb(0.9, 0.9, 0.9)
        for line in range(7 if n % 2 else 0):
            r = random.Random(n * 7 + line)
            cr.move_to(4, 12 + line * 14)
            cr.show_text("".join(r.choice(LETTERS) for _ in range(r.choice((0, 3, 8, 20, 32)))))
    return 40, draw


def redraw(args):
    # A terminal's page of text held 200 ms, then drawn anew, a blank
    # between for 40 ms, its green caret gone with it.
    def draw(cr, ms):
        n = ms // 40
        sharp(cr)
        cr.set_source_rgb(0, 0, 0.44)
        cr.paint()
        if n % 6 == 5:
            return
        cr.set_source_rgb(0.9, 0.9, 0.9)
        r = random.Random(n // 6)
        for line in range(7):
            cr.move_to(4, 12 + line * 14)
            cr.show_text("".join(r.choice(LETTERS) for _ in range(r.choice((0, 3, 8, 20, 32)))))
        cr.set_source_rgb(0, 1, 0)
        cr.rectangle(4, 102, 8, 12)
        cr.fill()
    return 40, draw


def stair(args):
    # A line a pixel high on a tile's last row, above a wall's edge, part
    # of it a row lower for 30 ms once a second, as an aliased line's step
    # in a turning view.
    def draw(cr, ms):
        cr.set_source_rgb(0, 0.3, 0)
        cr.paint()
        cr.set_source_rgb(0.85, 0.45, 0.45)
        cr.rectangle(0, 70, W, 3)
        cr.fill()
        cr.set_source_rgb(0.67, 0.85, 0)
        cr.rectangle(100, 63, 100, 1)
        cr.rectangle(0, 64 if ms // 30 % 33 == 0 else 63, 100, 1)
        cr.fill()
    return 30, draw


def poles(args):
    # Two yellow poles alike on a horizon, as bzflag's are while the tank
    # turns, a step of 8 a frame toward each other from either side,
    # crossing, and out the other.
    def draw(cr, ms):
        n = ms // 30
        cr.set_source_rgb(0.4, 0.6, 0.9)
        cr.paint()
        cr.set_source_rgb(0, 0.4, 0)
        cr.rectangle(0, 60, W, 60)
        cr.fill()
        cr.set_source_rgb(0.9, 0.9, 0)
        for x in (n % 30 * 8 - 16, 208 - n % 30 * 8):
            cr.rectangle(x, 20, 2, 40)
            cr.fill()
    return 30, draw


def line(args):
    # A line a pixel wide, not smoothed, as bzflag's ground lines while the
    # tank turns: drifting, and a little back and on each frame, so its
    # steps move a few pixels along it, and back.
    def draw(cr, ms):
        import cairo
        n = ms // 30
        cr.set_antialias(cairo.ANTIALIAS_NONE)
        cr.set_source_rgb(0, 0.3, 0)
        cr.paint()
        cr.set_source_rgb(0, 0.83, 0.67)
        cr.set_line_width(1)
        y = 58 + 0.02 * n + (0.25 if n % 2 else -0.25)
        cr.move_to(0, y)
        cr.line_to(W, y + 10)
        cr.stroke()
    return 30, draw


def passer(args):
    # bzflag's strip as it was at the screen's edge: six columns black and
    # green every other frame of 30 ms, in a tile with two of the scene's
    # beside it and the page's background after, through ten columns of
    # which something passes for a third of each second.
    def draw(cr, ms):
        n, t = ms // 30, ms / 1000
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.paint()
        cr.set_source_rgb(0, 0.4, 0)
        cr.rectangle(0, 0, 178, H)
        cr.fill()
        if t % 1 < 0.33:
            cr.set_source_rgb(1, 1, 1)
            cr.rectangle(166, t % 1 * 400 - 12, 26, 12)
            cr.fill()
        cr.set_source_rgb(*((0, 0, 0) if n % 2 else (0.53, 0.79, 0)))
        cr.rectangle(178, 0, 6, H)
        cr.fill()
    return 30, draw


def icon(args):
    # An X of strokes two wide flashing white for 40 ms once a second on
    # gray.
    def draw(cr, ms):
        cr.set_source_rgb(0.3, 0.3, 0.3)
        cr.paint()
        if ms // 10 % 100 < 4:
            cr.set_source_rgb(1, 1, 1)
            for i in range(14):
                cr.rectangle(65 + i, 49 + i, 2, 1)
                cr.rectangle(78 - i, 49 + i, 2, 1)
            cr.fill()
    return 10, draw


def dropout(args):
    # A line a pixel high, light on dark ground under a wall, missing for
    # 30 ms once a second, as depth-fighting drops one in a turning view.
    def draw(cr, ms):
        cr.set_source_rgb(0, 0.3, 0)
        cr.paint()
        cr.set_source_rgb(0.85, 0.45, 0.45)
        cr.rectangle(0, 20, W, 41)
        cr.fill()
        if ms // 10 % 100 > 2:
            cr.set_source_rgb(0.67, 0.85, 0)
            cr.rectangle(0, 62, W, 1)
            cr.fill()
    return 10, draw


def busy(args):
    # bzflag's strip, six columns black and green every other frame of
    # 30 ms, in a tile with two of a scene moving on every frame, never
    # black, ground lines at a wall's foot, and the page's background.
    def draw(cr, ms):
        n = ms // 30
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.paint()
        for x in range(0, 178, 2):
            for y in range(0, H, 4):
                v = ((x * 7 + y * 13 + n * 29) % 97) / 97
                cr.set_source_rgb(0.1 * v, 0.4 + 0.5 * v, 0.1)
                cr.rectangle(x, y, 2, 4)
                cr.fill()
        cr.set_source_rgb(*((0, 0, 0) if n % 2 else (0.53, 0.79, 0)))
        cr.rectangle(178, 0, 6, H)
        cr.fill()
    return 30, draw


def edge(args):
    # A strip six columns wide, partway into a tile, black and green every
    # other 30 ms over plain gray, and a square in a corner turning red and
    # blue every 150 ms, so other pictures change too.
    def draw(cr, ms):
        cr.set_source_rgb(0.7, 0.7, 0.7)
        cr.paint()
        cr.set_source_rgb(*((0, 0, 0) if ms // 30 % 2 else (0.2, 0.6, 0.2)))
        cr.rectangle(180, 0, 6, H)
        cr.fill()
        cr.set_source_rgb(*((1, 0, 0) if ms // 150 % 2 else (0, 0, 1)))
        cr.rectangle(8, 8, 10, 10)
        cr.fill()
    return 30, draw


def gray(args):
    # The whole window two grays 6% apart, every other 30 ms.
    return 30, lambda cr, ms: (cr.set_source_rgb(*[0.5 if ms // 30 % 2 else 0.56] * 3),
                               cr.paint())


def grating(args):
    # Black and white stripes 6 pixels wide swapping every 30 ms, a white
    # rule every 10 rows: each look is the other moved a stripe across,
    # which isn't scrolling.
    def draw(cr, ms):
        cr.set_source_rgb(1, 1, 1)
        cr.paint()
        cr.set_source_rgb(0, 0, 0)
        for x in range(ms // 30 % 2 * 6, W, 12):
            for y in range(0, H, 10):
                cr.rectangle(x, y + 1, 6, 9)
        cr.fill()
    return 30, draw


def gradient(args):
    # Two faces 8% apart, the edge between them sweeping past unevenly,
    # forward and back a little each frame, as a turning view's do.
    def draw(cr, ms):
        n = ms // 30
        cr.set_source_rgb(0.84, 0.44, 0.44)
        cr.paint()
        cr.set_source_rgb(0.76, 0.44, 0.44)
        cr.rectangle(0, 0, n * 3 % 240 + (6 if n % 2 else -6), H)
        cr.fill()
    return 30, draw


def skip(args):
    # Motion faster than the tiles: a red square of 12, between pixels so
    # its edges are blended, a step of 24 a frame along a row, and gone a
    # frame at the end, so that last, at the window's edge, a column of it
    # is in a tile alone, and where it was before isn't beside that.
    def draw(cr, ms):
        n = ms // 30
        cr.set_source_rgb(1, 1, 1)
        cr.paint()
        if n % 9 < 8:
            cr.set_source_rgb(0.8, 0, 0)
            cr.rectangle(12.5 + 24 * (n % 9), 50, 12, 12)
            cr.fill()
    return 30, draw


def strip(args):
    # As bzflag's strip: black every other 30 ms, and between, a green
    # scene with a square crossing it, a little further on each time.
    def draw(cr, ms):
        black = ms // 30 % 2
        cr.set_source_rgb(0, 0, 0) if black else cr.set_source_rgb(0, 0.6, 0)
        cr.paint()
        if not black:
            cr.set_source_rgb(1, 1, 1)
            cr.rectangle(ms / 1000 * 100 % 216 - 16, 50, 16, 16)
            cr.fill()
    return 30, draw


def motion(kind):
    # Motion, which is neither: a black square crossing white at 300
    # pixels a second (move), or a red one of 12 at 1200, through a tile
    # in a picture or two (fast); or lines of text scrolling up at 200,
    # 14 pixels apart, by whole pixels as a terminal or a GTK 3 list is
    # (scroll), or 40 apart, smoothly, with white between (spaced); or
    # 15 apart, by half a line a frame, as GTK 4 scrolls by fractions of a
    # pixel: rows the same every other frame, never shifted whole (smooth).
    tick = 30 if kind == "smooth" else 16

    def draw(cr, ms):
        t = ms / 1000
        cr.set_source_rgb(1, 1, 1)
        cr.paint()
        cr.set_source_rgb(0, 0, 0)
        if kind in ("move", "fast"):
            if kind == "fast":
                cr.set_source_rgb(0.8, 0, 0)
            side, speed = (12, 1200) if kind == "fast" else (16, 300)
            cr.rectangle(t * speed % 216 - 16, 50, side, side)
            cr.fill()
            return
        gap = {"scroll": 14, "smooth": 15}.get(kind, 40)
        dy = {"scroll": int(t * 200), "smooth": ms // tick * 7.5}.get(kind, t * 200)
        for row in range(H // gap + 2):
            cr.move_to(4, 14 + row * gap - dy % gap)
            cr.show_text(f"line {row + int(dy / gap)}: the quick brown fox")
    return lambda args: (tick, draw)


def _gcd(a, b):
    while b:
        a, b = b, a % b
    return a


PATTERNS = {"flip": flip, "flash": flash, "scene": scene, "band": band,
            "noisy": lambda args: band(args, noisy=True), "panel": panel, "text": text,
            "pages": pages, "redraw": redraw, "stair": stair, "poles": poles, "line": line,
            "passer": passer, "icon": icon, "dropout": dropout, "busy": busy, "edge": edge,
            "gray": gray, "grating": grating, "gradient": gradient, "skip": skip,
            "strip": strip, **{k: motion(k) for k in ("move", "scroll", "smooth", "spaced", "fast")}}
