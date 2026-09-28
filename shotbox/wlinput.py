"""Pressing keys and moving the pointer in a Wayland session under sway:
what xtest.py does for X11.

A few Wayland requests spoken over the compositor's socket, and two
protocols wlroots compositors have for exactly this: a virtual keyboard
(zwp_virtual_keyboard_v1) and a virtual pointer (zwlr_virtual_pointer_v1).
No Python Wayland binding and no wtype: the standard library, with the
keymap passed as a file descriptor.

The keyboard is made once per connection, with a keymap holding every key
shotbox can press, each symbol on a key of its own, so nothing needs Shift
and the keymap never changes. A program meets a new keyboard's keymap
along with its first key, and wtype, which makes a keyboard every time it
runs, was seen to drop a first key. So a new keyboard first presses a key
with no symbol, then waits for that to go through and a moment more. In
testing no key went missing with or without that; it's cheap to keep.
"""

import os
import socket
import struct
import time

from .xtest import KEYSYMS, MODIFIERS, XError

# Real modifier bits, as the keymap below maps them.
MOD_BITS = {0xFFE1: 0x01, 0xFFE3: 0x04, 0xFFE9: 0x08, 0xFFE7: 0x08, 0xFFEB: 0x40}
# Linux's input event codes for pointer buttons 1, 2 and 3.
BUTTONS = {1: 0x110, 2: 0x112, 3: 0x111}
PRESSED, RELEASED = 1, 0
KEYMAP_XKB_V1 = 1

# What the keymap holds: a key with no symbol, for the first press; the
# modifiers; the named keys; and printable ASCII.
TYPABLE = sorted(set(KEYSYMS.values()) | set(range(0x20, 0x7F)))


def keymap():
    """The keymap, as XKB text: each symbol on its own keycode, level one."""
    codes, symbols = [], []
    code = 9
    blank = code
    codes.append(f"<K{code}> = {code};")
    code += 1
    mods = {}
    for name, sym in (("Shift", 0xFFE1), ("Control", 0xFFE3), ("Mod1", 0xFFE9),
                      ("Mod4", 0xFFEB)):
        codes.append(f"<K{code}> = {code};")
        extra = ", 0xffe7" if sym == 0xFFE9 else ""   # Meta beside Alt, on Mod1
        symbols.append(f"key <K{code}> {{ [ 0x{sym:x}{extra} ] }};")
        symbols.append(f"modifier_map {name} {{ <K{code}> }};")
        mods[sym] = code
        code += 1
    keys = {}
    for sym in TYPABLE:
        codes.append(f"<K{code}> = {code};")
        symbols.append(f"key <K{code}> {{ [ 0x{sym:x} ] }};")
        keys[sym] = code
        code += 1
    text = ("xkb_keymap {\n"
            f'xkb_keycodes "shotbox" {{ minimum = 8; maximum = {code}; '
            + " ".join(codes) + " };\n"
            'xkb_types "shotbox" { include "complete" };\n'
            'xkb_compat "shotbox" { include "complete" };\n'
            'xkb_symbols "shotbox" { ' + " ".join(symbols) + " };\n"
            "};\n")
    return text, blank, keys


def _string(s):
    data = s.encode() + b"\0"
    return struct.pack("<I", len(data)) + data + b"\0" * (-len(data) % 4)


