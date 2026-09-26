# shotbox

Reproducible screenshots of real programs, taken where they can't touch your
desktop.

`shotbox shoot` starts a program on a private X display, with its own D-Bus
and a scratch home, waits until it's actually ready, takes the picture, and
cleans up. Run it twice and you get the same bytes. Nothing it runs can
reach your session: no stray windows on your screen, no settings changed, no
profiles or caches written in your home.

```
shotbox shoot editor.png --window 'Text Editor' -- gnome-text-editor notes.md
```

## Why

Screenshots for a README, a theme preview, or a check that a UI still looks
right all want the same things, and every project was growing its own copy:

- **Sealed.** The environment is rebuilt from an allowlist, not scrubbed from
  a denylist, so nothing leaks in by accident. `DISPLAY`, `WAYLAND_DISPLAY`
  and your session bus are gone; `HOME` and every XDG directory are a scratch
  dir. The bus has nothing activatable on it, so no gvfs, dconf or portals
  start behind your back. Settings are in-memory, so apps come up with their
  own defaults, not yours.
- **Ready, not slept.** Waits are for things: a window mapped, a port open, a
  file written, or text on a terminal's screen. No `sleep 6` and hope.
- **Deterministic.** X11 on Xvfb, GTK's software renderer, `LANG=C.UTF-8`,
  `TZ=UTC`, a cursor that doesn't blink (GTK's text caret included, and GTK's
  animations off), and PNGs with no timestamps in them.
- **Cleaned up.** Every program runs in its own process group, and the group
  is killed on the way out: signalling a wrapper script alone leaves its
  children running.

## Install

Needs `Xvfb`, `xauth`, `dbus-daemon`, ImageMagick and `xwininfo`; for
`shotbox term`, PyGObject with VTE (`gir1.2-vte-2.91`). On Debian:

```
sudo apt install xvfb xauth dbus-daemon imagemagick x11-utils gir1.2-vte-2.91
ln -s "$PWD/bin/shotbox" ~/.local/bin/shotbox
```

No Python packages: it's the standard library and those tools.

## Commands

**`shotbox shoot OUT.png [options] -- COMMAND...`** starts the command in a
sealed session, waits, takes the picture and stops everything.

- `--window RE` takes that window (its name, a regex matched in full) rather
  than the whole display, and waits for it to appear.
- `--wait window:RE|port:N|file:PATH|ready` waits for more (repeatable).
  `ready` is `$SHOTBOX_SCRATCH/ready` existing; `shotbox term` writes it.
- `--crop WxH+X+Y`, `--settle SECS` (0.3), `--timeout SECS` (30),
  `--log FILE` for the program's output. If a wait fails or the program
  dies, it says which and shows the program's last output.

**`shotbox run [options] -- COMMAND...`** runs a command in a sealed session
and exits with its status. For scripts that take several pictures: inside,
`shotbox wait window|port|file|ready ARG` and `shotbox capture OUT.png
[--window RE] [--crop G]` work on the session's display.

Inside, `shotbox key CHORD...` presses keys (`ctrl+comma`, `Return`,
`alt+shift+Tab`), `shotbox type TEXT` types ASCII text, and `shotbox click
X Y`, `shotbox move X Y` and `shotbox drag X1 Y1 X2 Y2` work the pointer,
at a point on the screen or, with `--window RE`, inside a window (`click
--button 3`, `--double`). They
speak XTEST to the display directly, so there's still nothing to install.

Both take the session options: `--screen WxH` (1280x800); `--env NAME=VALUE`
and `--pass NAME` to set or let through variables; `--seed DIR` to start the
home as a copy of a directory (a config, a profile, sample files);
`--desktop` for real GSettings and the system's D-Bus services, which a
desktop shell needs; `--system-bus` for a stand-in system bus; `--keep` to
keep the scratch dir and say where it is.

**`shotbox term [options] -- COMMAND...`** is a terminal to take pictures of:
VTE, the engine behind GNOME Terminal, Ptyxis and Tilix, in a plain window
named `shotbox-term`.

- `--scheme FILE` colors it: a Tilix scheme as is, or
  `{"foreground", "background", "cursor", "palette": [16 colors]}`.
- `--size COLSxROWS`, `--font "Monospace 11"`, `--title NAME`.
- Steps, in order: `--when REGEX` waits for the screen's text to match,
  `--type TEXT` types (`\r` is Enter, `\e` Escape), `--sleep SECS`. After
  the last one it writes the ready file.
- `--log FILE` keeps every byte the program wrote, escape codes and all
  (via `script`, whose first line is its own header). Colors are hard to
  judge in a picture and easy to grep in the log.

```
shotbox shoot irssi.png --window shotbox-term --wait ready -- \
  shotbox term --scheme dark.json --size 88x24 \
    --when 'End of /NAMES' --type 'hello\r' -- irssi -c 127.0.0.1
```

**`shotbox compare A.png B.png [--diff D.png] [--fuzz 1%] [--max N]`**
counts the pixels that differ and fails if more than `--max` (0) do. With a
committed picture, that's a visual regression test.

## Node

`node/` is a small package for browser checks with Playwright, from the
pieces several projects had copied between them:

```js
import { serve, checks, pageErrors, launch, until, gif } from 'shotbox';
```

- `serve(dir, port = 0)`: a static server on localhost that serves ES
  modules with the right type; port 0 picks a free one.
- `checks()`: `check(cond, what)` and `skip(what)` print `ok`, `FAIL` or
  `skip` lines; `done()` prints the tally and returns the exit status.
- `pageErrors(page)`: every uncaught exception and `console.error`.
- `launch(cmd, args)`: a program in its own process group, with `kill()`
  that reaches its children and `why()` that says how it ended and what it
  printed. `until(test, ms)` polls.
- `gif(webm, out)`: a Playwright recording as a GIF, via ffmpeg, with its
  own palette.

Use it from a checkout: `"shotbox": "file:../shotbox/node"` in
`devDependencies`.

## Tests

`test/run.sh` checks the session, the terminal, the pictures and the Node
helpers, and takes a few seconds.

## License

MIT. See [LICENSE](LICENSE).
