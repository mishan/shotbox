#!/usr/bin/env python3
"""A plain GTK 3 window to take pictures of: test/window.py TITLE [LOG]
[corner|list], or TITLE contrast, or TITLE slow MS, or TITLE flip MS, or TITLE ticking MS,
or TITLE flash MS, or TITLE clock LOG, or TITLE loading, or
TITLE caret MS, or TITLE spinner, or TITLE moving, or
TITLE move, or TITLE scroll, or TITLE strip, or TITLE scene, or TITLE spaced,
or TITLE smooth, or TITLE band [WIDTH [DARK]], or TITLE fast, or TITLE noisy, or TITLE panel,
or TITLE text, pages, redraw, stair, poles, line, gradient, grating, passer, skip,
edge, gray, busy, icon, dropout, beep, fields, alert, popover, wide or shift, or
TITLE trap LOG [focused]. With LOG alone, it holds an entry instead,
and writes what's typed in it there; with corner too, a button in its top
left corner, and writes "clicked" there when it's clicked; with list, rows
longer and more of them than fit, and writes where they're scrolled to,
down and across, there. With contrast,
a switch and a text view in a frame with an edge, which `a11y contrast
--edges 3` should pass; light text whose color is dark enough, which it
may measure short; a label drawn see-through, which it shouldn't; large
text, which needs only 3:1; and a dot, too small to measure. With slow, a square that
turns dark MS milliseconds after the pointer comes into the window, and
light again that long after it leaves: a known latency. With fields, an
entry named by its mnemonic label, and a search bar not revealed, in a
notebook with its tabs hidden. With alert, a Check button that shows an
error in an info bar and is renamed Checked, a Resend button that counts
down to 1s, and a Delete button that asks in a message dialog, its window
titled Delete. With dot,
a "." and nothing else. With secret, a label Plain and below it one,
Secret, drawn all magenta, its text and background. With popover, a faint label and a modal popover
open below it. With wide, a window 1000 pixels wide, a label
as wide, its text at the right, and below it a button at each end. With
moving, a faint label that's dark half a second in two, and dark words
sliding by; with blinking, dark words shown and hidden. With ticking, a
still gray window but for its top right 20x20, black and white by turns
every MS milliseconds, as a clock is. With trap, buttons Before, one with
no name, and After, and a second window, "TITLE two", with Other: once
SIGUSR1 arms it, the program stops itself (SIGSTOP) as a screen reader
reads the unnamed button, partway through a tree, and writes "stopped"
to LOG; with focused, only once the button has the keyboard focus. With
shift, a button with no name and Later, which SIGUSR1 arms to take a New
one in front as a screen reader reads the first. With
A11Y_NAME in its environment, its window is named that, apart from its title."""

import os
import sys
import time

import gi

import patterns

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

w = Gtk.Window(title=sys.argv[1])
w.set_default_size(200, 120)
if sys.argv[2:] == ["contrast"]:
    css = Gtk.CssProvider()
    css.load_from_data(b"window { background: #faf8fc; } label { color: #5f5670; }"
                       b" .dim { opacity: 0.55; } frame > border { border-color: #767676; }")
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), css,
                                             Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin=12)
    light = Gtk.Label()
    light.set_markup('<span weight="light">Contact</span>')
    dim = Gtk.Label(label="Dimmed")
    dim.get_style_context().add_class("dim")
    switch = Gtk.Switch(halign=Gtk.Align.START)
    switch.get_accessible().set_name("Wi-Fi")
    notes = Gtk.TextView(margin=6)
    notes.set_size_request(-1, 60)
    notes.get_accessible().set_name("Notes")
    frame = Gtk.Frame()
    frame.add(notes)
    big = Gtk.Label()
    big.set_markup('<span size="xx-large" weight="bold" foreground="#808080">Heading</span>')
    for widget in (light, dim, switch, frame, big, Gtk.Label(label=".")):
        box.add(widget)
    w.add(box)
elif sys.argv[2:] == ["wide"]:
    box = Gtk.Box()
    box.pack_start(Gtk.Button(label="Here"), False, False, 0)
    box.pack_end(Gtk.Button(label="There"), False, False, 0)
    # Spaced, so the buttons' shadow isn't in the label's box.
    rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    rows.add(Gtk.Label(label="Far", xalign=1))
    rows.add(box)
    w.set_size_request(1000, 120)
    w.add(rows)
elif sys.argv[2:] == ["popover"]:
    css = Gtk.CssProvider()
    css.load_from_data(b"label { color: #a0a0a0; }")
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), css,
                                             Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    faint = Gtk.Label(label="Faint words")
    pop = Gtk.Popover(relative_to=faint, modal=True, position=Gtk.PositionType.BOTTOM)
    pop.add(Gtk.Button(label="Inside", visible=True))
    GLib.timeout_add(300, lambda: pop.popup() and False)
    w.add(faint)
