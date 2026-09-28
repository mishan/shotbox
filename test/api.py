"""The Python API, the pointer, and parking it: a GTK button, hovered,
clicked, then not hovered, on X11 and, with sway and grim, on Wayland.
Run by test/run.sh; prints ok/FAIL lines like it."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import shotbox  # noqa: E402
from shotbox import x  # noqa: E402

BUTTON = """
import sys, gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
w = Gtk.Window(title="shotbox-button")
w.set_default_size(200, 120)
w.move(0, 0)
b = Gtk.Button(label="hover me")
b.connect("clicked", lambda b: open(sys.argv[1], "a").write("clicked\\n"))
w.add(b)
w.connect("destroy", Gtk.main_quit)
w.show_all()
Gtk.main()
"""

fails = 0


def check(cond, what):
    global fails
    print(("ok    " if cond else "FAIL  ") + what)
    fails += not cond


tmp = Path(tempfile.mkdtemp())


def pointer(on, **session):
    """Hover, click and park, in a session made with `session`."""
    d = tmp / on
    d.mkdir()
    with shotbox.Session(size=(640, 480), **session) as s:
        s.spawn([sys.executable, "-c", BUTTON, str(d / "clicks")])
        w = s.wait_window("shotbox-button")
        check(w[2] > 1 and w[3] > 1, f"{on}: a Session waits for a window, and says where it is")
        s.move(630, 470)
        s.wait_stable(window="shotbox-button")
        s.capture(d / "rest.png", window="shotbox-button")
        s.move(w[2] // 2, w[3] // 2, window="shotbox-button")
        s.wait_stable(window="shotbox-button")
        s.capture(d / "hover.png", window="shotbox-button")
        check(x.compare(d / "rest.png", d / "hover.png") > 0, f"{on}: hovering the button shows")
        s.click(w[2] // 2, w[3] // 2, window="shotbox-button")
        s.until("the click", lambda: (d / "clicks").exists(), timeout=5)
        check((d / "clicks").read_text() == "clicked\n", f"{on}: a click reaches the button")
        s.capture(d / "parked.png", window="shotbox-button", park=True)
        check(x.compare(d / "rest.png", d / "parked.png") == 0,
              f"{on}: capture(park=True) takes it as if never hovered")
        s.failed = str(d / "failed.png")
        try:
            s.wait_window("never", timeout=0.5)
            check(False, f"{on}: a failed wait raises")
        except shotbox.SessionError as e:
            check("failed.png" in str(e) and (d / "failed.png").exists(),
                  f"{on}: a failed wait raises, with a picture of the screen")


pointer("x11")
if shutil.which("sway") and shutil.which("grim"):
    pointer("wayland", wayland=True)
elif os.environ.get("SHOTBOX_WAYLAND") == "required":
    check(False, "wayland: the pointer, skipped: no sway or grim")
else:
    print("skip  wayland: the pointer: no sway or grim")

here = subprocess.run(
    [sys.argv[1], "run", "--env", f"PYTHONPATH={Path(__file__).resolve().parent.parent}", "--",
     sys.executable, "-c", "import shotbox; s = shotbox.here(); print(s.xt.width, s.xt.height)"],
    capture_output=True, text=True).stdout.strip()
check(here == "1280 800", f"here() is the display it's inside ({here})")
sys.exit(1 if fails else 0)
