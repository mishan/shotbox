#!/usr/bin/env python3
"""a11y contrast --from, on trees and pictures made by hand from what each
rule says: no display, accessibility bus or PyGObject (its import is
blocked): test/contrast_test.py SHOTBOX."""

import base64
import json
import subprocess
import sys

import contrast_fixture
from contrast_fixture import BLACK, Pic, check, contrast, node, sb, tmp, window


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
    ("a GTK 4 dialog that isn't a layer, under a box as big as its window",
     [window(toolkit="GTK 4.16.3"), node("frame/panel[0]", "panel", bounds=[0, 0, 200, 100]),
      node("frame/panel[0]/panel[0]", "panel", bounds=[0, 0, 200, 100]),
      node("frame/panel[0]/panel[0]/dialog[1]", "dialog", "D", bounds=BOX)], FAINT, [], (0, [])),
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

# A field with no edge of its own, in a box that draws one round it.
FRAMED = Pic().fill(20, 20, 100, 1, BLACK).fill(20, 59, 100, 1, BLACK) \
    .fill(20, 20, 1, 40, BLACK).fill(119, 20, 1, 40, BLACK)
st, out, _ = contrast([W, node("frame/panel[0]", "panel", bounds=[20, 20, 100, 40]),
                       node("frame/panel[0]/text[0]", "text", "Notes", ["editable"],
                            bounds=[24, 24, 92, 32])], FRAMED, "--edges", "3", "--passes")
check((st, [line[:63] for line in out]) == (
    0, ["frame/panel[0]/text[0]: edge passes, drawn by what it's in; its"]),
      f"contrast --from --edges: a field's edge drawn by what it's in ({st}, {out})")

# A window wider than the screen: what's past its edge isn't measured.
st, out, _ = contrast([window(window=[0, 0, 300, 100], bounds=[0, 0, 300, 100]),
                       label(bounds=[150, 10, 100, 20]),
                       node("frame/button[1]", "button", "There", bounds=[220, 10, 60, 20])],
                      Pic(), "--edges", "3")
check((st, sorted(out)) == (0, ["frame/button[1]: edge not measured: outside the screen",
                                "frame/button[1]: text not measured: outside the screen",
                                "frame/label[0]: text not measured: partly outside the screen"]),
      f"contrast --from: past the screen's edge, not measured ({st}, {out})")


# Behind a modal dialog, each case a shape the rule names, in a GTK 4 tree,
# where with --strict all that isn't behind one fails, being a note.
FULL = [0, 0, 200, 100]


def behind(*more, toolkit="GTK 4.16.3"):
    """What's said behind a modal dialog, and what fails, in a window of
    `toolkit` whose content holds a page with a faint label, then `more`."""
    _, out, _ = contrast([window(toolkit=toolkit), node("frame/panel[0]", "panel", bounds=FULL),
                          node("frame/panel[0]/panel[0]", "panel", bounds=FULL),
                          node("frame/panel[0]/panel[0]/label[0]", "label", "Faint words", bounds=BOX),
                          *more], FAINT, "--strict", "--json")
    j = json.loads(out[0]) if out else {}
    return (sorted((n["name"], n["behind"]) for n in j.get("behind", [])),
            sorted(n["name"] for n in j.get("problems", [])))


