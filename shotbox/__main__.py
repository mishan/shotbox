"""shotbox: reproducible screenshots of real programs, in a sealed session.

    shotbox shoot OUT.png [options] -- COMMAND...   run it, wait, take the picture
    shotbox run [options] -- COMMAND...             run it in a sealed session
    shotbox term [options] -- COMMAND...            a terminal to take pictures of
    shotbox wait window|port|file|ready|stable ARG  (inside a session) wait for it
    shotbox capture OUT.png [--window RE]           (inside a session) take a picture
    shotbox key CHORD...                            (inside a session) press keys
    shotbox type TEXT                               (inside a session) type text
    shotbox click X Y [--window RE]                 (inside a session) click there
    shotbox move X Y [--window RE]                  (inside a session) point there
    shotbox drag X1 Y1 X2 Y2 [--window RE]          (inside a session) drag
    shotbox park                                    (inside a session) pointer out of the way
    shotbox compare A.png B.png [--diff D.png]      how many pixels differ

`shotbox COMMAND --help` for each one's options.
"""

import argparse
import os
import sys
import time
from pathlib import Path

from . import term, x, xtest
from .screen import Screen, SessionError
from .session import Session


def size(s):
    w, h = s.lower().split("x")
    return int(w), int(h)


def session_options(p):
    g = p.add_argument_group("the session")
    g.add_argument("--screen", type=size, default=(1280, 800), metavar="WxH",
                   help="the display's size (1280x800)")
    g.add_argument("--desktop", action="store_true",
                   help="real GSettings (dconf) and the system's D-Bus services, "
                        "for desktop shells; the default is in-memory settings "
                        "and nothing activatable")
    g.add_argument("--system-bus", action="store_true", help="a stand-in system bus too")
    g.add_argument("--seed", metavar="DIR", help="start the scratch home as a copy of DIR")
    g.add_argument("--env", action="append", default=[], metavar="NAME=VALUE",
                   help="set a variable inside (repeatable)")
    g.add_argument("--pass", dest="passthrough", action="append", default=[], metavar="NAME",
                   help="let a variable through from outside (repeatable)")
    g.add_argument("--keep", action="store_true", help="keep the scratch dir, and say where")


def make_session(a):
    env = dict(e.split("=", 1) for e in a.env)
    return Session(size=a.screen, desktop=a.desktop, system_bus=a.system_bus,
                   seed=a.seed, keep=a.keep, env=env, passthrough=a.passthrough)


def split(argv):
    """Options, and the command after --."""
    if "--" in argv:
        i = argv.index("--")
        return argv[:i], argv[i + 1:]
    return argv, []


def command(cmd, p):
    if not cmd:
        p.error("no command given, after --")
    return cmd


def cmd_run(argv):
    p = argparse.ArgumentParser(prog="shotbox run",
                                description="Run a command in a sealed session: its own X display, "
                                            "D-Bus and home, and none of yours.")
    session_options(p)
    opts, cmd = split(argv)
    a = p.parse_args(opts)
    cmd = command(cmd, p)
    with make_session(a) as s:
        return s.run(cmd)


def tail(path, n=30):
    try:
        lines = Path(path).read_text(errors="replace").splitlines()
    except OSError:
        return "(no output)"
    return "\n".join(lines[-n:]) or "(no output)"


