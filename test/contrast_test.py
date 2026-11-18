#!/usr/bin/env python3
"""a11y contrast --from, on trees and pictures made by hand from what each
rule says: no display, accessibility bus or PyGObject (its import is
blocked): test/contrast_test.py SHOTBOX."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

sb = sys.argv[1]
fails = 0
tmp = Path(tempfile.mkdtemp())
(tmp / "gi").mkdir()
(tmp / "gi" / "__init__.py").write_text("raise ImportError('PyGObject blocked by contrast_test.py')\n")
CONVERT = ["magick"] if subprocess.run(["sh", "-c", "command -v magick"],
                                       capture_output=True).returncode == 0 else ["convert"]
WHITE, BLACK = (255, 255, 255), (0, 0, 0)


def check(ok, what):
    global fails
    print(("ok    " if ok else "FAIL  ") + what)
    fails += not ok


class Pic:
    def __init__(self, w=200, h=100, back=WHITE):
        self.w, self.h, self.data = w, h, bytearray(bytes(back) * w * h)

    def fill(self, x, y, w, h, color):
        for j in range(y, y + h):
            self.data[(j * self.w + x) * 3:(j * self.w + x + w) * 3] = bytes(color) * w
        return self

    def text(self, box, color):
        """Strokes in `box` (x, y, w, h), as a glyph's are: 4 rows, 3 wide."""
        x, y, w, h = box
        for i in range(x + 2, x + w - 4, 6):
            self.fill(i, y + 2, 3, max(h - 4, 1), color)
        return self

    def copy(self):
        p = Pic(self.w, self.h)
        p.data = bytearray(self.data)
        return p

    def save(self, path):
        subprocess.run([*CONVERT, "ppm:-", str(path)], check=True,
                       input=b"P6 %d %d 255\n" % (self.w, self.h) + bytes(self.data))


def node(path, role, name="", states=(), bounds=None, **more):
    return {"role": role, "name": name, "description": "", "states": list(states), "path": path,
            "depth": path.count("/"), "bounds": bounds, **more}


def window(toolkit="gtk 3.24.49", **more):
    return node("frame", "frame", "w", bounds=[0, 0, 200, 100], pid=7, toolkit=toolkit,
                window=[0, 0, 200, 100], **more)


def contrast(nodes, screen, *args, samples=(), hovers=(), pictures=None, tree=None):
    """contrast --from a directory of `nodes`, the `screen` picture,
    `samples` (Pic, x, y) and `hovers` (box, Pic): (status, lines, stderr)."""
    d = Path(tempfile.mkdtemp(dir=tmp))
    (d / "tree.json").write_text(tree if tree is not None else json.dumps(nodes))
    screen.save(d / "picture.png")
    for i, (p, _, _) in enumerate(samples, 1):
        p.save(d / f"sample-{i}.png")
    for i, (_, p) in enumerate(hovers, 1):
        p.save(d / f"hover-{i}.png")
    (d / "pictures.json").write_text(pictures if pictures is not None else json.dumps(
        {"version": 1, "screen": "picture.png",
         "samples": [{"file": f"sample-{i}.png", "x": x, "y": y}
                     for i, (_, x, y) in enumerate(samples, 1)],
         "hovers": [{"file": f"hover-{i}.png", "box": list(b)} for i, (b, _) in enumerate(hovers, 1)]}))
    r = subprocess.run([sb, "a11y", "contrast", "--from", str(d), *args], capture_output=True,
                       text=True, env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(tmp)})
    return r.returncode, r.stdout.splitlines(), r.stderr


W = window()
BOX = [10, 10, 60, 20]
FAINT = Pic().text(BOX, (0x99,) * 3)
DARK = Pic().text(BOX, BLACK)


def label(**more):
    return node("frame/label[0]", "label", "Hi", **{"bounds": BOX, **more})


