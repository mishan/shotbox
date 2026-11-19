"""What test/contrast_test.py and test/contrast_gtk4_test.py share: a run
of a11y contrast --from on a directory made by hand, with no display,
accessibility bus or PyGObject (its import is blocked)."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sb = sys.argv[1]
fails = 0
tmp = Path(tempfile.mkdtemp())
(tmp / "gi").mkdir()
(tmp / "gi" / "__init__.py").write_text("raise ImportError('PyGObject blocked by contrast_fixture.py')\n")
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
    return node("frame", "frame", "w", pid=7, toolkit=toolkit,
                **{"bounds": [0, 0, 200, 100], "window": [0, 0, 200, 100], **more})


def contrast(nodes, screen, *args, samples=(), hovers=(), pictures=None, tree=None, files=()):
    """contrast --from a directory of `nodes`, the `screen` picture,
    `samples` (Pic, x, y), `hovers` (box, Pic) and `files` (name, JSON):
    (status, lines, stderr)."""
    d = Path(tempfile.mkdtemp(dir=tmp))
    for name, o in files:
        (d / name).write_text(o if isinstance(o, str) else json.dumps(o))
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
                       text=True, env={"PATH": os.environ["PATH"], "PYTHONPATH": str(tmp)})
    return r.returncode, r.stdout.splitlines(), r.stderr
