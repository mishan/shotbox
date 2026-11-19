#!/usr/bin/env python3
"""a11y contrast --from on GTK 4 windows made by hand: each node where GTK
says it is and where its text is drawn, the reads its search makes and the
shapes it draws, as a live run saves them, a rule a case:
test/contrast_gtk4_test.py SHOTBOX."""

import base64
import random
import re
import sys

import contrast_fixture
from contrast_fixture import WHITE, Pic, check, contrast, node, window

FAINT, DARK = (0xa0,) * 3, (0x20,) * 3
DOWN = (0, -0.25, 0.25, 0.5)   # 4.16's shapes, at fractions of a pixel
TALL = 11


def glyph(c, size="13"):
    """`c`'s 5 columns, each a number whose bit y is its pixel y down, of
    TALL: random from its code point, and its font's `size`, which draws
    it otherwise; about a third on, as text covers its box, but none
    blank and at least 16 pixels in all (what's measured); a space blank,
    4 wide."""
    if c == " ":
        return [0] * 4
    r = random.Random(ord(c) if size == "13" else f"{c} {size}")
    while True:
        cols = [sum(1 << y for y in range(TALL) if r.random() < 0.3) for _ in range(5)]
        if all(cols) and sum(bin(col).count("1") for col in cols) >= 16:
            return cols


def columns(text, spacing=0, size="13"):
    """`text`'s columns, its glyphs a blank column apart, `spacing` more."""
    cols = []
    for i, c in enumerate(text):
        cols += ([0] * (1 + spacing) if i else []) + glyph(c, size)
    return cols


