"""A session's display, from Python: waiting on it, driving it, and taking
pictures of it. What the `shotbox wait`, `capture`, `key`, `click` and
friends commands do, without a process for each step.

Inside `shotbox run`, the display is the one in the environment:

    import shotbox
    screen = shotbox.here()
    screen.wait_window("Text Editor")
    screen.click(40, 60, window="Text Editor")
    screen.wait_stable(window="Text Editor")
    screen.capture("editor.png", window="Text Editor", park=True)

A Session is a Screen too, for a script that starts its own.

Anything that fails raises SessionError, saying what. With `failed` set (or
$SHOTBOX_FAILED), a failure first leaves a picture of the screen there.
"""

import os
import time
from pathlib import Path

from . import wl, wlinput, x, xtest


class SessionError(RuntimeError):
    pass


def wait_for(what, test, timeout, interval=0.1, alive=None):
    """Poll `test()` until it returns something true, or fail saying what."""
    end = time.monotonic() + timeout
    while True:
        got = test()
        if got:
            return got
        if alive is not None and alive.poll() is not None:
            raise SessionError(f"gave up waiting for {what}: the program exited "
                               f"(status {alive.returncode})")
        if time.monotonic() > end:
            raise SessionError(f"gave up waiting for {what} after {timeout:g}s")
        time.sleep(interval)


class Screen:
    """The display in `env` (DISPLAY, XAUTHORITY and SHOTBOX_SCRATCH; the
    process's own environment by default)."""

    def __init__(self, env=None, failed=None):
        self.env = dict(os.environ if env is None else env)
        self.failed = failed or self.env.get("SHOTBOX_FAILED")
        self._x = None

    # --- failing --------------------------------------------------------------

    def fail(self, message):
        """Raise SessionError(message), first taking a picture of the screen
        to `failed` if it's set, and saying where."""
        if self.failed and x.try_capture(self.env, self.failed, self.backend):
            message += f"; the screen then: {self.failed}"
        raise SessionError(message)

    def until(self, what, test, timeout=30, alive=None):
        """Poll `test()` until it returns something true, and return that;
        or fail, saying it gave up waiting for `what`. With `alive` (a
        process), fail sooner if it exits."""
        try:
            return wait_for(what, test, timeout, alive=alive)
        except SessionError as e:
            self.fail(str(e))

    # --- waiting --------------------------------------------------------------

    def test(self, kind, arg="", window=None):
        """What to say, and what to poll, for a wait: window (a regex), port,
        file, ready, or stable (seconds; `window` to watch just that one)."""
        if kind == "window":
            return f"a window named {arg!r}", lambda: self.backend.find_window(self.env, arg)
        if kind == "port":
            return f"port {arg}", lambda: x.port_open(int(arg))
        if kind == "file":
            return f"{arg} to exist", lambda: Path(arg).exists()
        if kind == "ready":
            ready = Path(self.env["SHOTBOX_SCRATCH"]) / "ready"
            return "the program to say it's ready", ready.exists
        if kind == "stable":
            quiet = float(arg) if arg else 0.5
            where = f"the window {window!r}" if window else "the display"
            return (f"{where} to hold still for {quiet:g}s",
                    x.Still(self.env, window, quiet, self.backend))
        raise SessionError(f"don't know how to wait for {kind!r} "
                           "(window, port, file, ready or stable)")

    def wait_window(self, name, timeout=30):
        """Wait for a viewable window whose name matches `name` (a regex,
        matched in full); its (id, name, width, height, x, y)."""
        return self.until(*self.test("window", name), timeout)

    def wait_port(self, port, timeout=30):
        self.until(*self.test("port", port), timeout)

    def wait_file(self, path, timeout=30):
        self.until(*self.test("file", path), timeout)

    def wait_ready(self, timeout=30):
        """Wait for $SHOTBOX_SCRATCH/ready, which `shotbox term` writes."""
        self.until(*self.test("ready"), timeout)

    def wait_stable(self, seconds=0.5, window=None, timeout=30):
        """Wait until the display, or the window named `window`, has looked
        the same for `seconds`: for the paint after a click, a panel sliding
        in, a toast going away."""
        self.until(*self.test("stable", seconds, window), timeout)

    # --- windows and pictures -------------------------------------------------

    def window(self, name):
        """The window named `name` (a regex, matched in full), or fail."""
        w = self.backend.find_window(self.env, name)
        if not w:
            self.fail(f"no window named {name!r}")
        return w

    def capture(self, out, window=None, crop=None, park=False):
        """A picture of the display, or of the window named `window`, to
        `out` (a PNG), then cropped (WxH+X+Y). With `park`, the pointer
        goes out of the way first, so nothing shows its hover."""
        if park:
            self.park()
        self.backend.capture(self.env, out, window=self.window(window) if window else None,
                             crop=crop)
        return Path(out)

    # --- input ----------------------------------------------------------------

    @property
    def wayland(self):
        """Whether this is a Wayland session (under sway) rather than X11."""
        return bool(self.env.get("SWAYSOCK"))

    @property
    def backend(self):
        """The module that finds windows and takes pictures: wl or x."""
        return wl if self.wayland else x

    @property
    def xt(self):
        """The input connection, opened on first use and kept: XTEST on
        X11, a virtual keyboard and pointer on Wayland."""
        if self._x is None:
            self._x = (wlinput if self.wayland else xtest).Display(self.env)
        return self._x

    def _at(self, px, py, window):
        if not window:
            return px, py
        w = self.window(window)
        return w[4] + px, w[5] + py

    def key(self, *chords):
        """Press and release each chord in turn: ctrl+comma, Return,
        alt+shift+Tab."""
        for c in chords:
            self.xt.chord(c)

    def type(self, text):
        """Type ASCII text into whatever has the keyboard focus."""
        self.xt.type(text)

    def move(self, px, py, window=None):
        """Move the pointer to X, Y on the screen, or inside `window`."""
        self.xt.move(*self._at(px, py, window))

    def click(self, px, py, window=None, button=1, double=False):
        self.xt.click(*self._at(px, py, window), button=button, count=2 if double else 1)

    def drag(self, x1, y1, x2, y2, window=None, button=1):
        dx, dy = self._at(0, 0, window)
        self.xt.drag(x1 + dx, y1 + dy, x2 + dx, y2 + dy, button=button)

    def park(self, settle=2.0):
        """Move the pointer to the screen's bottom-right corner, off whatever
        it was hovering, then wait up to `settle` seconds for the display to
        hold still, for the repaint. A display that keeps changing (a video,
        a spinner) isn't a failure here: it's taken as it is."""
        self.xt.move(self.xt.width - 1, self.xt.height - 1)
        if settle:
            try:
                wait_for("", x.Still(self.env, quiet=0.3, backend=self.backend), settle)
            except SessionError:
                pass

    def close(self):
        if self._x is not None:
            self._x.close()
            self._x = None


def here():
    """The display of the `shotbox run` this is inside."""
    if not os.environ.get("SHOTBOX_SCRATCH"):
        raise SessionError("not inside a shotbox session")
    return Screen()