for case, nodes, screen, args, want in [
    ("text that passes", [W, label()], DARK, ["--passes"],
     (0, ["frame/label[0]: text passes at 21.00:1, #000000 on #ffffff (at least 4.5)"])),
    ("text that fails", [W, label()], FAINT, [],
     (1, ["frame/label[0]: text 2.84:1, #999999 on #ffffff (at least 4.5)"])),
    ("large text, held to 3:1", [W, label(large=True)], FAINT, [],
     (1, ["frame/label[0]: text 2.84:1, #999999 on #ffffff (at least 3, large text)"])),
    ("GTK 3 text drawn lighter than its own color", [W, label(color="#555555")], FAINT, [],
     (1, ["frame/label[0]: text 2.84:1, #999999 on #ffffff (at least 4.5); drawn lighter than "
          "its color, #555555, which is 7.45:1 (light text, or opacity)"])),
    ("an image, held to 3:1", [W, node("frame/image[0]", "image", "Logo", bounds=BOX)], FAINT, [],
     (1, ["frame/image[0]: graphics 2.84:1, #999999 on #ffffff (at least 3)"])),
    ("what's left out: disabled, a check box, GTK 3's switch, a field, what isn't showing",
     [W, label(states=["disabled"]),
      node("frame/check box[1]", "check box", "Agree", bounds=BOX),
      node("frame/toggle button[2]", "toggle button", "Wi-Fi", bounds=BOX, switch=True),
      node("frame/text[3]", "text", "Notes", ["editable"], bounds=BOX),
      node("frame/label[4]", "label", "Gone", bounds=BOX, showing=False)], FAINT, [], (0, [])),
    ("a control with nothing drawn",
     [W, node("frame/button[0]", "button", "Close", bounds=BOX)], Pic(), [],
     (1, ["frame/button[0]: text not seen: nothing drawn on #ffffff"])),
    ("no bounds: can't tell where it is", [W, label(bounds=None)], Pic(), [],
     (1, ["frame/label[0]: text not measured: can't tell where it is"])),
    ("no bounds, and not drawn", [W, label(bounds=None, drawn=False)], Pic(), [], (0, [])),
    ("too small to measure", [W, label(bounds=[10, 10, 4, 4])], Pic().fill(11, 11, 2, 2, BLACK),
     [], (0, ["frame/label[0]: text too small to measure, 4 pixels"])),
    ("in a modal window's program", [window(shut_by="Save as"), label()], FAINT, [],
     (0, ['frame/label[0]: text behind a modal dialog "Save as"'])),
    ("in an untitled modal window's program", [window(shut_by=""), label()], FAINT, [],
     (0, ['frame/label[0]: text behind a modal dialog ""'])),
    ("behind a modal dialog in its window",
     [W, label(), node("frame/dialog[1]", "dialog", "Settings", ["modal"], bounds=[0, 0, 200, 100])],
     FAINT, [], (0, ['frame/label[0]: text behind a modal dialog "Settings"'])),
    ("ignored by its path", [W, label()], FAINT, ["--ignore", r"^frame/label\["], (0, [])),
    ("ignored by its tree line", [W, label()], FAINT, ["--ignore", '^label "Hi"'], (0, [])),
    ("GTK 4's, a note", [window(toolkit="GTK 4.16.3"), label()], FAINT, [],
     (2, ["frame/label[0]: text not measured from a file: GTK 4 is measured live only"])),
]:
    got = contrast(nodes, screen, *args)
    check(got[:2] == want, f"contrast --from: {case}" + ("" if got[:2] == want else f": {got}"))

# A control drawn only with the pointer over it says how it is then.
st, out, _ = contrast([W, node("frame/button[0]", "button", "Close", bounds=BOX)], Pic(),
                      hovers=[(BOX, Pic(*BOX[2:]).text([0, 0, *BOX[2:]], BLACK))])
check((st, out) == (1, ["frame/button[0]: text not seen: nothing drawn on #ffffff; with the "
                        "pointer over it, 21.00:1, #000000 on #ffffff (at least 4.5)"]),
      f"contrast --from: a control drawn only with the pointer over it ({st}, {out})")

# A web page's text, measured run by run; one with text only in a field,
# none of it measured, is a note.
DOC = node("frame/document web[0]", "document web", "page", bounds=[0, 0, 200, 100])
PARA = node("frame/document web[0]/paragraph[0]", "paragraph", contents="Faint words",
            bounds=BOX, runs=[{"run": "Faint words", "look": {}, "bounds": BOX,
                               "dom": {"tag": "p", "id": "intro"}, "text": "Faint words"}],
            dom={"tag": "p", "id": "intro"})
st, out, _ = contrast([window(toolkit="Gecko 128.0"), DOC, PARA], FAINT)
check((st, out) == (1, ['frame/document web[0]/paragraph[0]: text 2.84:1, #999999 on #ffffff '
                        '(at least 4.5)  <- p#intro "Faint words"']),
      f"contrast --from: a page's text, by its runs ({st}, {out})")
st, out, _ = contrast([window(toolkit="Gecko 128.0"), DOC, dict(PARA, runs=[])], FAINT)
check((st, out) == (2, ["frame/document web[0]: text not measured: none of the page's text was"]),
      f"contrast --from: a page node none of whose runs were read, not measured ({st}, {out})")
st, out, err = contrast([window(toolkit="Chromium 120.0"), DOC,
                         node("frame/document web[0]/entry[0]", "entry", "Name", ["editable"],
                              bounds=BOX, filled=True)], FAINT)
check((st, out) == (2, ["frame/document web[0]: text not measured: none of the page's text was"])
      and "text in a field" in err, f"contrast --from: a page with text only in a field ({st}, {out})")

# Text blinking: changing, a note, failing only with --strict; failing at
# its best, a problem; one that's moved isn't measured where it was.
BLINK = [(DARK, 0, 0), (FAINT, 0, 0), (DARK, 0, 0)]
st, out, _ = contrast([W, label()], FAINT, samples=BLINK)
st2, _, _ = contrast([W, label()], FAINT, "--strict", samples=BLINK)
check((st, out, st2) == (0, ["frame/label[0]: text changing: 2.84:1 to 21.00:1 (at least 4.5)"], 1),
      f"contrast --from: text blinking, changing, failing with --strict ({st}, {out}, {st2})")