def cmd_shoot(argv):
    p = argparse.ArgumentParser(
        prog="shotbox shoot",
        description="Start a command in a sealed session, wait until it's ready, "
                    "take a screenshot, and stop it.")
    p.add_argument("out", help="the PNG to write")
    p.add_argument("--window", metavar="RE",
                   help="take this window (its name, a regex matched in full) "
                        "instead of the whole display; also waits for it")
    p.add_argument("--crop", metavar="WxH+X+Y", help="then crop to this")
    p.add_argument("--wait", action="append", default=[], metavar="WHAT",
                   help="wait for window:RE, port:N, file:PATH, ready (the "
                        "program touched $SHOTBOX_SCRATCH/ready, as `shotbox "
                        "term` does after its steps), or stable[:SECS] (the "
                        "--window, or the display, unchanged for SECS, 0.5); "
                        "repeatable, in order")
    p.add_argument("--settle", type=float, default=0.3, metavar="SECS",
                   help="then wait this long for the last paint (0.3)")
    p.add_argument("--park", action="store_true",
                   help="move the pointer out of the way before the picture")
    p.add_argument("--timeout", type=float, default=30, metavar="SECS",
                   help="give up on a wait after this long (30)")
    p.add_argument("--log", metavar="FILE", help="keep the command's output here")
    p.add_argument("--failed", metavar="FILE",
                   help="if it fails, a picture of the screen goes here "
                        "(OUT's name with -failed, beside it)")
    session_options(p)
    opts, cmd = split(argv)
    a = p.parse_args(opts)
    cmd = command(cmd, p)
    waits = list(a.wait)
    if a.window and not any(w.startswith("window:") for w in waits):
        waits.insert(0, "window:" + a.window)
    if not waits and not a.settle:
        p.error("nothing to wait for: give --window, --wait or --settle")

    with make_session(a) as s:
        s.failed = a.failed or str(Path(a.out).with_name(Path(a.out).stem + "-failed.png"))
        log = a.log or str(s.scratch / "command.log")
        proc = s.spawn(cmd, log=log)
        try:
            for spec in waits:
                kind, _, arg = spec.partition(":")
                s.until(*s.test(kind, arg, window=a.window), a.timeout, alive=proc)
            time.sleep(a.settle)
            if proc.poll() is not None:
                s.fail(f"the program exited (status {proc.returncode}) "
                       "before the picture was taken")
            if a.window and not x.find_window(s.env, a.window):
                s.fail(f"the window {a.window!r} went away")
            s.capture(a.out, window=a.window, crop=a.crop, park=a.park)
        except SessionError as e:
            sys.stderr.write(f"shotbox: {e}\n--- {' '.join(cmd)} said ---\n{tail(log)}\n")
            return 1
    print(a.out)
    return 0


def inside():
    """The display of the session this runs in."""
    if not os.environ.get("SHOTBOX_SCRATCH"):
        raise SystemExit("shotbox: this only works inside `shotbox run`")
    return Screen()


def cmd_wait(argv):
    p = argparse.ArgumentParser(prog="shotbox wait",
                                description="Inside `shotbox run`: wait for a window, "
                                            "a port, a file, the ready file, or the "
                                            "screen to stop changing.")
    p.add_argument("kind", choices=("window", "port", "file", "ready", "stable"))
    p.add_argument("arg", nargs="?", default="",
                   help="the window's name (a regex), the port, the file; for "
                        "stable, how long it must hold still (0.5)")
    p.add_argument("--window", metavar="RE",
                   help="for stable: watch this window rather than the display")
    p.add_argument("--timeout", type=float, default=30)
    p.add_argument("--failed", metavar="FILE",
                   help="if it gives up, a picture of the screen goes here "
                        "($SHOTBOX_FAILED)")
    a = p.parse_args(argv)
    screen = inside()
    screen.failed = a.failed or screen.failed
    screen.until(*screen.test(a.kind, a.arg, window=a.window), a.timeout)
    return 0


def cmd_capture(argv):
    p = argparse.ArgumentParser(prog="shotbox capture",
                                description="Inside `shotbox run`: screenshot the display "
                                            "or one window.")
    p.add_argument("out")
    p.add_argument("--window", metavar="RE")
    p.add_argument("--crop", metavar="WxH+X+Y")
    p.add_argument("--park", action="store_true",
                   help="move the pointer out of the way first, as `shotbox park`")
    a = p.parse_args(argv)
    inside().capture(a.out, window=a.window, crop=a.crop, park=a.park)
    return 0


