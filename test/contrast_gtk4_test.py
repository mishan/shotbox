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


def glyph(c):
    """`c`'s 5 columns, each a number whose bit y is its pixel y down, of
    TALL: random from its code point, about a third on, as text covers
    its box, but none blank and at least 16 pixels in all (what's
    measured); a space blank, 4 wide."""
    if c == " ":
        return [0] * 4
    r = random.Random(ord(c))
    while True:
        cols = [sum(1 << y for y in range(TALL) if r.random() < 0.3) for _ in range(5)]
        if all(cols) and sum(bin(col).count("1") for col in cols) >= 16:
            return cols


def columns(text, spacing=0):
    """`text`'s columns, its glyphs a blank column apart, `spacing` more."""
    cols = []
    for i, c in enumerate(text):
        cols += ([0] * (1 + spacing) if i else []) + glyph(c)
    return cols


def shape(text):
    """`text` as text_shapes() draws it: its coverage, two blank columns
    each side."""
    cols = [0, 0] + columns(text) + [0, 0]
    cover = bytes(255 if c >> y & 1 else 0 for y in range(TALL) for c in cols)
    return [len(cols), TALL, base64.b64encode(cover).decode()]


def paint(pic, name, drawn, color, spacing):
    for x, c in enumerate(columns(name, spacing)):
        for y in range(TALL):
            if c >> y & 1:
                pic.fill(drawn[0] + x, drawn[1] + y, 1, 1, color)


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
            blink=False, text=None):
        """A node GTK `says` is at [x, y, w, h], its name, or the `text` typed
        in it (a field), drawn in `color` with its corner at `drawn`,
        `spacing` more between its glyphs; if it's to `blink`, not in the
        first picture, but in those after. GTK
        says its extents in its parent's are its box less its parent's,
        and from 4.14.6 lays its text out at its box's corner, as wide as
        it's drawn. A node of one child but a button has no actions, as
        a stack's page."""
        up = next(n for n in self.nodes if n["path"] == path.rsplit("/", 1)[0])
        editable = ["editable"] * (text is not None)
        self.nodes.append(node(path, role, name, ["showing", "visible", *states, *editable], says))
        r = self.reads
        r["relative"][path] = says and up["bounds"] and [
            says[0] - up["bounds"][0], says[1] - up["bounds"][1], *says[2:]]
        r["fonts"][path] = {"family-name": "Fixture", "size": "13", "run-end": str(len(text or name))}
        end = len(name) - (self.release >= (4, 22, 3))
        r["laid"][path] = None if self.release < (4, 14, 6) or not end else [
            0, 0, len(columns(name[:end], spacing))]
        r["paged"][path] = path
        r["popups"][path] = False
        r["texts"][path] = [t for t in (name, text) if t]
        if drawn and blink:
            self.blinking.append((text or name, drawn, color, spacing))
        elif drawn:
            paint(self.pic, text or name, drawn, color, spacing)
        return self

    def contrast(self, *args, trusted=False):
        """contrast --from what a live run would have saved of this window
        with `args` and --window, GTK's bounds `trusted`."""
        later = self.pic.copy()
        for d in self.blinking:
            paint(later, *d)
        paths = [n["path"] for n in self.nodes]
        self.reads["pages"] = {p: "button" not in n["role"] and sum(
            q.rsplit("/", 1)[0] == p for q in paths) == 1 for p, n in zip(paths, self.nodes)}
        texts = {t for ts in self.reads["texts"].values() for t in ts}
        texts |= {n["name"] for n in self.nodes[1:] if n["name"]}
        if self.release >= (4, 22, 3):
            texts |= {t[:-1] for t in texts if len(t) > 1}
        downs = DOWN if self.release >= (4, 16) else DOWN[:1]
        shapes = [{"text": t, "attrs": a, "dy": dy, "kinds": [[shape(t)]]}
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
FOUND = "2.61:1, #a0a0a0 on #ffffff (at least 4.5); found 6,5 px from "
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
for case, faint, blink, want in [
        ("matching in two places, faint, where the other passes, a note", ["check"], False, TWICE),
        ("matching in two places, faint in both, failing at the better", ["check", "Reecheck"], False,
         "2.61:1 at best, #a0a0a0 on #ffffff (at least 4.5); it matches in two places and fails in both"
         + FOUND48),
        ("matching in two places, passing, a note", [], False, TWICE),
        ("blinking, matching in two places, where the other passes, changing", ["check"], True,
         "changing: 1.01:1 to 16.57:1 (at least 4.5)"),
        ("blinking, matching in two places, faint in both, failing at its colors",
         ["check", "Reecheck"], True,
         "2.61:1 at best, changing from 1.01:1, #a0a0a0 on #ffffff (at least 4.5)")]:
    _, out, _ = stacked(["Recheck", "check", "Reecheck"], faint, blink).contrast("--passes")
    got = [line for line in out if line.startswith(L1)]
    check(got == [L1 + want], f"contrast --from, GTK 4: {case}" + ("" if got == [L1 + want] else f": {out}"))

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
              text=t)
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

sys.exit(bool(contrast_fixture.fails))
