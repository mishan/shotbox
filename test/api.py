"""The Python API, and parking the pointer: a GTK button, hovered, then
not. Run by test/run.sh; prints ok/FAIL lines like it."""

import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import shotbox  # noqa: E402
from shotbox import x  # noqa: E402

BUTTON = """
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
w = Gtk.Window(title="shotbox-button")
w.set_default_size(200, 120)
w.move(0, 0)
w.add(Gtk.Button(label="hover me"))
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
with shotbox.Session(size=(640, 480)) as s:
    s.spawn([sys.executable, "-c", BUTTON])
    w = s.wait_window("shotbox-button")
    check(w[2] > 1 and w[3] > 1, "a Session waits for a window, and says where it is")
    s.move(630, 470)
    s.wait_stable(window="shotbox-button")
    s.capture(tmp / "rest.png", window="shotbox-button")
    s.move(w[2] // 2, w[3] // 2, window="shotbox-button")
    s.wait_stable(window="shotbox-button")
    s.capture(tmp / "hover.png", window="shotbox-button")
    check(x.compare(tmp / "rest.png", tmp / "hover.png") > 0, "hovering the button shows")
    s.capture(tmp / "parked.png", window="shotbox-button", park=True)
    check(x.compare(tmp / "rest.png", tmp / "parked.png") == 0,
          "capture(park=True) takes it as if never hovered")
    s.failed = str(tmp / "failed.png")
    try:
        s.wait_window("never", timeout=0.5)
        check(False, "a failed wait raises")
    except shotbox.SessionError as e:
        check("failed.png" in str(e) and (tmp / "failed.png").exists(),
              "a failed wait raises, with a picture of the screen")

here = subprocess.run(
    [sys.argv[1], "run", "--env", f"PYTHONPATH={Path(__file__).resolve().parent.parent}", "--",
     sys.executable, "-c", "import shotbox; s = shotbox.here(); print(s.xt.width, s.xt.height)"],
    capture_output=True, text=True).stdout.strip()
check(here == "1280 800", f"here() is the display it's inside ({here})")
sys.exit(1 if fails else 0)