def coverage(cols, dy):
    """How much of each pixel `cols` cover, a row at a time, set `dy` down,
    a fraction of a pixel split between two rows, as antialiased text is;
    a row more where it's split."""
    def at(col, y):
        return 0 <= y < TALL and col >> y & 1
    # Raised, it's drawn as if lowered the rest of a pixel, from a row
    # higher: the row more is above.
    rows, lower = range(TALL + bool(dy)), dy + (dy < 0)
    return [[(1 - lower % 1) * at(col, int(y - lower // 1)) + lower % 1 * at(col, int(y - lower // 1) - 1)
             for col in cols] for y in rows]


def shape(text, size, dy=0):
    """`text` as text_shapes() draws it: its coverage, two blank columns
    each side."""
    rows = coverage([0, 0] + columns(text, size=size) + [0, 0], dy)
    cover = bytes(round(255 * c) for row in rows for c in row)
    return [len(rows[0]), len(rows), base64.b64encode(cover).decode()]


def paint(pic, name, drawn, color, spacing, size, dy=0):
    for y, row in enumerate(coverage(columns(name, spacing, size), dy)):
        for x, c in enumerate(row):
            if c:
                i = ((drawn[1] + y) * pic.w + drawn[0] + x) * 3
                was = pic.data[i:i + 3]
                pic.data[i:i + 3] = bytes(round(b * (1 - c) + f * c) for b, f in zip(was, color))


class Gtk4Window:
    """A GTK 4 window `size` big, of nodes added by path in tree order."""

    def __init__(self, release, size=(300, 120), back=WHITE, grid=None):
        """Its background `back`, lines of a `grid` color across it every
        24 pixels, from its left and its bottom, as CSS's
        repeating-linear-gradient draws them."""
        self.release = tuple(map(int, release.split(".")))
        self.pic = Pic(*size, back=back)
        w, h = size
        for x in range(0, w, 24) if grid else ():
            self.pic.fill(x, 0, 1, h, grid)
        for y in range(h - 1, -1, -24) if grid else ():
            self.pic.fill(0, y, w, 1, grid)
        self.nodes = [window(toolkit=f"GTK {release}", bounds=[0, 0, *size], window=[0, 0, *size])]
        self.blinking = []
        self.reads = {k: {} for k in ("relative", "pages", "fonts", "laid", "paged", "popups", "texts")}

    def add(self, path, role, name="", says=None, drawn=None, color=FAINT, spacing=0, states=(),
            blink=False, text=None, draws=None, laid=(0, 0), size="13", labeled=False, page=False,
            relative=None, down=0):
        """A node GTK `says` is at [x, y, w, h], drawn with its corner at
        `drawn`, `down` a fraction of a pixel lower, in `color`, in a font
        `size`, `spacing` more between its glyphs; if it's to `blink`, not
        in the first picture, but in those after. What it draws is
        `draws`, else the `text` in it (a field's, or a label's named
        otherwise), else its name. GTK says its extents in its parent's
        are `relative`, else its box less its parent's; from 4.14.6 lays
        its text out at `laid` in its box, as wide as what it shows;
        leaves out its name of what it may draw if a label it's `labeled`
        by names it; and says it has one child and no actions if it's a
        stack's `page`."""
        up = next(n for n in self.nodes if n["path"] == path.rsplit("/", 1)[0])
        self.nodes.append(node(path, role, name, ["showing", "visible", *states], says))
        r = self.reads
        r["relative"][path] = relative or says and up["bounds"] and [
            says[0] - up["bounds"][0], says[1] - up["bounds"][1], *says[2:]]
        r["pages"][path] = page
        r["fonts"][path] = {"family-name": "Fixture", "size": size, "run-end": str(len(text or name))}
        shows = text or name
        end = len(shows) - (self.release >= (4, 22, 3))
        r["laid"][path] = None if self.release < (4, 14, 6) or not end else [
            *laid, len(columns(shows[:end], spacing))]
        r["paged"][path] = path
        r["popups"][path] = False
        r["texts"][path] = [t for t in (None if labeled else name, text) if t]
        if drawn and blink:
            self.blinking.append((draws or text or name, drawn, color, spacing, size, down))
        elif drawn:
            paint(self.pic, draws or text or name, drawn, color, spacing, size, down)
        return self

    def contrast(self, *args, trusted=False):
        """contrast --from what a live run would have saved of this window
        with `args` and --window, GTK's bounds `trusted`."""
        later = self.pic.copy()
        for d in self.blinking:
            paint(later, *d)
        texts = {t for ts in self.reads["texts"].values() for t in ts}
        texts |= {n["name"] for n in self.nodes[1:] if n["name"]}
        if self.release >= (4, 22, 3):
            texts |= {t[:-1] for t in texts if len(t) > 1}
        downs = DOWN if self.release >= (4, 16) else DOWN[:1]
        shapes = [{"text": t, "attrs": a, "dy": dy, "kinds": [[shape(t, dict(a)["size"], dy)]]}
                  for t in sorted(texts) for a in {tuple(sorted(f.items())) for f in
                                                   self.reads["fonts"].values()}
                  for dy in downs]
        for s in shapes:
            s["attrs"] = dict(s["attrs"])
        # Every read of a field, and every shape of its texts, only in
        # fields.json, as --save keeps them.
        fields = {n["path"] for n in self.nodes if "editable" in n["states"]}
        typed = {t for p in fields for t in self.reads["texts"][p]}
        apart = {k: ({p: v for p, v in r.items() if p not in fields},
                     {p: v for p, v in r.items() if p in fields}) for k, r in self.reads.items()}
        gtk4 = {"version": 1, "trusted": trusted, "cannot": None, "raised": True, "gone": None,
                "reads": {k: r[0] for k, r in apart.items()}}
        files = [("gtk4.json", gtk4), ("shapes.json", {"version": 1, "shapes": [
            x for x in shapes if x["text"] not in typed]})]
        if fields:
            files.append(("fields.json", {"version": 1, "reads": {k: r[1] for k, r in apart.items()},
                                          "shapes": [x for x in shapes if x["text"] in typed]}))
        return contrast(self.nodes, self.pic, *args, samples=[(later, 0, 0)] * bool(self.blinking),
                        files=files)


def label(win, i, name, says, drawn, color=FAINT, up="frame/panel[0]", **more):
    return win.add(f"{up}/label[{i}]", "label", name, says, drawn, color, **more)


def boxed(release):
    """A window with a panel GTK says is at 10,10, 280 by 60."""
    return Gtk4Window(release).add("frame/panel[0]", "panel", says=[10, 10, 280, 60])


def loose(line):
    """`line` as a pattern, any score for 0.NN, anything for "..."."""
    return re.compile(re.escape(line).replace(r"0\.NN", r"0\.\d\d").replace(r"\.\.\.", ".*"))


def run(case, got, want):
    """Whether contrast said `want`: (status, lines), a line a pattern
    where it's re.Pattern."""
    ok = got[0] == want[0] and len(got[1]) == len(want[1]) and all(
        w.fullmatch(g) if isinstance(w, re.Pattern) else g == w for g, w in zip(got[1], want[1]))
    check(ok, f"contrast --from, GTK 4: {case}" + ("" if ok else f": {got}"))


L0 = "frame/panel[0]/label[0]: text "
PASS = "passes at 16.29:1, #202020 on #ffffff (at least 4.5); found 6,5 px from "
NOTED = "not measured: GTK 4 reports its position wrong"
SAYS = [10, 10, 80, 16]


def dark(release, name):
    return label(boxed(release), 0, name, SAYS, (16, 15), color=DARK)


# Text found where it's drawn: up to 4.14.5 inside the box GTK says, from
# 4.14.6 below and right of where it says the text is, as far as its
# containers have room round what's in them.
FAILING_AT = "2.61:1, #a0a0a0 on #ffffff (at least 4.5); found "
FOUND = FAILING_AT + "6,5 px from "
for release, says, want in [
        ("4.14.5", [10, 10, 80, 16], [L0 + FOUND + "the corner of the box GTK 4.14.5 says"]),
        ("4.14.6", [10, 10, 70, 12], [L0 + FOUND + "where GTK 4.14.6 says its text is"]),
        ("4.14.5", [10, 10, 70, 12], [L0 + "not found, but nothing where it can be has the contrast it "
                                      "needs: the best anything there reaches is 2.66:1 (at least 4.5)"])]:
    run(f"text where it's drawn, GTK {release} saying it's in {says[2]} by {says[3]}",
        label(boxed(release), 0, "Faint words", says, (16, 15)).contrast(), (1, want))

# At its second page, the first's label left of the window.
carousel = Gtk4Window("4.14.6").add("frame/panel[0]", "panel", says=[-300, 0, 600, 120])
label(carousel, 0, "Before", [-290, 10, 80, 16], None)
label(carousel, 1, "Shown", SAYS, (16, 15), DARK)
disabled = (label(boxed("4.14.6"), 0, "Faint words", [16, 15, 80, 11], (16, 15))
            .add("frame/panel[0]/push button[1]", "push button", "Off", [16, 40, 40, 20], states=["disabled"])
            .add("frame/panel[0]/push button[1]/label[0]", "label", "Off", [20, 45, 20, 11], (20, 45)))
for case, win, kw, want in [
    ("told to trust GTK's bounds, measured where it says; not a disabled button's label", disabled,
     dict(trusted=True), (1, [L0 + "2.61:1, #a0a0a0 on #ffffff (at least 4.5)"])),
    ("a single letter from 4.22.3, which GTK gives no width, noted",
     dark("4.22.3", "A"), {}, (2, [L0 + NOTED + " (a single letter: GTK gives it no width)"])),
    *[(f"a single letter up to 4.22.2, or one with no case, found ({t}, {r})", dark(r, t), {},
       (0, [L0 + PASS + where])) for r, t, where in [
           ("4.22.2", "A", "where GTK 4.22.2 says its text is"),
           ("4.22.3", "+", "the corner of the box GTK 4.22.3 says")]],
    ("text from 4.22.3, its width a character short", dark("4.22.3", "Hello"), {},
     (0, [L0 + PASS + "where GTK 4.22.3 says its text is"])),
    ("text not all ASCII up to 4.14.5, found", dark("4.14.5", "\u00dcber"), {},
     (0, [L0 + PASS + "the corner of the box GTK 4.14.5 says"])),
    ("text not all ASCII from 4.14.6, whose width GTK says short, noted", dark("4.14.6", "\u00dcber"), {},
     (2, [L0 + NOTED + " (not all ASCII: GTK measures its width short)"])),
    ("a carousel's page not shown, its label outside the window, noted", carousel, {},
     (0, ["frame/panel[0]/label[1]: text " + PASS + "where GTK 4.14.6 says its text is",
          L0 + "not measured: not shown (scrolled out of view, or hidden)"])),
]:
    run(case, win.contrast("--passes", **kw), want)

# Nothing measured but faint text not found, and what --strict fails for
# not being measured: 1, not 2, "nothing measured".
lone = label(boxed("4.14.6"), 0, "Faint words", SAYS, (16, 15), spacing=2)
run("--strict fails what fails, where nothing else is measured",
    label(lone, 1, "\u00dcber", [10, 40, 80, 16], (16, 45), DARK).contrast("--strict"),
    (1, [L0 + "not found, but nothing where it can be has the contrast it needs: the best anything "
         "there reaches is 2.66:1 (at least 4.5)", "frame/panel[0]/label[1]: text " + NOTED
         + " (not all ASCII: GTK measures its width short)"]))

# What isn't measured fails --strict, beside text that passes.
for args, st in [((), 0), (("--strict",), 1)]:
    run(f"what isn't measured, failing only with --strict ({' '.join(args)})",
        label(dark("4.14.6", "Hello"), 1, "\u00dcber", [10, 40, 80, 16], (16, 45), DARK).contrast(*args),
        (st, ["frame/panel[0]/label[1]: text " + NOTED + " (not all ASCII: GTK measures its width short)"]))

# A stack's page, whose place GTK counts twice in its child's: found
# where it's drawn, that place taken off once.
stack = Gtk4Window("4.14.6").add("frame/panel[0]", "panel", says=[10, 10, 280, 80])
stack.add("frame/panel[0]/panel[0]", "panel", says=[20, 20, 100, 30], page=True, relative=[10, 10, 100, 30])
stack.add("frame/panel[0]/panel[0]/label[0]", "label", "Faint words", [30, 30, 100, 30], (20, 22),
          relative=[10, 10, 100, 30])
run("a stack's page's child, its place counted twice, found where it's drawn", stack.contrast(),
    (1, ["frame/panel[0]/panel[0]/label[0]: text " + FAILING_AT
         + "-10,-8 px from where GTK 4.14.6 says its text is"]))

# From 4.16, GTK sets text at fractions of a pixel, which no shape drawn
# at whole ones matches well enough: looked for again as drawn a quarter,
# a half and three quarters lower; before, not.
for down in (0.5, 0.25, -0.25):
    for release, st, want in [
            ("4.14.6", 2, re.compile(re.escape(L0 + NOTED) + r" \(no match good enough: 0\.\d\d at best\)")),
            ("4.16.0", 0, L0 + PASS + "where GTK 4.16.0 says its text is")]:
        run(f"text set {down} px down, at {release}",
            label(boxed(release), 0, "Faint words", SAYS, (16, 15), DARK, down=down).contrast("--passes"),
            (st, [want]))

# Text over a dark theme's grid, whose lines vary as much as faint text
# does, beside text that passes: faint, found and failing; faint and
# spaced, not found, but nothing where it can be has the contrast it
# needs, failing too; readable and spaced, not found, a note, failing
# only with --strict. What GTK says of that: from 4.14.6, how much wider
# it lays it out than it's drawn.
GLOOM, LINES = (0x0f, 0x0d, 0x14), (0x1e, 0x19, 0x29)
DIM, LIGHT = (0x3a, 0x34, 0x46), (0xeb, 0xe6, 0xf0)
for release, spaced, ending in [
        ("4.14.5", r"no match good enough: 0\.\d\d at best", "the corner of the box GTK 4.14.5 says"),
        ("4.14.6", "GTK lays it out 30 px wider than its font draws it: letter-spaced, larger or upper case",
         "where GTK 4.14.6 says its text is")]:
    for case, color, spacing, args, want in [
            ("faint", DIM, 0, (), (1, [L0 + "1.61:1, #3a3446 on #0f0d14 (at least 4.5); found 6,5 px from "
                                       + ending])),
            ("faint and spaced", DIM, 3, (), (1, [L0 + "not found, but nothing where it can be has the "
                                                  "contrast it needs: the best anything there reaches is "
                                                  "1.65:1 (at least 4.5)"])),
            *[(f"readable and spaced{', --strict' * st}", LIGHT, 3, ("--strict",) * st,
               (st, [re.compile(re.escape(L0 + NOTED + " (") + spaced + r"\)")])) for st in (0, 1)]]:
        win = Gtk4Window(release, back=GLOOM, grid=LINES).add("frame/panel[0]", "panel",
                                                               says=[10, 10, 280, 60])
        label(win, 0, "Faint words", SAYS, (16, 15), color, spacing=spacing)
        label(win, 1, "Shown", [10, 40, 80, 16], (16, 45), LIGHT)
        run(f"over a grid, {case} ({release})", win.contrast(*args), want)


def stacked(texts, faint=(), blink=False):
    """A box of labels one over another, as GTK 4.14.6 lays them out:
    padded 4 round and 40 below, so each one's room takes in those under
    it, its labels said 4 left of where they're drawn and 8 up."""
    win = Gtk4Window("4.14.6", (300, 160)).add("frame/panel[0]", "panel",
                                                says=[5, 15, 290, 44 + 19 * len(texts)])
    for i, t in enumerate(texts):
        label(win, i, t, [5, 15 + 19 * i, 6 * len(t) + 7, 19], (9, 23 + 19 * i),
              FAINT if t in faint else DARK, blink=blink)
    return win


# "check" over "unchecked": "unchecked" found, "check" inside it no match
# for all of it; "check", matching in both, taken at its own place, the
# other being inside "unchecked", found.
PASSING = "passes at 16.29:1, #202020 on #ffffff (at least 4.5)"
FAILING = "2.61:1, #a0a0a0 on #ffffff (at least 4.5)"
FOUND48 = "; found 4,8 px from where GTK 4.14.6 says its text is"
L1 = "frame/panel[0]/label[1]: text "
for faint, st in [((), 0), (("check",), 1)]:
    run("text found though shorter text inside it matches there; the shorter at its own place"
        + " (faint)" * bool(faint), stacked(["check", "unchecked"], faint).contrast("--passes"),
        (st, [L0 + (FAILING if faint else PASSING) + FOUND48, L1 + PASSING + FOUND48]))

# Under "Recheck", which holds "check", "check"'s own place is in doubt:
# it fails in both places only over a faint "Reecheck", at the better;
# where one passes, it's a note naming the other. "Reecheck" is drawn as
# "Recheck" nearly is, but doesn't hold it, so it isn't found apart from
# it, as real fonts draw "unchecked". Blinking, not drawn when first
# pictured, it's looked for in the pictures after, its doubt as before:
# over a faint "Reecheck" taken, only to fail in both, at its colors;
# over one that passes, bounded by what's there, changing: up to 16.57:1,
# the most anything where it can be reaches, not its own 16.29:1.
TWICE = 'not measured: GTK 4 reports its position wrong (it matches elsewhere too, in "Reecheck")'
L2 = "frame/panel[0]/label[2]: text "
OVER = loose(L0 + NOTED + " (it matches elsewhere too, 0.NN: the same text twice, or like it)")
UNDER = L2 + NOTED + ' (another node\'s text matches there too: "Recheck")'
NONE = "not found, but nothing where it can be has the contrast it needs: the best anything there reaches is "
CHANGING = "changing: 1.01:1 to 16.57:1 (at least 4.5)"
for case, faint, blink, want in [
        ("matching in two places, faint, where the other passes, a note", ["check"], False,
         (2, [OVER, L1 + TWICE, UNDER])),
        ("matching in two places, faint in both, failing at the better", ["check", "Reecheck"], False,
         (1, [L1 + "2.61:1 at best, #a0a0a0 on #ffffff (at least 4.5); it matches in two places and fails in "
              "both" + FOUND48, L2 + NONE + "2.66:1 (at least 4.5)", OVER])),
        ("matching in two places, passing, a note", [], False, (2, [OVER, L1 + TWICE, UNDER])),
        ("blinking, matching in two places, where the other passes, changing", ["check"], True,
         (1, [L2 + NONE + "1.01:1 (at least 4.5)", L0 + CHANGING, L1 + CHANGING])),
        ("blinking, matching in two places, faint in both, failing at its colors",
         ["check", "Reecheck"], True,
         (1, [L1 + "2.61:1 at best, changing from 1.01:1, #a0a0a0 on #ffffff (at least 4.5)",
              L2 + "2.66:1 at best, changing from 1.01:1 (at least 4.5)", L0 + CHANGING]))]:
    run(case, stacked(["Recheck", "check", "Reecheck"], faint, blink).contrast("--passes"), want)

# A hidden "Open File" isn't taken for "Open" and "File" drawn side by
# side under it, where it would draw them: "Open" is drawn only there.
split = Gtk4Window("4.14.6", (300, 160)).add("frame/panel[0]", "panel", says=[5, 15, 290, 82])
split.add("frame/panel[0]/label[0]", "label", "Open File", [5, 15, 61, 19])
split.add("frame/panel[0]/panel[1]", "panel", says=[5, 34, 280, 19])
FILE = 9 + len(columns("Open ")) + 1
label(split, 0, "Open", [5, 34, 31, 19], (9, 42), DARK, up="frame/panel[0]/panel[1]")
label(split, 1, "File", [FILE - 4, 34, 31, 19], (FILE, 42), DARK, up="frame/panel[0]/panel[1]")
OTHER = "not measured: GTK 4 reports its position wrong (another node's text matches there too: "
run("text not taken for pieces of it drawn side by side, nor they for it", split.contrast("--passes"),
    (2, [L0 + OTHER + '"Open")', "frame/panel[0]/panel[1]/label[0]: text " + OTHER + '"Open File")',
         "frame/panel[0]/panel[1]/label[1]: text " + OTHER + '"Open File")']))

# Check boxes in rows, and entries each above a label of their text, in
# its room, as GTK lays them out in a padded, bordered box. Text found in
# two places, one inside another's found and taken there, is taken at the
# other: "tick" passing and "dim" failing. Not the first "pair", whose
# other place is the second's, not taken; nor the second, whose other
# place is in "unpair", and looked for again at the one left, the first's
# room reaches it. And text an entry holds too, found where only that
# one's room reaches as well: "Same" passing, "Pale" failing.
GRAY, INK, PALE = (0xf0,) * 3, (0x10,) * 3, (0xc8,) * 3
owned = Gtk4Window("4.14.6", (454, 359), back=GRAY).add("frame/panel[0]", "panel", says=[0, 0, 454, 359])
for i, y, h, boxes in [(0, 0, 27, [("tick", INK), ("untick", INK)]),
                       (1, 39, 19, [("dim", PALE), ("undim", PALE)]),
                       (2, 70, 27, [("pair", INK), ("pair", INK), ("unpair", INK)])]:
    owned.add(f"frame/panel[0]/panel[{i}]", "panel", says=[0, y, 440, h])
    x = 0
    for j, (t, color) in enumerate(boxes):
        box, wide = f"frame/panel[0]/panel[{i}]/check box[{j}]", 6 * len(t) + 7
        owned.add(box, "check box", t, [x, y, 20 + wide, h])
        owned.add(box + "/panel[0]", "panel", says=[x, y + 1, 16, 16])
        owned.add(box + "/label[1]", "label", t, [x + 20, y, wide, 19], (x + 31, y + 13), color)
        x += 26 + wide
for i, t, y, color in [(3, "Same", 109, INK), (4, "Pale", 231, PALE)]:
    owned.add(f"frame/panel[0]/panel[{i}]", "panel", says=[0, y, 168, 110])
    owned.add(f"frame/panel[0]/panel[{i}]/text[0]", "text", f"{t} field", [0, y, 168, 34], (13, y + 21), INK,
              states=["editable"], text=t)
    label(owned, 1, t, [0, y + 40, 168, 19], (7, y + 49), color, up=f"frame/panel[0]/panel[{i}]")
TAKEN = " px from where GTK 4.14.6 says its text is"
DIMLY = "text 1.46:1, #c8c8c8 on #f0f0f0 (at least 4.5); found "
INKY = "text passes at 16.69:1, #101010 on #f0f0f0 (at least 4.5); found "
run("text found in two places, one inside where another's is found, taken at the other",
    owned.contrast("--passes"),
    (1, [f"frame/panel[0]/panel[1]/check box[0]/label[1]: {DIMLY}11,13{TAKEN}",
         f"frame/panel[0]/panel[1]/check box[1]/label[1]: {DIMLY}11,13{TAKEN}",
         f"frame/panel[0]/panel[4]/label[1]: {DIMLY}7,9{TAKEN}",
         f"frame/panel[0]/panel[0]/check box[0]/label[1]: {INKY}11,13{TAKEN}",
         f"frame/panel[0]/panel[0]/check box[1]/label[1]: {INKY}11,13{TAKEN}",
         f"frame/panel[0]/panel[2]/check box[2]/label[1]: {INKY}11,13{TAKEN}",
         f"frame/panel[0]/panel[3]/label[1]: {INKY}7,9{TAKEN}",
         'frame/panel[0]/panel[2]/check box[0]/label[1]: text not measured: GTK 4 reports its position wrong '
         '(it matches elsewhere too, in "pair")',
         'frame/panel[0]/panel[2]/check box[1]/label[1]: text not measured: GTK 4 reports its position wrong '
         '(it matches elsewhere too, in "unpair")']))

# A faint "Twin" over an entry holding "Twin", the entry's text in its
# room, or under it, in the entry's, the entry's text where nothing else
# can draw it: found where it's drawn, and failing. Nothing else is
# measured: not a hidden "Twin" over the label, nor, where GTK says
# what's in a box padded 40 above is over what's laid on its top, a label
# there or a hidden one, with a label, a drawing area or a label named
# otherwise on top. Laid out as GTK 4.24 laid out such windows of
# a11y_app.py's, saved live. Where both places match
# exactly, as a drawing area's or a label's drawing of it does here,
# which one is the other place can go either way, and so what the note
# names: not whether it's measured.
P, EDIT = "frame/panel[0]", ["editable"]


def twin(under=False, hidden=False):
    win = Gtk4Window("4.14.6", (360, 200)).add(P, "panel", says=[5, 15, 350, 93])
    y, typed = (49, 15) if under else (15, 34)
    over = f"{P}/panel[{int(under)}]"
    win.add(over, "panel", says=[5, y, 31, 19])
    win.add(over + "/label[0]", "label", "Twin", [5, y, 31, 19], (5, y))
    if hidden:
        win.add(over + "/label[1]", "label", "Twin", [5, y, 31, 19])
    return win.add(f"{P}/text[{int(not under)}]", "text", "", [5, typed, 168, 34], (14, typed + 8),
                   DARK, states=EDIT, text="Twin")


def over(hidden=False, drawn=False, named=False):
    """A box padded 40 above, an overlay's child, holding an entry of
    "Twin", or with `hidden`, `drawn` or `named` a tall label "Twin";
    over its top a faint label "Twin", or a dark one with `hidden`, a
    drawing area drawing it with `drawn`, a label named "Brother"
    showing it with `named`. With `hidden`, a hidden "Twin" laid 40 down
    too; without, with a tall label, a faint one, an entry of "Twin"
    beside it all."""
    tall, beside = hidden or drawn or named, (drawn or named) and not hidden
    win = Gtk4Window("4.14.6", (360, 220)).add(P, "panel", says=[5, 15, 350, 180 if tall else 174])
    if beside:
        win.add(f"{P}/text[0]", "text", "", [5, 61, 168, 34], (14, 69), DARK, states=EDIT, text="Twin")
    x, up = (173, f"{P}/panel[1]") if beside else (5, f"{P}/panel[0]")
    box = [x, 15, 31, 80] if tall else [x, 15, 168, 74]
    win.add(up, "panel", says=box).add(up + "/panel[0]", "panel", says=box)
    if tall:
        win.add(up + "/panel[0]/label[0]", "label", "Twin", [x, 15, 31, 40], (x, 65),
                DARK if hidden else FAINT, laid=(0, 10))
    else:
        win.add(up + "/panel[0]/text[0]", "text", "", [x, 15, 168, 34], (14, 63), DARK, states=EDIT,
                text="Twin")
    if drawn:
        win.add(up + "/panel[1]", "panel", says=[x, 15, 80, 24], drawn=(x, 15), color=DARK, draws="Twin")
    elif named:
        win.add(up + "/label[1]", "label", "Brother", [x, 15, 31, 19], (x, 15), DARK, text="Twin")
    else:
        win.add(up + "/label[1]", "label", "Twin", [x, 15, 31, 19], (x, 15), DARK if hidden else FAINT)
    if hidden:
        win.add(up + "/label[2]", "label", "Twin", [x, 55, 31, 40], laid=(0, 10))
    return win


FOUND00 = "2.61:1, #a0a0a0 on #ffffff (at least 4.5); found 0,0 px from where GTK 4.14.6 says its text is"
AGAIN = 'not measured: GTK 4 reports its position wrong (it matches elsewhere too, in '
for case, win, want in [
        ("a faint twin over an entry holding its text, found where it's drawn", twin(),
         (1, [f"{P}/panel[0]/label[0]: text " + FOUND00])),
        ("a faint twin under an entry holding its text, found where it's drawn", twin(under=True),
         (1, [f"{P}/panel[1]/label[0]: text " + FOUND00])),
        ("a twin with a hidden one over it, not measured", twin(hidden=True),
         (2, [f"{P}/panel[0]/label[{i}]: text " + AGAIN + '"Twin")' for i in (0, 1)])),
        ("a twin where GTK says an entry holding its text is, not measured", over(),
         (2, [f"{P}/panel[0]/label[1]: text " + AGAIN + 'the text "", whose text is "Twin")'])),
        ("a twin where GTK says a label is, with a hidden one, not measured", over(hidden=True),
         (2, [f"{P}/panel[0]/panel[0]/label[0]: text " + AGAIN + '"Twin")',
              f"{P}/panel[0]/label[1]: text " + AGAIN + '"Twin")',
              f"{P}/panel[0]/label[2]: text " + OTHER + '"Twin")']))]:
    run(case, win.contrast("--passes"), want)
TIED = NOTED + " (it matches elsewhere too, ...)"
for case, win, want in [
        ("a drawing area drawing it, and a hidden one", over(True, True),
         [f"{P}/panel[0]/panel[0]/label[0]: text " + TIED,
          f"{P}/panel[0]/label[2]: text " + OTHER + '"Twin")']),
        ("a drawing area drawing it", over(drawn=True), [f"{P}/panel[1]/panel[0]/label[0]: text " + TIED]),
        ("a label named otherwise", over(named=True),
         [f"{P}/panel[1]/panel[0]/label[0]: text " + TIED,
          f"{P}/panel[1]/label[1]: text " + NOTED + " (no match good enough: 0.NN at best)"])]:
    run(f"a twin where GTK says a label is, with {case} on top, not measured", win.contrast("--passes"),
        (2, [loose(line) for line in want]))

# An entry row's two title labels at one place, the small one drawn, the
# large one not: that one said so, not failed for what's there, nor
# noted unmatched; not said of a label not drawn over another text, nor
# one apart from its own. Laid out as libadwaita lays out a11y_app.py's.
ROW = "frame/list[0]/list item[0]/panel[0]/panel[0]"


def titled(color):
    win = Gtk4Window("4.14.6", (360, 200)).add("frame/list[0]", "list", says=[5, 15, 350, 54])
    win.add("frame/list[0]/list item[0]", "list item", "Display name Display name", [5, 15, 350, 54])
    win.add(ROW.rsplit("/", 1)[0], "panel", says=[11, 15, 334, 50]).add(ROW, "panel", says=[11, 15, 334, 50])
    win.add(ROW + "/label[0]", "label", "Display name", [11, 21, 77, 16], size="17")
    win.add(ROW + "/label[1]", "label", "Display name", [11, 21, 77, 16], (19, 23), color)
    win.add(ROW + "/text[2]", "text", "Display name", [11, 15, 282, 50], (19, 42), DARK, states=EDIT,
            text="Neon Doll", labeled=True)
    win.add("frame/panel[1]", "panel", says=[5, 75, 41, 19])
    label(win, 0, "Shown", [5, 75, 41, 19], (5, 75), DARK, up="frame/panel[1]")
    label(win, 1, "Ghost", [5, 75, 41, 19], None, up="frame/panel[1]")
    label(win, 2, "Ghost", [5, 100, 37, 19], (5, 100), DARK, up="frame")
    return label(win, 3, "Ghost", [5, 165, 40, 17], None, up="frame")


FOUND82 = "; found 8,2 px from where GTK 4.14.6 says its text is"
DRAWN = [f"frame/panel[1]/label[0]: text {PASSING}; found 0,0 px from where GTK 4.14.6 says its text is",
         f"frame/label[2]: text {PASSING}; found 0,0 px from where GTK 4.14.6 says its text is",
         ROW + "/label[0]: text " + NOTED + " (another node with its text is drawn where it is instead)",
         loose("frame/panel[1]/label[1]: text " + NOTED + " (no match good enough: 0.NN at best)")]
GONE = "frame/label[3]: text " + NONE + "1.01:1 (at least 4.5)"
for look, color, want in [("faint", FAINT, [ROW + "/label[1]: text " + FAILING + FOUND82, GONE]),
                          ("dark", DARK, [GONE, ROW + "/label[1]: text " + PASSING + FOUND82])]:
    run(f"an entry row's title not drawn said so, its twin measured ({look})",
        titled(color).contrast("--passes"), (1, want + DRAWN))

# Rows of a list scrolled out of view, which GTK calls showing: above the
# list but in the window, and below the window, said not shown, as with
# --strict, which fails what else isn't measured, but not those. Laid
# out as GTK 4.24 lays out a11y_app.py's, scrolled 60 px down.
LIST = "frame/scroll pane[0]/panel[0]/panel[0]"
rows = Gtk4Window("4.14.6", (360, 240)).add("frame/scroll pane[0]", "scroll pane", says=[5, 51, 350, 184])
rows.add("frame/scroll pane[0]/panel[0]", "panel", says=[5, 51, 350, 184])
rows.add(LIST, "panel", says=[5, -9, 350, 3800])
for i in (2, 3, 4, 199):
    label(rows, i, f"Row {i}", [5, -9 + 19 * i, 350, 19], (161, -9 + 19 * i + 4), DARK, up=LIST,
          laid=(156, 0))
label(rows, 5, "\u00dcber", [5, -9 + 19 * 5, 350, 19], (161, -9 + 19 * 5 + 4), DARK, up=LIST, laid=(156, 0))
UBER = f"{LIST}/label[5]: text " + NOTED + " (not all ASCII: GTK measures its width short)"
HID = [f"{LIST}/label[{i}]: text not measured: not shown (scrolled out of view, or hidden)" for i in (2, 199)]
for args, st in [((), 0), (("--strict",), 1)]:
    run(f"rows scrolled out of view, not shown{' (--strict)' * bool(args)}", rows.contrast(*args),
        (st, [UBER] * st + HID + [UBER] * (not st)))

sys.exit(bool(contrast_fixture.fails))
