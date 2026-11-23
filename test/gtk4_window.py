#!/usr/bin/env python3
"""A plain GTK 4 window, with no libadwaita: test/gtk4_window.py. In
frames, faint labels: one GTK can't pick (can-target off), one under an
overlay's clear child, and one in a menu button's popover, open below
the rest; and a stack shown at its first page, "Gone", then its second,
whose faint "Here" is at the other end. `glyphs
MARKUP|FONT|PX|WEIGHT|COLOR|BACKGROUND[|SHADOW]...` is a window of those
labels instead. `block LOG N [SECONDS...]` is N windows whose main thread,
on SIGUSR1, is busy for each of SECONDS (1 1 1), free for 90 ms between,
writing to LOG when each starts and ends. `fake LOG KIT WHAT SECONDS` is a
window whose program is on the accessibility bus as AccessKit's are, by
toolkit KIT, answering it from a thread of its own; on SIGUSR1, its main
thread is busy for SECONDS (WHAT main), or its bus thread is (bus), or
that, then it leaves the bus (leave). `empty` is a window, gtk4-empty, of a
button and below it a group named Nothing with nothing in it, 0 pixels
tall. `edged` is a window, gtk4-edged, in a box with a
border and padding, of rows with room to the right, of framed buttons:
Ok and Apply, of a size; Faintly; Thick; and Plain, flat. Most and More,
and Shifted and Further, flat, each beside a frame its size; Agree,
Also, Again and Apart, flat beside a frame its size; Wide, an entry;
Tall and Short, filled, touching; Bevel; Typing, focused, beside Pale
field, faint; Hover, flat, above a frame its size, which is beside Twin;
and Hid, half scrolled out."""

import os
import signal
import sys
import threading
import time

import gi

if sys.argv[1:2] == ["fake"]:
    os.environ["GTK_A11Y"] = "none"     # its own bus side, not GTK's
gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402


def faint(text, **props):
    label = Gtk.Label(**props)
    label.set_markup(f'<span foreground="#b0b0b0">{text}</span>')
    return label


def activate(app):
    w = Gtk.ApplicationWindow(application=app, title="gtk4-old")
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=12,
                  margin_bottom=12, margin_start=12, margin_end=12)
    menu = Gtk.MenuButton(label="Save", halign=Gtk.Align.START,
                          popover=Gtk.Popover(child=faint("Popped")))
    box.append(faint("Faint words"))
    box.append(faint("Untouchable", can_target=False))
    over = Gtk.Overlay(child=faint("Underneath"))
    over.add_overlay(Gtk.Box())
    box.append(over)
    stack = Gtk.Stack()
    stack.add_named(Gtk.Label(label="Gone", halign=Gtk.Align.START), "gone")
    here = faint("Here", halign=Gtk.Align.END)
    stack.add_named(here, "here")
    box.append(stack)
    box.append(menu)
    w.set_child(Gtk.Frame(child=Gtk.Frame(child=box, margin_top=9, margin_start=9)))
    w.present()

    def later():
        stack.set_visible_child(here)
        menu.popup()
    GLib.timeout_add(300, later)


def empty(app):
    w = Gtk.ApplicationWindow(application=app, title="gtk4-empty")
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    nothing = Gtk.Box(accessible_role=Gtk.AccessibleRole.GROUP)
    nothing.update_property([Gtk.AccessibleProperty.LABEL], ["Nothing"])
    box.append(Gtk.Button(label="Go"))
    box.append(nothing)
    w.set_child(box)
    w.present()