for case, more, kw, want in [
    ("libadwaita 1.10's dialog, laid over the content", [node("frame/panel[0]/dialog[1]", "dialog", "Reply", bounds=FULL)],
     {}, ([("Faint words", 'text behind a modal dialog "Reply"')], [])),
    ("only what's drawn under it", [node("frame/panel[0]/dialog[1]", "dialog", "Reply", bounds=FULL),
                                   node("frame/panel[0]/label[2]", "label", "After", bounds=BOX)],
     {}, ([("Faint words", 'text behind a modal dialog "Reply"')], ["After"])),
    ("libadwaita 1.5's sheet, three down from a layer, named by the first name in it",
     [node("frame/panel[0]/panel[1]", "panel", bounds=FULL),
      node("frame/panel[0]/panel[1]/panel[0]", "panel", bounds=FULL),
      node("frame/panel[0]/panel[1]/panel[0]/panel[0]", "panel", bounds=FULL),
      node("frame/panel[0]/panel[1]/panel[0]/panel[0]/dialog[1]", "dialog", bounds=BOX),
      node("frame/panel[0]/panel[1]/panel[0]/panel[0]/dialog[1]/label[0]", "label", "Notes", bounds=BOX)],
     {}, ([("Faint words", 'text behind a modal dialog "Notes"')], ["Notes"])),
    ("libadwaita 1.5's alert dialog, laid over the content",
     [node("frame/panel[0]/alert[1]", "alert", "Discard?", bounds=FULL)],
     {}, ([("Faint words", 'text behind a modal dialog "Discard?"')], [])),
    ("an error label", [node("frame/panel[0]/panel[0]/alert[1]", "alert", "Wrong password", bounds=BOX)],
     {}, ([], ["Faint words"])),
    ("a box or popover given a dialog's role, after the content",
     [node("frame/panel[0]/dialog[1]", "dialog", "Find", bounds=BOX)], {}, ([], ["Faint words"])),
    ("after a stack's page GTK lists twice, with no bounds",
     [node("frame/panel[0]/panel[1]", "panel"), node("frame/panel[0]/alert[2]", "alert", "Offline", bounds=FULL)],
     {}, ([], ["Faint words"])),
    ("after a banner folded away, showing but no height",
     [node("frame/panel[0]/grouping[1]", "grouping", "Offline", bounds=[0, 0, 200, 0]),
      node("frame/panel[0]/alert[2]", "alert", "Offline", bounds=FULL)], {}, ([], ["Faint words"])),
    ("after a page not showing", [node("frame/panel[0]/panel[1]", "panel", bounds=FULL, showing=False),
                                  node("frame/panel[0]/alert[2]", "alert", "Offline", bounds=FULL)],
     {}, ([], ["Faint words"])),
    ("a dialog not showing", [node("frame/panel[0]/dialog[1]", "dialog", "Reply", bounds=FULL, showing=False)],
     {}, ([], ["Faint words"])),
    ("an alert in a box laid over the rest", [node("frame/panel[0]/panel[1]", "panel", bounds=FULL),
                                              node("frame/panel[0]/panel[1]/alert[0]", "alert", "Lost connection",
                                                   bounds=BOX)], {}, ([], ["Faint words"])),
    ("dialogs over dialogs: the last in front",
     [node("frame/panel[0]/dialog[1]", "dialog", "First", bounds=FULL),
      node("frame/panel[0]/dialog[1]/label[0]", "label", "In first", bounds=BOX),
      node("frame/panel[0]/dialog[2]", "dialog", "Second", bounds=FULL)],
     {}, ([("Faint words", 'text behind a modal dialog "Second"'),
           ("In first", 'text behind a modal dialog "Second"')], [])),
    ("GTK 3's dialog, not modal", [node("frame/panel[0]/dialog[1]", "dialog", "Find", bounds=FULL)],
     {"toolkit": "gtk 3.24.49"}, ([], ["Faint words"])),
]:
    got = behind(*more, **kw)
    check(got == want, f"contrast --from: behind a modal dialog: {case}" + ("" if got == want else f": {got}"))

# GTK 4's, from what the live run read and drew: its text looked for in
# the box GTK 4.14 to 4.14.5 says, where it's drawn, by its shape.
def shape(w, h):
    """The coverage of Pic.text's strokes in a box `w` by `h`, as
    text_shapes() draws text: with two blank columns each side."""
    cover = bytearray((w + 4) * h)
    for i in range(2, w - 4, 6):
        for y in range(2, max(h - 2, 3)):
            cover[y * (w + 4) + i + 2:y * (w + 4) + i + 5] = b"\xff" * 3
    return [w + 4, h, base64.b64encode(cover).decode()]


ATTRS = {"family-name": "Sans", "size": "11", "run-end": "2"}
G4 = [window(toolkit="GTK 4.14.0"), label()]
DRAWN = Pic().text([14, 12, 40, 14], (0x99,) * 3)


