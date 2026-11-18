"""Flicker in a run of pictures: a part of the screen that keeps switching
between two looks, faster than anything meant to (a buffer drawn where it
shouldn't be, a strip of the wrong frame), or that flashes another look
once and comes back.

The screen is cut into tiles, and a tile's look is its mean color, so a
look that's the same in color but not pixel for pixel (a game's frame
behind a strip of it) is the same look. Each tile's looks over time make
states, a look and how long it held: in time, not pictures, since the
program draws at its own rate. A tile whose states go A, B, A, B... each
held no longer than `brief`, `times` changes or more, flickers; one that
goes A, B, A once, B as brief, flashed. A caret that blinks holds each
look half a second, and an animation doesn't come back to a look so
quickly, so neither is either.

Mean colors find what might be, a quarter of fuzz a change, so a band a
pixel wide is seen; the tile's pixels decide. Flicker keeps its place:
the pixels most changes change are most of what most of them do, and no
fewer than a line across the tile, which text, or a line's steps,
moving through aren't. Its looks come back as the same pictures most
times, nearer than A is to B, A as A and B as B, which anything moving
through doesn't; or one of them does, one color each time where they
differ, a band drawn black between frames of a scene that moves on, not
one color, or a shape of it, as pages of text over their background
aren't. A flash is to one color where it differs, a shape of it, from a
picture that held still and back to it, A held longer than `brief`
either side, not cut short by the start or end of watching; and not a
thin line gone to the color beside it; and the tiles round it don't
change about then, as they do when something moves through. A look
that's in the picture before or after, up or down the screen, the same
pixel for pixel, is text scrolling, and neither; and so is a flicker's
look that's near it moved a little, as text scrolled by fractions of a
pixel (GTK 4's or kinetic scrolling, a browser at a fractional scale)
is, drawn anew each picture, never the same.
"""

import functools
import math
import json
import operator
import re
import subprocess
import tempfile
import zlib
from collections import Counter
from pathlib import Path

from . import x
from .x import differ


