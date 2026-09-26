"""A terminal to take pictures of: VTE (GNOME Terminal's, Tilix's and Ptyxis's
engine) in a plain window, colored by a scheme file, driven by steps.

    shotbox term --scheme dark.json --size 88x24 \\
        --when 'Welcome' --type '/join #test\\r' --sleep 1 -- irssi

Steps run in order: --when REGEX waits until the screen's text matches,
--type TEXT types it as if at the keyboard (\\r is Enter, \\e is Escape),
--sleep SECS waits. When the last step is done the terminal writes
$SHOTBOX_SCRATCH/ready, which `shotbox shoot --wait ready` waits for, so the
picture is taken when the screen is right rather than after a guess.

--log FILE also keeps every byte the program wrote, escape codes and all, via
script(1). Colors in a screenshot are hard to check by eye; in the log they
are text: grep it for 38;2;255;45;149.

The scheme is JSON: Tilix's scheme format as is, or just
{"foreground", "background", "cursor", "palette": [16 colors]}. The cursor
doesn't blink, so it's never caught mid-blink.
"""

import argparse
import json
import os
import re
import shlex
import sys
from pathlib import Path


class Step(argparse.Action):
    def __call__(self, parser, ns, value, option):
        ns.steps = (ns.steps or []) + [(self.dest, value)]


def parse(argv):
    p = argparse.ArgumentParser(prog="shotbox term", description=__doc__.split("\n\n")[0])
    p.add_argument("--scheme", help="colors: a Tilix scheme or {foreground, background, cursor, palette}")
    p.add_argument("--size", default="80x24", help="columns x rows (80x24)")
    p.add_argument("--font", default="Monospace 11")
    p.add_argument("--title", default="shotbox-term", help="the window's name, for --window")
    p.add_argument("--log", help="keep the program's raw output here")
    p.add_argument("--timeout", type=float, default=30, help="how long a --when may wait (30s)")
    p.add_argument("--when", action=Step, dest="when", metavar="REGEX")
    p.add_argument("--type", action=Step, dest="type", metavar="TEXT")
    p.add_argument("--sleep", action=Step, dest="sleep", metavar="SECS")
    p.set_defaults(steps=[])
    cmd = []
    if "--" in argv:
        i = argv.index("--")
        argv, cmd = argv[:i], argv[i + 1:]
    args = p.parse_args(argv)
    args.cmd = cmd
    if not args.cmd:
        p.error("no command given, after --")
    return args


def load_scheme(path):
    s = json.loads(Path(path).read_text())
    return {
        "foreground": s.get("foreground") or s["foreground-color"],
        "background": s.get("background") or s["background-color"],
        "cursor": s.get("cursor") or s.get("cursor-background-color"),
        "palette": s["palette"],
        "bold": s.get("bold-color") if s.get("use-bold-color") else None,
    }


def unescape(text):
    return (text.replace("\\r", "\r").replace("\\n", "\n").replace("\\t", "\t")
                .replace("\\e", "\x1b").replace("\\\\", "\\"))


def main(argv):
    args = parse(argv)

    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    gi.require_version("Vte", "2.91")
    from gi.repository import Gdk, GLib, Gtk, Pango, Vte

    def rgba(h):
        c = Gdk.RGBA()
        c.parse(h)
        return c

    term = Vte.Terminal()
    term.set_font(Pango.FontDescription(args.font))
    term.set_cursor_blink_mode(Vte.CursorBlinkMode.OFF)
    term.set_audible_bell(False)
    cols, rows = map(int, args.size.split("x"))
    term.set_size(cols, rows)
    if args.scheme:
        s = load_scheme(args.scheme)
        term.set_colors(rgba(s["foreground"]), rgba(s["background"]),
                        [rgba(c) for c in s["palette"]])
        if s["cursor"]:
            term.set_color_cursor(rgba(s["cursor"]))
        if s["bold"]:
            term.set_color_bold(rgba(s["bold"]))

    cmd = args.cmd
    if args.log:
        cmd = ["script", "-q", "-f", "-e", "-O", os.path.abspath(args.log),
               "-c", shlex.join(cmd)]
    term.spawn_async(Vte.PtyFlags.DEFAULT, None, cmd, None,
                     GLib.SpawnFlags.SEARCH_PATH, None, None, -1, None, None)

    def text():
        try:
            return term.get_text_format(Vte.Format.TEXT) or ""
        except AttributeError:
            return term.get_text()[0] or ""

    steps = list(args.steps)
    state = {"since": GLib.get_monotonic_time()}

    def fail(msg):
        sys.stderr.write(f"shotbox term: {msg}\n--- the screen ---\n{text()}\n")
        Gtk.main_quit()
        state["status"] = 2
        return False

    def tick():
        if not steps:
            scratch = os.environ.get("SHOTBOX_SCRATCH")
            if scratch:
                Path(scratch, "ready").touch()
            return False
        kind, value = steps[0]
        now = GLib.get_monotonic_time()
        if kind == "when":
            if not re.search(value, text()):
                if (now - state["since"]) / 1e6 > args.timeout:
                    return fail(f"gave up after {args.timeout:g}s waiting for {value!r}")
                return True
        elif kind == "type":
            term.feed_child(unescape(value).encode())
        elif kind == "sleep":
            if (now - state["since"]) / 1e6 < float(value):
                return True
        steps.pop(0)
        state["since"] = now
        return True

    win = Gtk.Window(title=args.title)
    win.add(term)
    win.connect("destroy", Gtk.main_quit)
    # No window manager hands out focus, so take it: an unfocused terminal
    # draws a hollow cursor.
    win.connect("map-event", lambda w, e: w.get_window().focus(Gdk.CURRENT_TIME))
    win.show_all()
    term.grab_focus()
    GLib.timeout_add(100, tick)
    Gtk.main()
    return state.get("status", 0)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