class Display:
    """A connection to the compositor in `env` (XDG_RUNTIME_DIR and
    WAYLAND_DISPLAY), with a keyboard and a pointer of its own."""

    def __init__(self, env=None):
        env = os.environ if env is None else env
        path = os.path.join(env.get("XDG_RUNTIME_DIR", ""), env.get("WAYLAND_DISPLAY", ""))
        self.sock = socket.socket(socket.AF_UNIX)
        try:
            self.sock.connect(path)
        except OSError as e:
            raise XError(f"can't reach the Wayland compositor at {path}: {e.strerror}")
        self.buf = b""
        self.next_id = 2
        self.done = set()
        self.globals = {}
        self.registry = self._new()
        self._send(1, 1, struct.pack("<I", self.registry))    # wl_display.get_registry
        self.sync()
        missing = [i for i in ("wl_seat", "zwp_virtual_keyboard_manager_v1",
                               "zwlr_virtual_pointer_manager_v1") if i not in self.globals]
        if missing:
            raise XError("the compositor has no " + ", ".join(missing))
        seat = self._bind("wl_seat", 1)
        kbd_manager = self._bind("zwp_virtual_keyboard_manager_v1", 1)
        ptr_manager = self._bind("zwlr_virtual_pointer_manager_v1", 1)
        self.keyboard = self._new()
        self._send(kbd_manager, 0, struct.pack("<II", seat, self.keyboard))
        self.pointer = self._new()
        self._send(ptr_manager, 0, struct.pack("<II", seat, self.pointer))

        text, self.blank, self.keys = keymap()
        data = text.encode() + b"\0"
        fd = os.memfd_create("shotbox-keymap")
        try:
            os.write(fd, data)
            self._send(self.keyboard, 0, struct.pack("<II", KEYMAP_XKB_V1, len(data)), fd)
        finally:
            os.close(fd)
        # The first key goes to a program along with the keymap; let it be
        # one that means nothing, and give the program a moment with it.
        self._key(self.blank)
        self.sync()
        time.sleep(0.05)
        self.width, self.height = self._size(env)

    # --- the wire -------------------------------------------------------------

    def _new(self):
        self.next_id += 1
        return self.next_id - 1

    def _send(self, obj, opcode, args=b"", fd=None):
        msg = struct.pack("<II", obj, ((8 + len(args)) << 16) | opcode) + args
        if fd is None:
            self.sock.sendall(msg)
        else:
            socket.send_fds(self.sock, [msg], [fd])

    def _bind(self, interface, version):
        name, _ = self.globals[interface]
        new = self._new()
        self._send(self.registry, 0, struct.pack("<I", name) + _string(interface)
                   + struct.pack("<II", version, new))
        return new

    def _event(self):
        while len(self.buf) < 8:
            got = self.sock.recv(4096)
            if not got:
                raise XError("the compositor closed the connection")
            self.buf += got
        obj, word = struct.unpack_from("<II", self.buf)
        size, opcode = word >> 16, word & 0xFFFF
        while len(self.buf) < size:
            got = self.sock.recv(4096)
            if not got:
                raise XError("the compositor closed the connection")
            self.buf += got
        body, self.buf = self.buf[8:size], self.buf[size:]
        if obj == 1 and opcode == 0:                          # wl_display.error
            _, code, n = struct.unpack_from("<III", body)
            raise XError(f"Wayland error {code}: {body[12:12 + n - 1].decode(errors='replace')}")
        if obj == self.registry and opcode == 0:              # wl_registry.global
            name, n = struct.unpack_from("<II", body)
            interface = body[8:8 + n - 1].decode()
            version, = struct.unpack_from("<I", body, 8 + n + (-n % 4))
            self.globals[interface] = (name, version)
        elif opcode == 0 and obj >= 2:                         # a wl_callback.done
            self.done.add(obj)

    def sync(self):
        """Wait until the compositor has handled everything sent so far."""
        callback = self._new()
        self._send(1, 0, struct.pack("<I", callback))         # wl_display.sync
        while callback not in self.done:
            self._event()
        self.done.discard(callback)

    def _size(self, env):
        from . import wl
        out = wl.ipc(env, wl.GET_OUTPUTS)[0]["rect"]
        return out["width"], out["height"]

    # --- the keyboard ---------------------------------------------------------

    @staticmethod
    def _ms():
        return int(time.monotonic() * 1000) & 0xFFFFFFFF

    def _key(self, code, state=None):
        for s in ((PRESSED, RELEASED) if state is None else (state,)):
            self._send(self.keyboard, 1, struct.pack("<III", self._ms(), code - 8, s))

    def _mods(self, mask):
        self._send(self.keyboard, 2, struct.pack("<IIII", mask, 0, 0, 0))

    def press(self, keysym, modifiers=()):
        """Press and release one key, with the modifier keysyms held."""
        if keysym not in self.keys:
            raise XError(f"no key for keysym 0x{keysym:x} in shotbox's keymap")
        mask = 0
        for m in modifiers:
            mask |= MOD_BITS[m]
        if mask:
            self._mods(mask)
        self._key(self.keys[keysym])
        if mask:
            self._mods(0)
        self.sync()

    def chord(self, spec):
        """Press and release a chord: `ctrl+comma`, `Return`, `alt+shift+Tab`.
        A lone `+` is the plus key."""
        *mods, key = spec.split("+") if spec != "+" else ["+"]
        for m in mods:
            if m.lower() not in MODIFIERS:
                raise XError(f"unknown modifier {m!r} in {spec!r}")
        sym = KEYSYMS.get(key, ord(key) if len(key) == 1 else None)
        if sym is None:
            raise XError(f"unknown key {key!r} in {spec!r}")
        self.press(sym, [MODIFIERS[m.lower()] for m in mods])

    def type(self, text):
        """Type text, one key at a time. ASCII only, as on X11."""
        for ch in text:
            self.press({"\n": 0xFF0D, "\r": 0xFF0D, "\t": 0xFF09}.get(ch, ord(ch)))

    # --- the pointer ----------------------------------------------------------

    def _frame(self):
        self._send(self.pointer, 4)

    def move(self, x, y):
        self._send(self.pointer, 1, struct.pack("<IIIII", self._ms(), x, y,
                                                self.width, self.height))
        self._frame()
        self.sync()

    def _button(self, button, state):
        self._send(self.pointer, 2, struct.pack("<III", self._ms(), BUTTONS[button], state))
        self._frame()

    def click(self, x, y, button=1, count=1):
        self.move(x, y)
        for _ in range(count):
            self._button(button, PRESSED)
            self._button(button, RELEASED)
        self.sync()

    def drag(self, x1, y1, x2, y2, button=1, steps=10):
        """Press at one point, move to another in steps, release there."""
        self.move(x1, y1)
        self._button(button, PRESSED)
        self.sync()
        for i in range(1, steps + 1):
            self.move(x1 + (x2 - x1) * i // steps, y1 + (y2 - y1) * i // steps)
        self._button(button, RELEASED)
        self.sync()

    def close(self):
        self.sock.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