def cmd_key(argv):
    p = argparse.ArgumentParser(prog="shotbox key",
                                description="Inside `shotbox run`: press and release each "
                                            "chord in turn, e.g. ctrl+comma, Return, "
                                            "alt+shift+Tab.")
    p.add_argument("chords", nargs="+", metavar="CHORD")
    a = p.parse_args(argv)
    inside().key(*a.chords)
    return 0


def cmd_type(argv):
    p = argparse.ArgumentParser(prog="shotbox type",
                                description="Inside `shotbox run`: type text into whatever "
                                            "has the keyboard focus.")
    p.add_argument("text")
    a = p.parse_args(argv)
    inside().type(a.text)
    return 0


def pointer_command(name, what):
    def cmd(argv):
        p = argparse.ArgumentParser(prog=f"shotbox {name}",
                                    description=f"Inside `shotbox run`: {what}.")
        p.add_argument("x", type=int)
        p.add_argument("y", type=int)
        p.add_argument("--window", metavar="RE",
                       help="X and Y are inside this window rather than the screen")
        if name == "click":
            p.add_argument("--button", type=int, default=1, help="1 left, 2 middle, 3 right")
            p.add_argument("--double", action="store_true", help="click twice")
        a = p.parse_args(argv)
        if name == "click":
            inside().click(a.x, a.y, window=a.window, button=a.button, double=a.double)
        else:
            inside().move(a.x, a.y, window=a.window)
        return 0
    return cmd


def cmd_drag(argv):
    p = argparse.ArgumentParser(prog="shotbox drag",
                                description="Inside `shotbox run`: press at X1 Y1, move to "
                                            "X2 Y2, release: a divider, a slider, a drop.")
    for n in ("x1", "y1", "x2", "y2"):
        p.add_argument(n, type=int)
    p.add_argument("--window", metavar="RE",
                   help="the points are inside this window rather than the screen")
    p.add_argument("--button", type=int, default=1)
    a = p.parse_args(argv)
    inside().drag(a.x1, a.y1, a.x2, a.y2, window=a.window, button=a.button)
    return 0


def cmd_park(argv):
    p = argparse.ArgumentParser(prog="shotbox park",
                                description="Inside `shotbox run`: move the pointer to the "
                                            "screen's bottom-right corner, off whatever it "
                                            "was hovering, and wait (up to --settle) for "
                                            "the repaint.")
    p.add_argument("--settle", type=float, default=2.0, metavar="SECS",
                   help="wait at most this long for the display to hold still (2)")
    a = p.parse_args(argv)
    inside().park(settle=a.settle)
    return 0


def cmd_compare(argv):
    p = argparse.ArgumentParser(prog="shotbox compare",
                                description="Count the pixels that differ between two "
                                            "images; fail if more than --max do.")
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--diff", metavar="OUT.png", help="write the differences, marked in red")
    p.add_argument("--fuzz", default="0%", help="colors this close count as the same (0%%)")
    p.add_argument("--max", type=int, default=0, help="pixels allowed to differ (0)")
    a = p.parse_args(argv)
    try:
        n = x.compare(a.a, a.b, diff=a.diff, fuzz=a.fuzz)
    except ValueError as e:
        sys.stderr.write(f"shotbox: {e}\n")
        return 2
    print(f"{n} pixels differ")
    return 0 if n <= a.max else 1


COMMANDS = {"run": cmd_run, "shoot": cmd_shoot, "term": term.main, "wait": cmd_wait,
            "capture": cmd_capture, "compare": cmd_compare, "key": cmd_key,
            "type": cmd_type, "click": pointer_command("click", "move the pointer and click"),
            "move": pointer_command("move", "move the pointer, for a hover"),
            "drag": cmd_drag, "park": cmd_park}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help") or argv[0] not in COMMANDS:
        sys.stdout.write(__doc__.lstrip())
        return 0 if not argv or argv[0] in ("-h", "--help") else 2
    try:
        return COMMANDS[argv[0]](argv[1:])
    except (SessionError, xtest.XError) as e:
        sys.stderr.write(f"shotbox: {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
