"""A sealed session: a private X display, a private D-Bus, a scratch home.

Everything a screenshot needs to be reproducible and harmless. Nothing run
inside can reach your desktop: DISPLAY, WAYLAND_DISPLAY and the session bus
are gone, the environment is rebuilt from an allowlist rather than scrubbed
from a denylist, and HOME and every XDG directory point into a scratch dir
that is removed afterwards. Settings are in-memory and portals are off, so
apps come up with their own defaults instead of yours.

    with Session(size=(1280, 800)) as s:
        s.run(["gnome-text-editor"])

The pieces, and why each one:

- Xvfb on a display number of our own, with an Xauthority cookie, started
  with -displayfd so we know it's listening instead of guessing with sleep.
- dbus-daemon with a config of our own. By default its service directory is
  empty, so nothing gets activated on it behind your back (gvfs, dconf, the
  portals); desktop=True uses the system's service directories instead, for
  things like GNOME Shell that need dconf and friends.
- Optionally a stand-in system bus, for programs that insist on one.
- Every process in its own group, and the group killed on the way out:
  signalling a wrapper script alone leaves its children running.
"""

import os
import secrets
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path

# Passed through from the caller unless told otherwise. Everything else is
# rebuilt: nothing from your session leaks in by accident.
PASS = ("PATH", "USER", "LOGNAME", "SHELL", "TERM")

# Deterministic GTK: X11 on Xvfb, the software renderer, no portals, no
# accessibility bus, in-memory settings, nothing mounted.
SEALED_ENV = {
    "LANG": "C.UTF-8",
    "TZ": "UTC",
    "GDK_BACKEND": "x11",
    "GSK_RENDERER": "cairo",
    "ADW_DISABLE_PORTAL": "1",
    "GDK_DEBUG": "no-portals",
    "GTK_A11Y": "none",
    "NO_AT_BRIDGE": "1",
    "GIO_USE_VFS": "local",
    "GSETTINGS_BACKEND": "memory",
}

BUS_CONFIG = """<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-Bus Bus Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
  <type>{type}</type>
  <keep_umask/>
  <listen>{listen}</listen>
  <auth>EXTERNAL</auth>
  {services}
  <policy context="default">
    <allow send_destination="*" eavesdrop="true"/>
    <allow eavesdrop="true"/>
    <allow own="*"/>
  </policy>
</busconfig>
"""


GTK_SETTINGS = """[Settings]
gtk-cursor-blink = false
gtk-enable-animations = false
"""


class SessionError(RuntimeError):
    pass


def need(*tools):
    missing = [t for t in tools if not shutil.which(t)]
    if missing:
        raise SessionError("not found: " + ", ".join(missing))


def free_display(skip=()):
    """The lowest display number with neither a lock nor a socket."""
    for n in range(99, 1000):
        if n in skip:
            continue
        if not (Path(f"/tmp/.X{n}-lock").exists()
                or Path(f"/tmp/.X11-unix/X{n}").exists()):
            return n
    raise SessionError("no free X display number")


def kill_group(proc, grace=2.0):
    """TERM the process's group, then KILL it if it hasn't gone."""
    if proc is None or proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(grace)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()