def means(pixels, width, height, tile, before=None, then=None):
    """Each tile's mean color, (r, g, b), of RGB `pixels`: every row, so a
    band a row high is in it. A tile as it was in the picture `before`,
    whose means were `then`, keeps its mean: most of a screen holds still."""
    out = []
    for ty in range(0, height, tile):
        band = slice(ty * width * 3, min(height, ty + tile) * width * 3)
        if before is not None and pixels[band] == before[band]:
            out += then[len(out):len(out) + -(-width // tile)]
            continue
        for tx in range(0, width, tile):
            rows = [(y * width + tx) * 3 for y in range(ty, min(height, ty + tile))]
            span = (min(width, tx + tile) - tx) * 3
            if before is not None and all(pixels[r:r + span] == before[r:r + span] for r in rows):
                out.append(then[len(out)])
                continue
            r = g = b = 0
            for at in rows:
                part = pixels[at:at + span]
                r, g, b = r + sum(part[0::3]), g + sum(part[1::3]), b + sum(part[2::3])
            n = len(rows) * span // 3
            out.append((r / n, g / n, b / n))
    return out


def states(times, looks, end, fuzz):
    """[[look, start, seconds held, picture]]: `looks` at `times`, a look
    held while the next is within `fuzz` (of 255) of it in every channel,
    and the picture, by its place in `looks`, it first showed in."""
    out = []
    for k, (t, look) in enumerate(zip(times, looks)):
        if out and all(abs(a - b) <= fuzz for a, b in zip(out[-1][0], look)):
            continue
        out.append([look, t, None, k])
    for here, there in zip(out, out[1:]):
        here[2] = there[1] - here[1]
    if out:
        out[-1][2] = end - out[-1][1]
    return out


@functools.lru_cache(maxsize=1 << 14)
def changed(a, b, fuzz):
    """The pixels, by offset, where two tiles' RGB pixels differ by more
    than `fuzz` percent in a channel: kept, as a strip's two looks are
    told apart again each time they come back."""
    limit = fuzz * 2.55
    return frozenset(k for k in range(0, len(a), 3)
                     if abs(a[k] - b[k]) > limit or abs(a[k + 1] - b[k + 1]) > limit
                     or abs(a[k + 2] - b[k + 2]) > limit)


def alike(a, b, fuzz):
    """Whether two tiles' RGB pixels are the same picture: no more than one
    in fifty differing by more than twice `fuzz` percent, which noise in a
    black that isn't clean is within. Text scrolling past differs by more,
    in its strokes."""
    most = len(a) // 150
    return differ((len(a) // 3, 1, a), (len(b) // 3, 1, b), 2 * fuzz, most) <= most


def moved(here, picture, width, x, y, wide, reach, fuzz):
    """Whether a tile's RGB pixels `here`, `wide` across, at `x`, `y` in a
    `picture` `width` across, are that picture's moved up or down by up to
    `reach`, near enough, where it isn't the same picture: text scrolled
    by fractions of a pixel, drawn anew each time, is no copy. Block
    matching, as a video encoder's motion search: the shift whose rows'
    sums of green are nearest, if no more than half as far as in place,
    and its pixels, or half a pixel either side, too. Not across: stripes
    swapping are each other moved across, and that's flicker."""
    high, w3, row = len(here) // 3 // wide, wide * 3, width * 3

    def box(dy):
        at = (y + dy) * row + x * 3
        return b"".join(picture[a:a + w3] for a in range(at, at + high * row, row))

    def apart(a, b):
        return sum(map(abs, map(operator.sub, a, b)))

    still = box(0)
    if alike(here, still, fuzz):
        return False
    top = max(0, y - reach)
    mine = [sum(here[a + 1:a + w3:3]) for a in range(0, len(here), w3)]
    theirs = [sum(picture[a + 1:a + w3:3]) for a in
              range(top * row + x * 3, min(len(picture) // row, y + high + reach) * row, row)]
    far = {d: apart(mine, theirs[d - top + y:d - top + y + high])
           for d in range(top - y, top - y + len(theirs) - high + 1)}
    d = min((d for d in far if d), key=far.get, default=0)
    if not d or 2 * far[d] > far[0]:
        return False
    at = box(d)
    return any(2 * apart(here, t) <= apart(here, still) for t in [at] + [
        bytes(map(lambda p, q: (p + q + 1) // 2, at, box(e))) for e in (d - 1, d + 1) if e in far])


def recur(shown, fuzz, where, line):
    """Whether each look, A and B, of a tile's pictures `shown` a state
    after another, comes back as the same picture most times, as `alike`
    says, but for pixels of `where`, where it keeps switching, that don't
    come back most times: a scene moving on in a column or two beside a
    strip. Those that do must be most of `where`, and a `line` or more.
    Something passing through the rest of the tile spoils a few times."""
    allow, out = len(shown[0]) // 150, []
    for side in (0, 1):
        offs = [changed(shown[m], shown[m + 2], 2 * fuzz) for m in range(side, len(shown) - 2, 2)]
        # A pair the same but for less than half of `where` differs in no more.
        if 2 * sum(len(off) <= allow + len(where) // 2 for off in offs) <= len(offs):
            out.append(False)
            continue
        gone = Counter(k for off in offs for k in off & where)
        kept = {k for k in where if 2 * gone[k] <= len(offs)}
        same = sum(len(off - where) <= allow and len(off & kept) <= allow for off in offs)
        out.append(2 * same > len(offs) and 2 * len(kept) > len(where) and len(kept) >= line)
    return out


def plain(pixels, where, fuzz):
    """Whether a tile's pixels at `where`, where it differs from another
    look, are all near one color: a flash to black, or a band of the tile
    drawn black every other frame, not something passing through it."""
    limit = fuzz * 2.55
    return all(max(pixels[k + c] for k in where) - min(pixels[k + c] for k in where) <= 2 * limit
               for c in range(3))


def filled(where, wide, high):
    """Whether pixels, by offset in a tile `wide` by `high`, are a shape,
    not strokes scattered as text's are: filling at least half the box
    round them, or one piece, a line, a ring, an X, more than half across
    the tile both ways."""
    at = {(k // 3 % wide, k // 3 // wide) for k in where}
    xs, ys = [x for x, _ in at], [y for _, y in at]
    w, h = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
    if 2 * len(at) >= w * h:
        return True
    if 2 * w <= wide or 2 * h <= high:
        return False
    todo, piece = [min(at)], set()
    while todo:
        x, y = todo.pop()
        if (x, y) not in piece:
            piece.add((x, y))
            todo += [(x + i, y + j) for i in (-1, 0, 1) for j in (-1, 0, 1) if (x + i, y + j) in at]
    return len(piece) == len(at)


def dropped(before, after, where, wide, fuzz):
    """Whether a tile's pixels at `where`, a line no more than two wide
    that stood apart from what was either side of it in `before`, took
    the color of one side in `after`: something thin missing for a
    picture, as a line at a wall's foot in a turning view is, not a part
    of the screen drawn over, nor the edge of a region grown."""
    xs, ys = [k // 3 % wide for k in where], [k // 3 // wide for k in where]
    if min(max(xs) - min(xs), max(ys) - min(ys)) > 1:
        return False

    def side(dx, dy):
        return {3 * ((y + dy) * wide + x + dx) for x, y in zip(xs, ys)
                if 0 <= x + dx < wide and 0 <= (y + dy) * wide * 3 < len(after)} - where

    def near(p, at, q, there):
        return max(abs(x - y) for x, y in
                   zip(colors(p, p, at)[0], colors(q, q, there)[0])) <= 2 * fuzz * 2.55

    for dx, dy in ((0, 1), (1, 0), (0, 2), (2, 0)):
        for one, other in ((side(dx, dy), side(-dx, -dy)), (side(-dx, -dy), side(dx, dy))):
            if (one and other and near(after, where, after, one)
                    and not near(before, where, before, one)
                    and not near(before, where, before, other)):
                return True
    return False


def colors(a, b, where):
    """Two tiles' looks, as the mean color of each at `where`, where they
    differ: a narrow band's own colors, not the tile's, most of which held
    still."""
    return tuple(tuple(sum(p[k + c] for k in where) / len(where) for c in range(3))
                 for p in (a, b))


def runs(held, brief):
    """Each stretch of brief states in a tile's, with the look either side:
    [A, B, A, B...], as states."""
    i = 1
    while i < len(held):
        if held[i][2] > brief:
            i += 1
            continue
        k = i
        while k < len(held) and held[k][2] <= brief:
            k += 1
        yield held[i - 1:k + 1]
        i = k


def needs(held, brief):
    """The pictures, by place, `find` looks at a tile in: each state's
    first, and the last of a flash's first look."""
    return {k for seq in runs(held, brief) for k in [s[3] for s in seq] + [seq[1][3] - 1]}


def find(held, brief, times, fuzz, pixels, wide):
    """In one tile's states, its longest flicker, as (start, changes, mean
    seconds a brief state, look A, look B, the pictures it changed in), or
    else a flash, as (start, seconds, look, then look, picture, the
    picture it came back in), each, or None and []: see the module's
    docstring.
    `pixels(k)` is the tile's pixels in picture `k`, of those `needs` says,
    which decide what the mean colors found: brief states one after
    another. A flash is said with its picture too, to tell it from motion.
    `wide` is the tile's width in pixels."""
    best, flashes = None, []
    for seq in runs(held, brief):
        changes = len(seq) - 1
        if changes < times and changes != 2:
            continue
        shown = [pixels(st[3]) for st in seq]
        a, b = shown[0], shown[1]
        high = len(a) // 3 // wide
        # Neither look coming back, even with half the tile moving on, is
        # something moving, every picture new: no need to count its pixels.
        most = len(a) // 150 + len(a) // 6
        if not any(2 * sum(len(changed(shown[m], shown[m + 2], 2 * fuzz)) <= most for m in pairs)
                   > len(pairs) for pairs in (range(0, changes - 1, 2), range(1, changes - 1, 2))):
            continue
        # Where it keeps switching: the pixels most changes change, each by
        # as much as a new look's mean moves, which must be most of what
        # most of them change, and no fewer than a line across the tile.
        # Something passing through the rest of the tile is left out; text
        # or a line moving through changes other pixels each time, and a
        # line's steps moving, a few.
        each = Counter(changed(p, q, fuzz / 4) for p, q in zip(shown, shown[1:]))
        often = Counter()
        for c, m in each.items():
            often.update(dict.fromkeys(c, m))
        where = {k for k, m in often.items() if 2 * m > changes}
        if len(where) < min(wide, high) or 2 * sum(m for c, m in each.items()
                                        if 2 * len(where & c) >= len(c)) <= changes:
            continue
        looks = colors(a, b, where)
        # The same picture is nearer than the two looks are: two faces of
        # a scene a little apart, an edge between them sweeping past,
        # would come back at any wider.
        near = min(fuzz, max(abs(x - y) for x, y in zip(*looks)) / 2.55 / 4)
        back = recur(shown, near, where, min(wide, high))
        # One color where the first two looks differ there, as a page of
        # text, missing a stroke the others have, isn't at all of it.
        first = where & changed(a, b, fuzz / 4) or where
        plains = [plain(a, first, fuzz), plain(b, first, fuzz)]
        # Both looks coming back as the same pictures; or one, a color all over
        # each time, as a frame drawn black between frames of a scene that
        # moves on, which isn't one color, or is a shape of it, as a wall is and
        # pages of text over their background aren't. The white between lines
        # of text scrolling smoothly past comes back, but as every other look.
        if changes >= times and (all(back) or any(
                r and all(plain(s, first, fuzz) for s in shown[side::2])
                and (not q or filled(first, wide, high))
                for side, r, q in zip((0, 1), back, plains[::-1]))):
            brief_ones = [s[2] for s in seq[1:] if s[2] <= brief]
            run = (seq[1][1], changes, sum(brief_ones) / len(brief_ones), *looks,
                   [st[3] for st in seq[1:]])
            best = run if best is None or changes > best[1] else best
        # A flash: from a picture that held still, to a color, and back:
        # what's moving holds no picture still, though it come back. Held,
        # longer than brief, as only the first and last states, cut short
        # by watching, may not be: motion before or after went unseen. And
        # it's a shape gone to that color, a band, a line, an icon, not
        # the scattered strokes of text drawn once, nor a line gone.
        elif (changes == 2 and seq[0][2] > brief < seq[2][2] and back[0] and plains[1]
              and alike(a, pixels(seq[1][3] - 1), fuzz) and filled(where, wide, high)
              and not dropped(a, b, where, wide, fuzz)):
            flashes.append((seq[1][1], seq[1][2], looks[1], looks[0], seq[1][3], seq[2][3]))
    return best, ([] if best else flashes)


def boxes(tiles, across, tile):
    """Tiles, by index, that touch, merged: [(x, y, width, height, [tiles])]."""
    left, out = set(tiles), []
    while left:
        group, todo = [], [left.pop()]
        while todo:
            n = todo.pop()
            group.append(n)
            x, y = n % across, n // across
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    m = (y + dy) * across + (x + dx)
                    if 0 <= x + dx < across and m in left:
                        left.remove(m)
                        todo.append(m)
        xs, ys = [n % across for n in group], [n // across for n in group]
        out.append((min(xs) * tile, min(ys) * tile, (max(xs) - min(xs) + 1) * tile,
                    (max(ys) - min(ys) + 1) * tile, group))
    return sorted(out, key=lambda b: (b[1], b[0]))


def hex_of(look):
    return "#" + "".join(f"{round(c):02x}" for c in look)


def watch(frames, size, seconds, taken=None, tile=16, brief=0.1, times=8, fuzz=6.0, ignore=(),
          save=None, compressed=False):
    """Flicker and flashes in `frames`, a watch of `seconds` of a picture
    `size` (width, height): each (at, rgb), when it was taken, in seconds
    from the start, and its pixels, width * height * 3 bytes, in order. A
    frame the same as the one before is dropped, as a picture that didn't
    change. Tiles `tile` pixels square, a state no longer than `brief`
    seconds brief, `times` changes or more flicker, looks within `fuzz`
    percent the same, and boxes (width, height, x, y) in `ignore` left
    out. ([dict(kind="flicker" or "flash", box, at, changes, every,
    looks)], a box of tiles each, in order; `taken`, how many pictures
    were, by default how many frames; how many were kept). With `save`, a
    directory, each one's pictures there as a sheet (see `_sheet`), its
    path its "sheet", or "unsaved" if it couldn't be written. With
    `compressed`, each rgb is zlib's, and frames are taken as they are.
    ValueError for what isn't one: a size, seconds, tile or box to ignore
    that isn't; no frames; a time below 0, not after the one before, or
    past the watch's end but for the last's (taken as the watch ended); a
    frame of the wrong number of bytes."""
    number = finite
    if not (isinstance(size, (tuple, list)) and len(size) == 2
            and all(type(v) is int and v >= 1 for v in size)):
        raise ValueError(f"a size is (width, height), each 1 or more, not {size!r}")
    if not (number(seconds) and seconds > 0) or not (type(tile) is int and tile >= 1):
        raise ValueError(f"seconds is more than 0 and tile 1 or more, not {seconds!r}, {tile!r}")
    skip = list(ignore)
    if not all(isinstance(b, tuple) and len(b) == 4 and all(type(v) is int for v in b)
               for b in skip):
        raise ValueError(f"boxes to ignore are (width, height, x, y), not {skip!r}")
    width, height = size
    if compressed:
        shots = list(frames)
        given = len(shots)
    else:
        shots, last, given, before = [], None, 0, None
        for at, data in frames:
            given += 1
            if not (number(at) and at >= 0 and (before is None or at > before)
                    and (before is None or before <= seconds)):
                raise ValueError(f"frame {given}: its time, {at!r}, isn't a number 0 or more, "
                                 "after the one before, all but the last within the watch")
            before = at
            try:
                data = bytes(data)
            except TypeError:
                raise ValueError(f"frame {given}: its pixels aren't bytes") from None
            if len(data) != width * height * 3:
                raise ValueError(f"frame {given}: {len(data)} bytes, not "
                                 f"{width * height * 3}, for {width}x{height}")
            if data != last:
                shots.append((at, zlib.compress(data, 1)))
                last = data
    if not shots:
        raise ValueError("no frames")
    taken = given if taken is None else taken
    if save is not None:
        Path(save).mkdir(parents=True, exist_ok=True)
    times_ = [t for t, _ in shots]
    across = -(-width // tile)
    looks, before = [], None
    for _, data in shots:
        now = zlib.decompress(data)
        looks.append(means(now, width, height, tile, before, looks and looks[-1]))
        before = now
    # A tile's states, by its mean colors, a change of a quarter of fuzz
    # a new one, so a band a pixel or two wide is seen; the pixels decide.
    helds, wanted = {}, {}
    for n in range(len(looks[0])):
        tx, ty = n % across * tile, n // across * tile
        if any(gx < tx + tile and tx < gx + gw and gy < ty + tile and ty < gy + gh
               for gw, gh, gx, gy in skip):
            continue
        helds[n] = states(times_, [frame[n] for frame in looks], seconds,
                                  fuzz * 2.55 / 4)
        for k in needs(helds[n], brief):
            wanted.setdefault(k, []).append(n)
    # Each picture a tile is looked at in, decompressed once, for those.
    tiles_in = {}
    for k in sorted(wanted):
        f = zlib.decompress(shots[k][1])
        for n in wanted[k]:
            tx, ty = n % across * tile, n // across * tile
            x1, y1 = min(tx + tile, width), min(ty + tile, height)
            tiles_in[n, k] = b"".join(f[(y * width + tx) * 3:(y * width + x1) * 3]
                                      for y in range(ty, y1))
    found = {"flicker": {}, "flash": {}}
    for n, held in helds.items():
        tx, ty = n % across * tile, n // across * tile
        flickering, flashed = find(held, brief, times, fuzz,
                                           lambda k, n=n: tiles_in[n, k],
                                           min(tile, width - tx))
        if flickering:
            found["flicker"][n] = flickering
        elif flashed:
            found["flash"][n] = flashed
    # A look that's in the picture before or after, up or down the
    # screen, is text scrolling: lines alike, one where another was, or
    # drawn again the same after a blank, aren't a look coming back,
    # nor a line shown once a flash; a run is scrolling if as many of its
    # looks are as aren't. One color all over says nothing; another look the same
    # down the tile, a gradient across, a border, a strip, is anywhere
    # up or down, and holds its place as scrolling text doesn't. A
    # flicker's look may be a near copy, moved, as text scrolled by
    # fractions of a pixel is; that's asked of about eight of its
    # pictures, by an odd step so both looks are, as finding it costs
    # more, and they're scrolling if as many of those are as aren't.
    few = {(n, k) for n, f in found["flicker"].items() for k in f[5][::len(f[5]) // 8 | 1]}
    ask = {}
    for n, k in ([(n, k) for n, f in found["flicker"].items() for k in f[5]]
                 + [(n, k) for n, fs in found["flash"].items() for f in fs for k in f[4:]]):
        for j in (k - 1, k + 1):
            ask.setdefault(j, []).append((n, k))
    scrolled, say = set(), set()
    for j in sorted(set(ask) & set(range(len(shots)))):
        f, columns = zlib.decompress(shots[j][1]), {}
        for n, k in ask[j]:
            tx, ty = n % across * tile, n // across * tile
            step = (min(tx + tile, width) - tx) * 3
            here = tiles_in[n, k]
            if (n, k) in scrolled or here == here[:3] * (len(here) // 3):
                continue
            say.add((n, k))
            if here == here[:step] * (len(here) // step):
                continue
            if tx not in columns:
                columns[tx] = b"".join(f[(y * width + tx) * 3:(y * width + tx) * 3 + step]
                                       for y in range(height))
            at = columns[tx].find(here)
            while at >= 0 and (at % step or at == ty * step):
                at = columns[tx].find(here, at + 1)
            if at >= 0 or (n, k) in few and moved(here, f, width, tx, ty,
                                                           step // 3, tile, fuzz):
                scrolled.add((n, k))
    def scrolling(n, pictures):
        told = [(n, k) in scrolled for k in pictures if (n, k) in say]
        return bool(told) and 2 * sum(told) >= len(told)
    found["flicker"] = {n: f for n, f in found["flicker"].items() if not scrolling(n, f[5])
                        and not scrolling(n, [k for k in f[5] if (n, k) in few])}
    found["flash"] = {n: [f for f in fs if not scrolling(n, f[4:])]
                      for n, fs in found["flash"].items()}
    out, seen = [], []
    for bx, by, bw, bh, group in boxes(found["flicker"], across, tile):
        bw, bh = min(bw, width - bx), min(bh, height - by)    # tiles at the edge
        # The box said as its tile that changed most does.
        at, changes, every, a, b, ks = max((found["flicker"][n] for n in group),
                                           key=lambda f: f[1])
        out.append(dict(kind="flicker", box=f"{bw}x{bh}+{bx}+{by}", at=at, changes=changes,
                        every=every, looks=(hex_of(a), hex_of(b))))
        # A first look and eight changes: both looks, coming back.
        seen.append(((bx, by, bw, bh), [ks[0] - 1, *ks[:8]]))
    flashes = found["flash"]
    down = len(looks[0]) // across

    def beside(group):
        """The tiles round a group of tiles, not in it."""
        at = ((m % across, m // across) for m in group)
        return {(y + dy) * across + x + dx for x, y in at
                for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                if 0 <= x + dx < across and 0 <= y + dy < down} - set(group)

    def toward(k, n):
        """How tile n's mean color moved in picture k."""
        return [a - b for a, b in zip(looks[k][n], looks[k - 1][n])]

    def along(way, d):
        """Whether a tile's mean color moving `d` went `way`."""
        return (sum(a * b for a, b in zip(way, d))
                > 0.8 * sum(c * c for c in way) ** 0.5 * sum(c * c for c in d) ** 0.5)

    def between(p, a, b):
        """Whether color p is within twice fuzz of the way from a to b."""
        ab = [y - x for x, y in zip(a, b)]
        t = max(0, min(1, sum((q - x) * d for q, x, d in zip(p, a, ab))
                       / (sum(d * d for d in ab) or 1)))
        return near(p, [x + t * d for x, d in zip(a, ab)])

    @functools.lru_cache(maxsize=None)
    def turned(m, i):
        """Tile m's colors where it changed in its state i, before and
        after, or None."""
        old, new = tiles_in.get((m, helds[m][i - 1][3])), tiles_in.get((m, helds[m][i][3]))
        return old and new and colors(old, new, changed(old, new, fuzz / 4))

    def near(p, q):
        """Whether two colors are within twice fuzz of each other."""
        return sum((x - y) ** 2 for x, y in zip(p, q)) ** 0.5 <= 2 * fuzz * 2.55

    def brings(m, i, flashed):
        """Whether tile m's state i took the colors of a flash's, each
        (look, then) in `flashed`, or a part of them, or they its. One
        whose pictures weren't kept, as no run of its own needed them,
        can't say, and is taken to, so motion isn't missed."""
        if not turned(m, i):
            return True
        was, took = turned(m, i)
        return any(between(look, then, took) or between(took, was, look)
                   for look, then in flashed)

    def swapped(n, m):
        """Whether tile m, as flashing tile n changed, went the other
        way, from n's flash look to the look n had: something thin
        stepping from one into the other, as an aliased line's step
        does, or a square leaving a tile as it enters the next."""
        k, look, then = now[n][4], now[n][2], now[n][3]
        if not along([-c for c in toward(k, n)], toward(k, m)):
            return False
        i = next((i for i, st in enumerate(helds[m]) if i and st[3] == k), None)
        return (bool(i and turned(m, i))
                and near(turned(m, i)[0], look) and near(turned(m, i)[1], then))

    def took(m, i):
        """Whether tile m's state i is the color of one of the flash's
        looks, being under it."""
        return bool(turned(m, i)) and any(near(turned(m, i)[1], f[2]) for f in now.values())

    def still(n, i, t):
        """Whether tile n, before its state i, held a look longer than
        `brief`, or since watching began, up to within `brief` of `t`:
        one busy all along, a scene animating, a terminal scrolling,
        didn't."""
        for st in reversed(helds[n][:i]):
            if st[1] + st[2] < t - brief:
                return False
            if st[2] > brief or st is helds[n][0]:
                return True
        return False

    done = set()
    for k in sorted({f[4] for fs in flashes.values() for f in fs}):
        # Tiles that flashed in the same picture make a box. Something
        # moving through turns a tile beside it the same way, briefly,
        # as it passes, within `brief`, or a picture, before or after,
        # if pictures come slower; a flash doesn't, and what changes
        # beside it in the same picture, another way, or for longer, is
        # something else: a caret, a spinner, a word in the flash.
        now = {n: f for n, fs in flashes.items() for f in fs
               if f[4] == k and (n, k) not in done}
        if not now:
            continue
        # What showed only while the flash did, one color or not, is one
        # thing with it, and what's beside that is what's beside it: a
        # square passing, a sliver of it in a tile at the window's edge,
        # or lines of text drawn once in a terminal scrolling.
        gone = max(f[5] for f in now.values())
        # A flash drawn torn, a part of it a picture later, is one: what
        # flashed before it was gone is with it, not something moving.
        now.update({n: f for n, fs in flashes.items() for f in fs if k < f[4] < gone})
        done |= {(n, f[4]) for n, f in now.items()}
        # Of what changed with it, a tile busy before isn't with it,
        # unless the flash covered it, taking its color.
        with_it = {m for m, held in helds.items()
                   for i, (st, after) in enumerate(zip(held, held[1:]))
                   if st[3] == k and after[3] <= gone
                   and (still(m, i, times_[k]) or took(m, i))}
        for bx, by, bw, bh, group in boxes(now.keys() | with_it, across, tile):
            if not now.keys() & set(group):
                continue
            # Most of the box gone other ways than the flash did is a
            # region drawn anew, as a terminal scrolling a page at a time
            # does: its caret gone for the page.
            went = [sum(c) for c in zip(*(toward(now[n][4], n) for n in group if n in now))]
            if 2 * sum(not along(went, toward(k, n)) for n in group if n not in now) > len(group):
                continue
            # Nor is it where a thin thing stepped out of, into a tile of
            # the box or beside it, for that picture.
            if any(swapped(n, m) for n in group if n in now
                   for m in set(group) | beside(group) if m != n and m in helds):
                continue
            # And it passes through what held still, with its colors: a
            # tile beside busy all along, a scene animating, or going
            # darker as text scrolls in by a black flash, says nothing.
            shown = [now[n][2:4] for n in group if n in now]
            if any(along(went, toward(st[3], m)) for m in beside(group) if m in helds
                   for i, st in enumerate(helds[m]) if i and st[3] != k and st[2] <= brief
                   and (abs(st[3] - k) == 1 or abs(st[1] - times_[k]) <= brief)
                   and still(m, i, st[1]) and brings(m, i, shown)):
                continue
            bw, bh = min(bw, width - bx), min(bh, height - by)
            at, held_for, look, then, first, _ = min(
                (now[n] for n in group if n in now), key=lambda f: f[0])
            # Torn, till the last of it is gone.
            after = max(now[n][5] for n in group if n in now)
            out.append(dict(kind="flash", box=f"{bw}x{bh}+{bx}+{by}", at=at, changes=2,
                            every=held_for,
                            looks=(hex_of(then), hex_of(look))))
            seen.append(((bx, by, bw, bh), [*range(first - 1, after)][:8] + [after]))
    order = sorted(range(len(out)), key=lambda i: out[i]["at"])
    if save is not None:
        for number, i in enumerate(order, 1):
            f = out[i]
            path = Path(save) / f"{number:0{len(str(len(out)))}d}-{f['kind']}-{f['box']}.png"
            # One not written leaves the rest, and what was found, to be said.
            try:
                f["sheet"] = str(_sheet(path, shots, seen[i][1], seconds, (width, height),
                                             seen[i][0], tile))
            except (OSError, subprocess.CalledProcessError):
                f["unsaved"] = str(path)
    return [out[i] for i in order], taken, len(shots)


def _sheet(out, shots, ks, end, size, box, margin):
    """Pictures `ks` of `shots`, (seconds, compressed RGB `size`) of a
    watch that ended at `end`, cut to `box` (x, y, width, height) and
    `margin` round it, the box outlined, each labeled with when it
    showed, in order, as one PNG at `out` no more than 1920 pixels each
    way: magnified, a pixel a square, up to 8 times, so a band a pixel
    wide is seen, or shrunk, its label not, to fit."""
    (width, height), (bx, by, bw, bh) = size, box
    x0, y0 = max(0, bx - margin), max(0, by - margin)
    x1, y1 = min(width, bx + bw + margin), min(height, by + bh + margin)
    cw, ch = x1 - x0, y1 - y0
    # As near square as it goes: a strip down the screen side by side,
    # one across it one above another.
    across = max(1, min(len(ks), round((len(ks) * ch / cw) ** 0.5)))
    down = -(-len(ks) // across)
    # A cell's border is 2 pixels, its label 17 high.
    fit = min((1920 // across - 2) / cw, (1920 // down - 20) / ch)
    scale = min(8, int(fit)) or fit
    grow = (["-scale", f"{scale * 100}%"] if scale >= 1
            else ["-resize", f"{int(cw * scale)}x{int(ch * scale)}!"])
    left, top = int((bx - x0) * scale) - 1, int((by - y0) * scale) - 1
    right, bottom = int((bx - x0 + bw) * scale), int((by - y0 + bh) * scale)
    with tempfile.TemporaryDirectory(dir=Path(out).parent) as tmp:
        cells = []
        for n, k in enumerate(ks):
            t, data = shots[k]
            till = shots[k + 1][0] if k + 1 < len(shots) else max(end, t)
            data = zlib.decompress(data)
            cells.append(Path(tmp) / f"{n}.png")
            subprocess.run([*x.CONVERT, "-size", f"{cw}x{ch}", "-depth", "8", "rgb:-", *grow,
                            "-fill", "none", "-stroke", "magenta", "+antialias",
                            # Two wide, so a sheet seen smaller keeps it.
                            "-draw", f"rectangle {left},{top} {right},{bottom}",
                            "-draw", f"rectangle {left - 1},{top - 1} {right + 1},{bottom + 1}",
                            "-antialias", "-stroke", "none", "-fill", "white",
                            "-background", "black", "+size", *x.font(), "-pointsize", "14",
                            f"label:{t:.3f}\u2013{till:.3f}s", "-gravity", "center", "-append",
                            "-bordercolor", "gray50", "-border", "1", str(cells[-1])],
                           input=b"".join(data[(y * width + x0) * 3:(y * width + x1) * 3]
                                          for y in range(y0, y1)), check=True)
        return x.sheet(cells, out, across=across)


def png(path, width, height, rgb):
    """`rgb`, width * height * 3 bytes, as a PNG at `path`, written here,
    as fast as a watch's frames need: each row unfiltered, compressed
    little."""
    def chunk(kind, data):
        return (len(data).to_bytes(4, "big") + kind + data
                + zlib.crc32(kind + data).to_bytes(4, "big"))
    row = width * 3
    rows = b"".join(b"\0" + rgb[y * row:(y + 1) * row] for y in range(height))
    Path(path).write_bytes(b"\x89PNG\r\n\x1a\n"
                           + chunk(b"IHDR", width.to_bytes(4, "big") + height.to_bytes(4, "big")
                                   + bytes([8, 2, 0, 0, 0]))
                           + chunk(b"IDAT", zlib.compress(rows, 1)) + chunk(b"IEND", b""))


def keep(out, shots, size, seconds, taken):
    """A watch, `shots` (at, zlib-compressed rgb) of a picture `size`, in the
    directory `out`, for `flicker --from`: each frame a PNG, then
    frames.json, last, so a watch kept only in part has none."""
    out, digits = Path(out), len(str(len(shots)))
    names = []
    for n, (at, data) in enumerate(shots, 1):
        names.append({"file": f"frame-{n:0{digits}d}.png", "at": at})
        png(out / names[-1]["file"], *size, zlib.decompress(data))
    # Whole or not there: a manifest cut short isn't one.
    part = out / "frames.json.part"
    part.write_text(json.dumps({"version": 1, "seconds": seconds, "taken": taken,
                                "size": list(size), "frames": names}))
    part.replace(out / "frames.json")


def finite(v):
    """Whether `v` is a number a time can be: an int or float, not a bool,
    finite (a whole number too big for a float isn't)."""
    try:
        return type(v) in (int, float) and math.isfinite(v)
    except OverflowError:
        return False


def ready(ignore, save=None, frames=None):
    """The boxes `ignore` says, (width, height, x, y), with `save`'s and
    `frames`' directories made and written to, before a watch: ValueError,
    saying why, for any that can't be."""
    skip = []
    for g in ignore:
        m = re.fullmatch(r"(\d+)x(\d+)\+(\d+)\+(\d+)", g)
        if not m:
            raise ValueError(f"what to ignore is WIDTHxHEIGHT+X+Y, not {g}")
        skip.append(tuple(int(n) for n in m.groups()))
    for kept_in, d in ((True, frames), (False, save)):
        if d is None:
            continue
        if not str(d):
            raise ValueError("a directory to save to, not ''")
        try:
            Path(d).mkdir(parents=True, exist_ok=True)
            tempfile.TemporaryFile(dir=d).close()
        except (FileExistsError, NotADirectoryError):
            raise ValueError(f"can't save to {d}: it, or a directory it's in, is a file") from None
        except OSError as e:
            raise ValueError(f"can't save to {d}: {e.strerror}") from None
        # Not over another watch: one part of each would be read as one.
        if kept_in and any(Path(frames).iterdir()):
            raise ValueError(f"{frames} isn't empty: --frames keeps a watch in a new directory")
        if kept_in and save is not None and (
                Path(frames).resolve() in (Path(save).resolve(), *Path(save).resolve().parents)):
            raise ValueError("--save's directory isn't --frames' or in it")
    return skip


def kept(d):
    """The watch `keep` kept in the directory `d`: (its frames, read a
    PNG at a time as they're asked for, its size, seconds, and how many
    pictures were taken). ValueError, saying why, for what isn't one,
    there or as its frames are read; OSError if ImageMagick can't run."""
    d = Path(d)
    try:
        m = json.loads((d / "frames.json").read_text())
    except OSError as e:
        raise ValueError(f"can't read {d / 'frames.json'}: {e.strerror}") from None
    except ValueError:
        m = None

    number = finite
    if not (isinstance(m, dict) and m.get("version") == 1 and number(m.get("seconds"))
            and m["seconds"] > 0 and isinstance(m.get("size"), list) and len(m["size"]) == 2
            and all(type(v) is int and v >= 1 for v in m["size"])
            and isinstance(m.get("frames"), list) and m["frames"]
            and type(m.get("taken")) is int and m["taken"] >= len(m["frames"])
            and all(isinstance(f, dict) and x.kept_name(f.get("file")) and number(f.get("at"))
                    for f in m["frames"])):
        raise ValueError(f"{d / 'frames.json'} isn't what flicker --frames writes")

    def frames():
        for f in m["frames"]:
            got = x.kept_png(d / f["file"], m["size"])
            if not got:
                raise ValueError(f"{d / f['file']} isn't a {m['size'][0]}x{m['size'][1]} "
                                 "picture flicker --frames wrote")
            yield f["at"], got[2]
    return frames(), tuple(m["size"]), m["seconds"], m["taken"]