PALER = Pic().text(BOX, (0xbb,) * 3)
st, out, _ = contrast([W, label()], FAINT, samples=[(PALER, 0, 0)])
check((st, out) == (1, ["frame/label[0]: text 2.84:1 at best, changing from 1.91:1, "
                        "#999999 on #ffffff (at least 4.5)"]),
      f"contrast --from: text failing at its best ({st}, {out})")
st, out, _ = contrast([W, label(moved=True)], FAINT, samples=[(Pic(), 0, 0)])
check((st, out) == (1, ["frame/label[0]: text 2.84:1, #999999 on #ffffff (at least 4.5)"]),
      f"contrast --from: text moved, not measured where it was ({st}, {out})")
st, out, _ = contrast([W, label()], FAINT, samples=[(Pic(), 0, 0)])
check((st, out) == (1, ["frame/label[0]: text 2.84:1 at best, changing from 1.00:1, "
                        "#999999 on #ffffff (at least 4.5)"]),
      f"contrast --from: text blinked off, where it was, failing at its best ({st}, {out})")

# A button's edge, with --edges.
EDGE = Pic().fill(10, 10, 60, 20, (0xee,) * 3)
st, out, _ = contrast([W, node("frame/button[0]", "button", "Save", bounds=BOX)], EDGE,
                      "--edges", "3")
check(st == 1 and any(line.startswith("frame/button[0]: edge 1.1") for line in out),
      f"contrast --from --edges: a button with no edge to speak of ({st}, {out})")

# --json, as the live one has it: no depth, pid or what was read live.
st, out, _ = contrast([W, label(large=True, color="#555555")], FAINT, "--json")
j = json.loads(out[0]) if out else {}
check(st == 0 and [set(n) for n in j.get("problems", [])] == [
    {"role", "name", "description", "states", "path", "bounds", "problem"}],
      f"contrast --from --json: no depth, pid or saved fields ({st}, {out})")

# A program that didn't answer: not all checked.
st, out, err = contrast([W, label(), node("application", "application", depth=0, pid=42,
                                         quiet=True)], FAINT)
check(st == 2 and out == ["frame/label[0]: text 2.84:1, #999999 on #ffffff (at least 4.5)"]
      and err.endswith("shotbox: not all checked: program 42 didn't answer: busy, or hung\n"),
      f"contrast --from: a program that didn't answer, not all checked ({st}, {out}, {err!r})")

for case, kw, said in [
    ("a tree that isn't one", {"tree": "{"}, "isn't a tree saved by a11y tree --json"),
    ("a field of the wrong type", {"tree": json.dumps([dict(W, switch=False)])},
     "isn't a tree saved by a11y tree --json"),
    ("a color that isn't one", {"tree": json.dumps([dict(W, color="red")])},
     "isn't a tree saved by a11y tree --json"),
    ("pictures.json of another version", {"pictures": json.dumps(
        {"version": 2, "screen": "picture.png", "samples": [], "hovers": []})},
     "isn't what contrast --save writes"),
    ("a picture that isn't there", {"pictures": json.dumps(
        {"version": 1, "screen": "none.png", "samples": [], "hovers": []})},
     "isn't a picture contrast --save wrote"),
    ("a picture outside the directory", {"pictures": json.dumps(
        {"version": 1, "screen": "../picture.png", "samples": [], "hovers": []})},
     "isn't what contrast --save writes"),
    ("a program that didn't answer before any window", {"tree": json.dumps(
        [node("application", "application", depth=0, pid=42, quiet=True), label()])},
     "isn't a tree saved by a11y tree --json"),
    ("a path step with no index", {"tree": json.dumps(
        [window(toolkit="GTK 4.16.3"), node("frame/panel", "panel", bounds=[0, 0, 200, 100]),
         node("frame/dialog", "dialog", "D", bounds=[0, 0, 200, 100])])},
     "isn't a tree saved by a11y tree --json"),
    ("a picture named as ImageMagick's own", {"pictures": json.dumps(
        {"version": 1, "screen": "xc:red", "samples": [], "hovers": []})},
     "isn't what contrast --save writes"),
    ("a picture named with a part of it", {"pictures": json.dumps(
        {"version": 1, "screen": "picture.png[1x1+0+0]", "samples": [], "hovers": []})},
     "isn't what contrast --save writes"),
    ("a hover not the size of its box", {"hovers": [(BOX, Pic(5, 5))]},
     "isn't a picture contrast --save wrote"),
    ("a sample not holding what's measured", {"samples": [(Pic(20, 20), 150, 50)]},
     "a sample doesn't hold all that's measured"),
]:
    st, out, err = contrast([W, label()], FAINT, **kw)
    check(st == 2 and not out and said in err and "Traceback" not in err,
          f"contrast --from: {case}, said ({st}, {err!r})")

for flag in (["--window", "w"], ["--save", str(tmp / "again")]):
    r = subprocess.run([sb, "a11y", "contrast", "--from", str(tmp), *flag], capture_output=True,
                       text=True)
    check(r.returncode == 2 and "takes no --window or --save" in r.stderr,
          f"contrast --from: no {flag[0]} ({r.stderr!r})")

sys.exit(bool(fails))