elif sys.argv[2:] == ["dot"]:
    w.add(Gtk.Label(label="."))
elif sys.argv[2:] == ["secret"]:
    css = Gtk.CssProvider()
    css.load_from_data(b"#secret { background: #ff00ff; color: #ff00ff; }")
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), css,
                                             Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin=20)
    box.add(Gtk.Label(label="Plain"))
    box.add(Gtk.Label(label="Secret", name="secret"))
    w.add(box)
elif sys.argv[2:] == ["fields"]:
    # GTK 3 names a field by its label as labelled-by, not as its own name;
    # an unrevealed bar's unnamed button is visible, but not showing; a
    # notebook's hidden tab is showing, but has no size.
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    label = Gtk.Label.new_with_mnemonic("_Name:")
    entry = Gtk.Entry()
    label.set_mnemonic_widget(entry)
    bar = Gtk.Revealer()
    bar.add(Gtk.Button.new_from_icon_name("open-menu-symbolic", Gtk.IconSize.BUTTON))
    for widget in (label, entry, bar):
        box.add(widget)
    book = Gtk.Notebook(show_tabs=False)
    book.append_page(box)
    w.add(book)
elif sys.argv[2:] == ["alert"]:
    # The bar shown, not revealed: revealing one says nothing of it showing.
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    bar = Gtk.InfoBar(message_type=Gtk.MessageType.ERROR, no_show_all=True)
    bar.get_content_area().add(Gtk.Label(label="Name is taken", visible=True))
    check = Gtk.Button(label="Check")
    check.connect("clicked", lambda b: (bar.show(), b.set_label("Checked")))
    resend = Gtk.Button(label="Resend in 5s")

    def tick(left):
        resend.set_label(f"Resend in {left}s")
        if left > 1:
            GLib.timeout_add(200, tick, left - 1)
        return False
    resend.connect("clicked", lambda b: tick(4))
    delete = Gtk.Button(label="Delete")
    delete.connect("clicked", lambda b: Gtk.MessageDialog(
        transient_for=w, title="Delete", message_type=Gtk.MessageType.WARNING,
        buttons=Gtk.ButtonsType.OK_CANCEL, text="Delete notes.md?",
        secondary_text="It can't be undone.").show())
    for widget in (bar, check, resend, delete):
        box.add(widget)
    w.add(box)
elif sys.argv[2:3] and sys.argv[2] in patterns.PATTERNS:
    # flicker's patterns, as they are at each tick from when the window was
    # made, as test/flicker_test.py draws them: a timer, or a draw, late
    # draws that tick late rather than skipping it, and the next is set
    # for its own time, so GLib's timers don't drift.
    area, began, at = Gtk.DrawingArea(), GLib.get_monotonic_time(), [0]
    tick, paint = patterns.PATTERNS[sys.argv[2]](sys.argv[3:])
    area.connect("draw", lambda a, cr: paint(cr, at[0]))

    def step():
        at[0] += tick
        area.queue_draw()
        late = (GLib.get_monotonic_time() - began) // 1000 - at[0]
        GLib.timeout_add(max(1, tick - late), step)
        return False
    GLib.timeout_add(tick, step)
    w.add(area)
elif sys.argv[2:3] == ["slow"]:
    late = int(sys.argv[3])
    square = Gtk.DrawingArea()
    dark = [False]
    square.connect("draw", lambda a, cr: (cr.set_source_rgb(*[0.1 if dark[0] else 0.9] * 3),
                                          cr.paint()))

    def turn(to):
        def now():
            dark[0] = to
            square.queue_draw()
        GLib.timeout_add(late, now)
    w.connect("enter-notify-event", lambda *_: turn(True))
    w.connect("leave-notify-event", lambda *_: turn(False))
    w.add(square)
elif sys.argv[2:3] == ["clock"]:
    # A label counting the seconds, a tenth at a time, as a clock does, above
    # a Go button that writes "clicked" to LOG.
    box, clock, go, n = Gtk.Box(orientation=Gtk.Orientation.VERTICAL), Gtk.Label(), Gtk.Button(label="Go"), [0]

    def tick():
        n[0] += 1
        clock.set_text(f"{n[0] // 10}.{n[0] % 10} s")
        return True
    tick()
    GLib.timeout_add(100, tick)
    go.connect("clicked", lambda b: open(sys.argv[3], "a").write("clicked\n"))
    box.pack_start(clock, False, False, 8)
    box.pack_start(go, False, False, 8)
    w.add(box)
