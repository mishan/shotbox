"""shotbox: reproducible screenshots of real programs, in a sealed session.

    shotbox shoot OUT.png [options] -- COMMAND...   run it, wait, take the picture
    shotbox run [options] -- COMMAND...             run it in a sealed session
    shotbox term [options] -- COMMAND...            a terminal to take pictures of
    shotbox wait window|port|file|ready ARG         (inside a session) wait for it
    shotbox capture OUT.png [--window RE]           (inside a session) take a picture
    shotbox compare A.png B.png [--diff D.png]      how many pixels differ

`shotbox COMMAND --help` for each one's options.
"""

import argparse
import os
import sys
import time
from pathlib import Path

from . import term, x
from .session import Session, SessionError, wait_for


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


def waiter(spec, env, scratch, proc):
    kind, _, arg = spec.partition(":")
    if kind == "window":
        return f"a window named {arg!r}", lambda: x.find_window(env, arg)
    if kind == "port":
        return f"port {arg}", lambda: x.port_open(int(arg))
    if kind == "file":
        return f"{arg} to exist", lambda: Path(arg).exists()
    if kind == "ready":
        return "the program to say it's ready", lambda: (scratch / "ready").exists()
    raise SystemExit(f"shotbox: don't know how to wait for {spec!r} "
                     "(window:RE, port:N, file:PATH or ready)")


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
                   help="wait for window:RE, port:N, file:PATH, or ready (the "
                        "program touched $SHOTBOX_SCRATCH/ready, as `shotbox "
                        "term` does after its steps); repeatable")
    p.add_argument("--settle", type=float, default=0.3, metavar="SECS",
                   help="then wait this long for the last paint (0.3)")
    p.add_argument("--timeout", type=float, default=30, metavar="SECS",
                   help="give up on a wait after this long (30)")
    p.add_argument("--log", metavar="FILE", help="keep the command's output here")
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
        log = a.log or str(s.scratch / "command.log")
        proc = s.spawn(cmd, log=log)
        try:
            for spec in waits:
                what, test = waiter(spec, s.env, s.scratch, proc)
                wait_for(what, test, a.timeout, alive=proc)
            time.sleep(a.settle)
            if proc.poll() is not None:
                raise SessionError(f"the program exited (status {proc.returncode}) "
                                   "before the picture was taken")
            window = x.find_window(s.env, a.window) if a.window else None
            if a.window and not window:
                raise SessionError(f"the window {a.window!r} went away")
            x.capture(s.env, a.out, window=window, crop=a.crop)
        except SessionError as e:
            sys.stderr.write(f"shotbox: {e}\n--- {' '.join(cmd)} said ---\n{tail(log)}\n")
            return 1
    print(a.out)
    return 0


def inside():
    if not os.environ.get("SHOTBOX_SCRATCH"):
        raise SystemExit("shotbox: this only works inside `shotbox run`")
    return os.environ, Path(os.environ["SHOTBOX_SCRATCH"])


def cmd_wait(argv):
    p = argparse.ArgumentParser(prog="shotbox wait",
                                description="Inside `shotbox run`: wait for a window, "
                                            "a port, a file, or the ready file.")
    p.add_argument("kind", choices=("window", "port", "file", "ready"))
    p.add_argument("arg", nargs="?", default="")
    p.add_argument("--timeout", type=float, default=30)
    a = p.parse_args(argv)
    env, scratch = inside()
    what, test = waiter(f"{a.kind}:{a.arg}", env, scratch, None)
    try:
        wait_for(what, test, a.timeout)
    except SessionError as e:
        sys.stderr.write(f"shotbox: {e}\n")
        return 1
    return 0


def cmd_capture(argv):
    p = argparse.ArgumentParser(prog="shotbox capture",
                                description="Inside `shotbox run`: screenshot the display "
                                            "or one window.")
    p.add_argument("out")
    p.add_argument("--window", metavar="RE")
    p.add_argument("--crop", metavar="WxH+X+Y")
    a = p.parse_args(argv)
    env, _ = inside()
    window = x.find_window(env, a.window) if a.window else None
    if a.window and not window:
        sys.stderr.write(f"shotbox: no window named {a.window!r}\n")
        return 1
    x.capture(env, a.out, window=window, crop=a.crop)
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
            "capture": cmd_capture, "compare": cmd_compare}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help") or argv[0] not in COMMANDS:
        sys.stdout.write(__doc__.lstrip())
        return 0 if not argv or argv[0] in ("-h", "--help") else 2
    try:
        return COMMANDS[argv[0]](argv[1:])
    except SessionError as e:
        sys.stderr.write(f"shotbox: {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