class Session:
    def __init__(self, size=(1280, 800), desktop=False, system_bus=False,
                 seed=None, keep=False, env=None, passthrough=()):
        self.size = size
        self.desktop = desktop
        self.system_bus = system_bus
        self.seed = seed
        self.keep = keep
        self.extra_env = dict(env or {})
        self.passthrough = tuple(PASS) + tuple(passthrough)
        self.scratch = None
        self.env = None
        self._procs = []

    # --- setup ----------------------------------------------------------------

    def __enter__(self):
        need("Xvfb", "xauth", "dbus-daemon")
        self.scratch = Path(tempfile.mkdtemp(prefix="shotbox-"))
        try:
            self._make_home()
            display, xauth = self._start_x()
            bus = self._start_bus("session")
            sysbus = self._start_bus("system") if self.system_bus else None
            self.env = self._make_env(display, xauth, bus, sysbus)
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def _make_home(self):
        home = self.scratch / "home"
        if self.seed:
            shutil.copytree(self.seed, home, symlinks=True)
        home.mkdir(exist_ok=True)
        for d in (".config", ".local/share", ".local/state", ".cache"):
            (home / d).mkdir(parents=True, exist_ok=True)
        # GTK apps: no blinking text caret, which a picture would catch on
        # or off at random, and no animations, which it would catch mid-way.
        # A seeded home's own settings win.
        for gtk in ("gtk-3.0", "gtk-4.0"):
            ini = home / ".config" / gtk / "settings.ini"
            if not ini.exists():
                ini.parent.mkdir(parents=True, exist_ok=True)
                ini.write_text(GTK_SETTINGS)
        run = self.scratch / "run"
        run.mkdir(mode=0o700)

    def _start_x(self):
        # Two sessions starting at once can pick the same free number; the
        # second Xvfb then fails to take it. Move on to the next one.
        xauth = self.scratch / "Xauthority"
        xauth.touch(mode=0o600)
        cookie = secrets.token_hex(16)
        taken = set()
        for _ in range(20):
            n = free_display(skip=taken)
            taken.add(n)
            subprocess.run(["xauth", "-q", "-f", str(xauth), "add", f":{n}", ".", cookie],
                           check=True)
            r, w = os.pipe()
            w_, h = self.size
            proc = subprocess.Popen(
                ["Xvfb", f":{n}", "-auth", str(xauth), "-displayfd", str(w),
                 "-screen", "0", f"{w_}x{h}x24", "-nolisten", "tcp", "-noreset"],
                pass_fds=(w,), stdout=subprocess.DEVNULL,
                stderr=open(self.scratch / "Xvfb.log", "wb"),
                start_new_session=True)
            os.close(w)
            with os.fdopen(r) as f:
                got = f.readline().strip()   # blocks until Xvfb listens or exits
            if got:
                self._procs.append(proc)
                return f":{got}", xauth
            proc.wait()
        raise SessionError("Xvfb didn't start; see " + str(self.scratch / "Xvfb.log"))

    def _start_bus(self, kind):
        services = self.scratch / f"{kind}-services"
        services.mkdir()
        if kind == "session" and self.desktop:
            dirs = "<standard_session_servicedirs/>"
        else:
            dirs = f"<servicedir>{services}</servicedir>"
        listen = (f"unix:tmpdir={self.scratch}" if kind == "session"
                  else f"unix:path={self.scratch / 'run' / 'system_bus_socket'}")
        conf = self.scratch / f"{kind}-bus.conf"
        conf.write_text(BUS_CONFIG.format(type=kind, listen=listen, services=dirs))
        proc = subprocess.Popen(
            ["dbus-daemon", "--config-file", str(conf), "--nofork", "--print-address"],
            stdout=subprocess.PIPE, stderr=open(self.scratch / f"{kind}-bus.log", "wb"),
            text=True, start_new_session=True)
        self._procs.append(proc)
        address = proc.stdout.readline().strip()
        if not address:
            raise SessionError(f"dbus-daemon ({kind}) didn't start")
        return address

    def _make_env(self, display, xauth, bus, sysbus):
        home = self.scratch / "home"
        env = {k: os.environ[k] for k in self.passthrough if k in os.environ}
        env.update(SEALED_ENV)
        if self.desktop:
            del env["GSETTINGS_BACKEND"]
        env.update(
            HOME=str(home),
            XDG_CONFIG_HOME=str(home / ".config"),
            XDG_DATA_HOME=str(home / ".local/share"),
            XDG_STATE_HOME=str(home / ".local/state"),
            XDG_CACHE_HOME=str(home / ".cache"),
            XDG_RUNTIME_DIR=str(self.scratch / "run"),
            DISPLAY=display,
            XAUTHORITY=str(xauth),
            DBUS_SESSION_BUS_ADDRESS=bus,
            SHOTBOX="1",
            SHOTBOX_SCRATCH=str(self.scratch),
        )
        if sysbus:
            env["DBUS_SYSTEM_BUS_ADDRESS"] = sysbus
        env.update(self.extra_env)
        return env

    # --- running things -----------------------------------------------------------

    def spawn(self, cmd, log=None, **kw):
        """Start `cmd` inside the session, in its own process group. Output
        goes to `log` (a path) if given, else through."""
        out = open(log, "ab") if log else None
        try:
            proc = subprocess.Popen(cmd, env=self.env, stdout=out, stderr=out,
                                    start_new_session=True, **kw)
        except OSError as e:
            raise SessionError(f"can't run {cmd[0]}: {e.strerror}")
        self._procs.append(proc)
        return proc

    def run(self, cmd, **kw):
        """Run `cmd` to the end inside the session; its exit status."""
        proc = self.spawn(cmd, **kw)
        try:
            return proc.wait()
        finally:
            kill_group(proc)

    # --- teardown -----------------------------------------------------------------

    def __exit__(self, *exc):
        for proc in reversed(self._procs):
            kill_group(proc)
        if self.scratch and self.scratch.exists():
            if self.keep:
                print(f"shotbox: kept {self.scratch}")
            else:
                shutil.rmtree(self.scratch, ignore_errors=True)
        return False


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