elif sys.argv[2:3] == ["loading"]:
    # Loading for a second: a progress bar named Progress to 100, rows
    # Row 1 to Row 5 one by one, a "Loading" label; then the label gone, a
    # Save button enabled and a Remember box checked.
    box, rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL), Gtk.ListBox()
    bar, loading = Gtk.ProgressBar(), Gtk.Label(label="Loading")
    save, remember = Gtk.Button(label="Save"), Gtk.CheckButton(label="Remember")
    bar.get_accessible().set_name("Progress")
    save.set_sensitive(False)
    for wid in (loading, bar, rows, save, remember):
        box.pack_start(wid, False, False, 2)
    n = [0]

    def step():
        n[0] += 1
        bar.set_fraction(n[0] / 10)
        if n[0] % 2 == 0:
            rows.add(Gtk.Label(label=f"Row {n[0] // 2}"))
            rows.show_all()
        if n[0] < 10:
            return True
        loading.hide()
        save.set_sensitive(True)
        remember.set_active(True)
        return False
    GLib.timeout_add(100, step)
    w.add(box)
elif sys.argv[2:3] == ["ticking"]:
    area, black = Gtk.DrawingArea(), [False]

    def draw(a, cr):
        cr.set_source_rgb(0.5, 0.5, 0.5)
        cr.paint()
        cr.set_source_rgb(*[0 if black[0] else 1] * 3)
        cr.rectangle(a.get_allocated_width() - 20, 0, 20, 20)
        cr.fill()
    area.connect("draw", draw)
    GLib.timeout_add(int(sys.argv[3]), lambda: black.__setitem__(0, not black[0])
                     or area.queue_draw() or True)
    w.add(area)
elif sys.argv[2:3] == ["caret"]:
    # A caret drawn on a timer of its own, as a game's is: a bar 2 by 16
    # after a word, shown and hidden every MS milliseconds.
    area, shown = Gtk.DrawingArea(), [True]

    def draw(a, cr):
        cr.set_source_rgb(1, 1, 1)
        cr.paint()
        cr.set_source_rgb(0, 0, 0)
        cr.move_to(10, 30)
        cr.show_text("hello")
        if shown[0]:
            cr.rectangle(50, 18, 2, 16)
            cr.fill()
    area.connect("draw", draw)
    GLib.timeout_add(int(sys.argv[3]), lambda: shown.__setitem__(0, not shown[0])
                     or area.queue_draw() or True)
    w.add(area)
elif sys.argv[2:] == ["spinner"]:
    spinner = Gtk.Spinner()
    spinner.start()
    w.add(spinner)
elif sys.argv[2:] == ["blinking"]:
    # Dark words, shown and hidden half a second each.
    words, start = Gtk.Label(label="Blinking dark words"), time.monotonic()
    GLib.timeout_add(20, lambda: words.set_opacity(
        (time.monotonic() - start) % 1 < 0.5) or True)
    w.add(words)
elif sys.argv[2:] == ["moving"]:
    # A faint label that flashes dark for half a second every two, and
    # dark words sliding by, 80 pixels a second, back and forth between 0
    # and 240, inside the window: never a jump, which would take them out of
    # where a read just before it said they are.
    css, start = Gtk.CssProvider(), time.monotonic()
    Gtk.StyleContext.add_provider_for_screen(w.get_screen(), css, 800)
    box, slide = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12), Gtk.Fixed()
    words = Gtk.Label(label="Breaking news scrolls by")
    box.add(Gtk.Label(label="Mostly faint words"))
    slide.put(words, 0, 0)
    box.add(slide)

    def tick():
        t = time.monotonic() - start
        css.load_from_data(b"window { background: #ffffff; } label { color: #000000; }"
                           b" box > label { color: %s; }" % (b"#000000" if t % 2 < 0.5
                                                               else b"#a0a0a0"))
        slide.move(words, int(abs(t * 80 % 480 - 240)), 0)
        return True
    GLib.timeout_add(20, tick)
    w.add(box)
elif sys.argv[2:3] == ["beep"]:
    # Black, white for 100 ms every second, and a tone that long played
    # as the white is drawn: a picture and a sound at the same instant.
    import math
    import struct
    import subprocess
    area, white, played = Gtk.DrawingArea(), [False], [False]
    pacat = subprocess.Popen(["pacat", "--format=s16le", "--rate=48000", "--channels=2",
                              "--latency-msec=10"], stdin=subprocess.PIPE)
    tone = b"".join(struct.pack("<hh", s, s) for s in (
        int(8000 * math.sin(2 * math.pi * 1000 * i / 48000)) for i in range(4800)))

    def draw(a, cr):
        cr.set_source_rgb(*[1 if white[0] else 0] * 3)
        cr.paint()
        if white[0] and not played[0]:
            played[0] = True
            pacat.stdin.write(tone)
            pacat.stdin.flush()

    def turn(to):
        white[0], played[0] = to, False
        area.queue_draw()
        return False

    def flash():
        turn(True)
        GLib.timeout_add(100, turn, False)
        return True
    area.connect("draw", draw)
    GLib.timeout_add(1000, flash)
    w.add(area)
