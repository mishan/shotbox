#!/usr/bin/env python3
"""A plain GTK 3 window to take pictures of: test/window.py TITLE."""

import sys

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

w = Gtk.Window(title=sys.argv[1])
w.set_default_size(200, 120)
w.add(Gtk.Label(label="a window"))
w.connect("destroy", Gtk.main_quit)
w.show_all()
Gtk.main()