def glyphs(app):
    w = Gtk.ApplicationWindow(application=app, title="gtk4-glyphs")
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=12,
                  margin_bottom=12, margin_start=12, margin_end=12)
    css = ""
    for i, case in enumerate(sys.argv[2:]):
        text, family, px, weight, color, back, *shadow = case.split("|")
        box.append(Gtk.Label(label=text, use_markup=True, halign=Gtk.Align.START,
                             css_classes=[f"g{i}"]))
        css += (f"label.g{i} {{ font-family: {family}; font-size: {px}px; font-weight: {weight};"
                f" color: {color}; background: {back}; padding: 6px 12px;"
                f" text-shadow: {shadow[0] if shadow else 'none'}; }}\n")
    provider = Gtk.CssProvider()
    provider.load_from_string(css)
    Gtk.StyleContext.add_provider_for_display(w.get_display(), provider,
                                              Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    w.set_child(box)
    w.present()


def edged(app):
    w = Gtk.ApplicationWindow(application=app, title="gtk4-edged")
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, css_classes=["padded"])

    # Wide, as what's in it is put off by as much as the room it has.
    def row(*children, into=box, width=440):
        r = Gtk.Box(spacing=6, halign=Gtk.Align.START, width_request=width)
        for c in children:
            r.append(c)
        into.append(r)
        return r

    def button(label, *css, **kw):
        return Gtk.Button(label=label, css_classes=list(css), **kw)

    def entry(name, *css):
        e = Gtk.Entry(css_classes=list(css), width_chars=8)
        e.update_property([Gtk.AccessibleProperty.LABEL], [name])
        return e

    def icon(name, *css):
        b = Gtk.Button(icon_name="window-close-symbolic", css_classes=list(css),
                       width_request=34, height_request=34)
        b.update_property([Gtk.AccessibleProperty.LABEL], [name])
        return b
    row(button("Ok", width_request=60), button("Apply", width_request=60),
        button("Faintly", "faint"), button("Thick", "thick"), button("Plain", "flat"))
    def decoyed(label, width):
        """A flat button and, beside it, a frame of its size, not a control."""
        return (button(label, "flat", width_request=width, height_request=34),
                Gtk.Box(width_request=width, height_request=34, css_classes=["decoy"]))
    row(button("Most"), button("More"), *decoyed("Shifted", 70), *decoyed("Further", 76),
        width=520)
    row(button("Agree"), button("Also"), button("Again"), *decoyed("Apart", 60))
    wide = entry("Wide")
    wide.set_size_request(300, -1)
    row(wide)
    joined = row(button("Tall", "solid", width_request=200, height_request=40),
                 button("Short", "solid", width_request=200, valign=Gtk.Align.CENTER))
    joined.set_spacing(0)
    row(button("Bevel", "bevel"))
    row(button("Off", "flat", width_request=60), button("Dim", width_request=60, sensitive=False))
    typing = entry("Typing")
    row(typing, entry("Pale field", "faint"))
    pair = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, height_request=120)
    row(Gtk.Box(width_request=34), icon("Hover", "flat"), into=pair)
    row(icon("Twin"), Gtk.Box(width_request=34, height_request=34, css_classes=["decoy"]),
        into=pair)
    box.append(pair)
    box.append(Gtk.ScrolledWindow(
        child=row(Gtk.Label(label="Scrolled further", width_request=100, xalign=0),
                  button("Hid"), into=Gtk.Box()),
        min_content_width=120, max_content_width=120, halign=Gtk.Align.START,
        vscrollbar_policy=Gtk.PolicyType.NEVER))
    provider = Gtk.CssProvider()
    provider.load_from_string(
        "window, scrolledwindow { background: #f0f0f0; }"
        " box.padded { padding: 6px 4px; border: 3px solid #808080; }"
        " button, entry { border-radius: 0; box-shadow: none; outline: none; min-height: 24px;"
        " min-width: 0; padding: 4px 8px; background: #e0e0e0; color: #101010;"
        " border: 1px solid #404040; }"
        " .faint { border-color: #d0d0d0; background: #f0f0f0; }"
        " .thick { border-width: 2px; }"
        " .flat { background: none; border-color: transparent; }"
        " .solid { background: #404040; color: #ffffff; border: none; }"
        " .bevel { border-color: #ffffff #404040 #404040 #ffffff; }"
        " box.decoy { border: 1px solid #404040; background: #e0e0e0; }")
    Gtk.StyleContext.add_provider_for_display(w.get_display(), provider,
                                              Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    w.set_child(box)
    w.present()
    typing.grab_focus()


def note(what):
    with open(sys.argv[2], "a") as f:
        f.write(f"{time.time():.3f} {what}\n")


def on_usr1(then):
    try:
        gi.require_version("GLibUnix", "2.0")
        from gi.repository import GLibUnix
        add = GLibUnix.signal_add
    except (ImportError, ValueError, AttributeError):   # older GLib
        add = GLib.unix_signal_add
    add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1, lambda *_: then() or True)


def block(app):
    def busy(left):
        note("start")
        end = time.monotonic() + left[0]
        while time.monotonic() < end:
            pass
        note("end")
        if left[1:]:
            GLib.timeout_add(90, busy, left[1:])
        return False
    on_usr1(lambda: busy([float(s) for s in sys.argv[4:]] or [1, 1, 1]))
    for _ in range(int(sys.argv[3])):
        Gtk.ApplicationWindow(application=app, title="gtk4-block",
                              child=Gtk.Label(label="Busy on SIGUSR1")).present()


def fake(app):
    kit, what, seconds = sys.argv[3], sys.argv[4], float(sys.argv[5])
    root, ctx, bus = "/org/a11y/atspi/accessible/root", GLib.MainContext(), []
    ready = threading.Event()
    node = Gio.DBusNodeInfo.new_for_xml(
        '<node><interface name="org.a11y.atspi.Application"><property name="ToolkitName" '
        'type="s" access="read"/></interface><interface name="org.a11y.atspi.Accessible">'
        '<property name="ChildCount" type="i" access="read"/></interface></node>')

    def serve():
        # Its calls are dispatched in this thread, as the context's.
        ctx.push_thread_default()
        conn = Gio.DBusConnection.new_for_address_sync(
            os.environ["AT_SPI_BUS_ADDRESS"], Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
            | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
        for iface in node.interfaces:
            conn.register_object(root, iface, None, lambda *a: GLib.Variant(
                "s", kit) if a[4] == "ToolkitName" else GLib.Variant("i", 0), None)
        conn.call_sync("org.a11y.atspi.Registry", root, "org.a11y.atspi.Socket", "Embed",
                       GLib.Variant("((so))", ((conn.get_unique_name(), root),)), None,
                       Gio.DBusCallFlags.NONE, -1, None)
        bus.append(conn)
        ready.set()
        GLib.MainLoop(ctx).run()

    def busy():
        note("start")
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            pass
        note("end")
        if what == "leave":
            bus[0].close_sync(None)
    threading.Thread(target=serve, daemon=True).start()
    # On the bus before its window shows, which is all a test waits for.
    ready.wait()
    on_usr1(busy if what == "main" else lambda: ctx.invoke_full(GLib.PRIORITY_DEFAULT, busy))
    Gtk.ApplicationWindow(application=app, title="fake", child=Gtk.Label(label="Fake")).present()


app = Gtk.Application(application_id="org.shotbox.Gtk4Old")
app.connect("activate", {"glyphs": glyphs, "block": block, "fake": fake, "empty": empty,
                         "edged": edged}.get(
    "".join(sys.argv[1:2]), activate))
app.run([])