def gtk4(gone=None, raised=True, **reads):
    return {"version": 1, "trusted": False, "cannot": None, "raised": raised, "gone": gone,
            "reads": {"relative": {}, "pages": {}, "fonts": {"frame/label[0]": ATTRS},
                      "laid": {"frame/label[0]": None},
                      "paged": {}, "popups": {"frame/label[0]": False}, "texts": {}, **reads}}


SHAPES = {"version": 1, "shapes": [{"text": "Hi", "attrs": ATTRS, "dy": 0, "kinds": [[shape(40, 14)]]}]}
for case, files, want in [
    ("found where it's drawn in its box", [("gtk4.json", gtk4()), ("shapes.json", SHAPES)],
     (1, ["frame/label[0]: text 2.84:1, #999999 on #ffffff (at least 4.5); found 4,2 px from "
          "the corner of the box GTK 4.14.0 says"])),
    ("out of time where the live run was", [("gtk4.json", gtk4(gone=1)), ("shapes.json", SHAPES)],
     (2, ["frame/label[0]: text not measured: no time left to look for it"])),
]:
    got = contrast(G4, DRAWN, files=files)
    check(got[:2] == want, f"contrast --from, GTK 4: {case}" + ("" if got[:2] == want else f": {got}"))

# A field whose text is drawn where the label's is found, which then can't
# be told for the label's: what's typed, its font and its shape, from
# fields.json. Not raised, the label is a note, which says why.
FIELD = node("frame/text[1]", "text", "Notes", ["editable"], bounds=BOX)
TYPED = {"version": 1, "reads": dict({k: {} for k in gtk4()["reads"]}, fonts={"frame/text[1]": ATTRS},
                                     texts={"frame/text[1]": ["Wisteria"]}),
         "shapes": [{"text": "Wisteria", "attrs": ATTRS, "dy": 0, "kinds": [[shape(40, 14)]]}]}
st, out, err = contrast(G4 + [FIELD], DRAWN, files=[("gtk4.json", gtk4(raised=False)),
                                                    ("shapes.json", SHAPES), ("fields.json", TYPED)])
check(st == 2 and out == ['frame/label[0]: text not measured: GTK 4 reports its position wrong (another '
                          'node\'s text matches there too: the text "Notes", whose text is "Wisteria")'],
      f"contrast --from, GTK 4: a field's text, from fields.json, matching where the label's is ({st}, {out})")
st, out, err = contrast(G4 + [FIELD], DRAWN, files=[("gtk4.json", gtk4(raised=False)),
                                                    ("shapes.json", SHAPES)])
check(st == 2 and not out and "frame/text[1]'s texts" in err,
      f"contrast --from, GTK 4: a field's text, without fields.json, not read ({st}, {out}, {err!r})")