elif sys.argv[2:3] == ["trap"]:
    import signal

    gi.require_version("Atk", "1.0")
    from gi.repository import Atk

    armed = []
    signal.signal(signal.SIGUSR1, lambda *_: armed.append("armed"))

    class Trap(Atk.Object):
        """A focusable button with no name, whose labels a screen reader
        asks for: only as it reads it, never fetched ahead with the rest,
        so a walk is partway through when the program stops."""
        def do_ref_state_set(self):
            states = Atk.StateSet()
            states.add_states([Atk.StateType.VISIBLE, Atk.StateType.SHOWING, Atk.StateType.ENABLED,
                               Atk.StateType.SENSITIVE, Atk.StateType.FOCUSABLE])
            return states

        def do_get_n_children(self):
            return 0

        def do_ref_relation_set(self):
            if armed == ["armed"] and (sys.argv[4:] != ["focused"] or trapped.has_focus()):
                armed.append("fired")
                open(sys.argv[3], "a").write("stopped\n")
                os.kill(os.getpid(), signal.SIGSTOP)
            return Atk.RelationSet()

    class Trapped(Gtk.DrawingArea):
        def do_get_accessible(self):
            if not hasattr(self, "acc"):
                self.acc = Trap()
                self.acc.set_role(Atk.Role.PUSH_BUTTON)
                self.acc.set_parent(self.get_parent().get_accessible())
            return self.acc

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    trapped = Trapped(can_focus=sys.argv[4:] == ["focused"])
    trapped.set_size_request(60, 20)
    for child in (Gtk.Button(label="Before"), trapped, Gtk.Button(label="After")):
        box.add(child)
    w.add(box)
    two = Gtk.Window(title=f"{sys.argv[1]} two")
    two.add(Gtk.Button(label="Other"))
    two.show_all()
elif sys.argv[2:] == ["shift"]:
    import signal

    gi.require_version("Atk", "1.0")
    from gi.repository import Atk

    armed = []
    signal.signal(signal.SIGUSR1, lambda *_: armed.append("armed"))

    class Unnamed(Atk.Object):
        """A focusable button with no name, whose labels a screen reader
        asks for as it reads it (never fetched ahead with the rest): once armed,
        that puts a New button in front of it, as a list does that's
        added to while it's read."""
        def do_ref_state_set(self):
            states = Atk.StateSet()
            states.add_states([Atk.StateType.VISIBLE, Atk.StateType.SHOWING, Atk.StateType.ENABLED,
                               Atk.StateType.SENSITIVE, Atk.StateType.FOCUSABLE])
            return states

        def do_get_n_children(self):
            return 0

        def do_ref_relation_set(self):
            if armed == ["armed"]:
                armed.append("fired")
                new = Gtk.Button(label="New")
                box.pack_start(new, False, False, 0)
                box.reorder_child(new, 0)
                new.show()
            return Atk.RelationSet()

    class Shifting(Gtk.DrawingArea):
        def do_get_accessible(self):
            if not hasattr(self, "acc"):
                self.acc = Unnamed()
                self.acc.set_role(Atk.Role.PUSH_BUTTON)
                self.acc.set_parent(self.get_parent().get_accessible())
            return self.acc

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    soon = Shifting()
    soon.set_size_request(60, 20)
    for child in (soon, Gtk.Button(label="Later")):
        box.add(child)
    w.add(box)
elif sys.argv[3:] == ["corner"]:
    button = Gtk.Button(label="Corner", halign=Gtk.Align.START, valign=Gtk.Align.START)
    button.connect("clicked", lambda b: open(sys.argv[2], "w").write("clicked"))
    w.add(button)
elif sys.argv[3:] == ["list"]:
    rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    for i in range(100):
        rows.add(Gtk.Label(label=f"Row {i} " + "and on " * 30, xalign=0))
    pane = Gtk.ScrolledWindow()
    pane.add(rows)
    down, across = pane.get_vadjustment(), pane.get_hadjustment()
    for adjustment in (down, across):
        adjustment.connect("value-changed", lambda a: open(sys.argv[2], "w").write(
            f"{down.get_value():.0f} {across.get_value():.0f}\n"))
    w.add(pane)
elif len(sys.argv) > 2:
    entry = Gtk.Entry()
    entry.connect("changed", lambda e: open(sys.argv[2], "w").write(e.get_text()))
    w.add(entry)
else:
    w.add(Gtk.Label(label="a window"))
w.connect("destroy", Gtk.main_quit)
w.show_all()
# Named apart from its title, as a screen reader hears it.
if os.environ.get("A11Y_NAME"):
    w.get_accessible().set_name(os.environ["A11Y_NAME"])
Gtk.main()