for case, files, said in [
    ("a read the live run didn't make", [("gtk4.json", gtk4(fonts={})), ("shapes.json", SHAPES)],
     "the saved run didn't read frame/label[0]'s font"),
    ("a shape it didn't draw", [("gtk4.json", gtk4()), ("shapes.json", {"version": 1, "shapes": []})],
     "the saved run didn't read a text's shape"),
    ("gtk4.json, not JSON", [("gtk4.json", "{"), ("shapes.json", SHAPES)], "isn't what contrast --save writes"),
    ("gtk4.json, null", [("gtk4.json", "null"), ("shapes.json", SHAPES)], "gtk4.json isn't what contrast --save writes"),
    ("fields.json, null", [("gtk4.json", gtk4()), ("shapes.json", SHAPES), ("fields.json", "null")],
     "fields.json isn't what contrast --save writes"),
    ("gtk4.json of another version", [("gtk4.json", dict(gtk4(), version=2)), ("shapes.json", SHAPES)],
     "isn't what contrast --save writes"),
    ("a read of a node not in the tree", [("gtk4.json", gtk4(popups={"frame/label[9]": False})),
                                          ("shapes.json", SHAPES)], "isn't what contrast --save writes"),
    ("a read of the wrong type", [("gtk4.json", gtk4(relative={"frame/label[0]": "near"})),
                                  ("shapes.json", SHAPES)], "isn't what contrast --save writes"),
    ("no shapes.json", [("gtk4.json", gtk4())], "can't read"),
    ("a shape not as big as it says", [("gtk4.json", gtk4()), ("shapes.json", {"version": 1, "shapes": [
        {"text": "Hi", "attrs": ATTRS, "dy": 0, "kinds": [[[44, 14, "AAAA"]]]}]})],
     "shapes.json isn't what contrast --save writes"),
    ("a node at a middle that isn't a path", [("gtk4.json", gtk4(paged={"frame/label[0]": []})),
                                              ("shapes.json", SHAPES)], "isn't what contrast --save writes"),
    ("shapes.json, not an object", [("gtk4.json", gtk4()), ("shapes.json", [1])],
     "isn't what contrast --save writes"),
    ("an empty group of shapes", [("gtk4.json", gtk4()), ("shapes.json", {"version": 1, "shapes": [
        {"text": "Hi", "attrs": ATTRS, "dy": 0, "kinds": [[]]}]})], "isn't what contrast --save writes"),
    ("no shapes at all, but not null", [("gtk4.json", gtk4()), ("shapes.json", {"version": 1, "shapes": [
        {"text": "Hi", "attrs": ATTRS, "dy": 0, "kinds": []}]})], "isn't what contrast --save writes"),
    ("gtk4.json with no gone", [("gtk4.json", {k: v for k, v in gtk4().items() if k != "gone"}),
                                ("shapes.json", SHAPES)], "isn't what contrast --save writes"),
    ("gtk4.json with no cannot", [("gtk4.json", {k: v for k, v in gtk4().items() if k != "cannot"}),
                                  ("shapes.json", SHAPES)], "isn't what contrast --save writes"),
    ("a shape with no kinds", [("gtk4.json", gtk4()), ("shapes.json", {"version": 1, "shapes": [
        {"text": "Hi", "attrs": ATTRS, "dy": 0}]})], "isn't what contrast --save writes"),
    ("fields.json with no shapes", [("gtk4.json", gtk4()), ("shapes.json", SHAPES),
                                    ("fields.json", {"version": 1, "reads": gtk4()["reads"]})],
     "isn't what contrast --save writes"),
    ("a field's shape not as big as it says", [("gtk4.json", gtk4()), ("shapes.json", SHAPES), (
        "fields.json", {"version": 1, "reads": {k: {} for k in gtk4()["reads"]}, "shapes": [
            {"text": "Hi", "attrs": ATTRS, "dy": 0, "kinds": [[[44, 14, "AAAA"]]]}]})],
     "fields.json isn't what contrast --save writes"),
    ("a read in both gtk4.json and fields.json", [("gtk4.json", gtk4()), ("shapes.json", SHAPES), (
        "fields.json", {"version": 1, "reads": dict({k: {} for k in gtk4()["reads"]},
                                                    fonts={"frame/label[0]": ATTRS}), "shapes": []})],
     "fields.json isn't what contrast --save writes"),
]:
    st, out, err = contrast(G4, DRAWN, files=files)
    check(st == 2 and not out and said in err and "Traceback" not in err,
          f"contrast --from, GTK 4: {case}, said ({st}, {out}, {err!r})")

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

r = subprocess.run([sb, "a11y", "contrast", "--help"], capture_output=True, text=True)
check("GTK 4's isn't measured" not in r.stdout and "gtk4.json" in r.stdout,
      f"contrast --help: --from measures GTK 4 from what was saved with it ({r.stdout[-400:]!r})")

(tmp / "full").mkdir()
(tmp / "full" / "tree.json").write_text("[]")
r = subprocess.run([sb, "a11y", "contrast", "--save", str(tmp / "full")], capture_output=True,
                   text=True)
check(r.returncode == 2 and "isn't empty" in r.stderr and (tmp / "full" / "tree.json").read_text() == "[]",
      f"contrast --save: into a directory that isn't empty, refused before it's touched ({r.stderr!r})")

for flag in (["--window", "w"], ["--save", str(tmp / "again")]):
    r = subprocess.run([sb, "a11y", "contrast", "--from", str(tmp), *flag], capture_output=True,
                       text=True)
    check(r.returncode == 2 and "takes no --window or --save" in r.stderr,
          f"contrast --from: no {flag[0]} ({r.stderr!r})")

sys.exit(bool(contrast_fixture.fails))
