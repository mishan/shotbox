# Changelog

## 0.3.0 — 2026-09-27

A session can be a Wayland one, under a headless sway, with Xwayland in
it for X clients; windows, pictures, waits and input work there as they
do on X11. A Playwright recording can come out the same each run.

### Added

- **Wayland sessions.** `--wayland` runs the program under a headless
  sway, drawing in software, instead of Xvfb, and `--xwayland` adds an
  Xwayland in it for X clients. Windows are found by title over sway's
  IPC and taken with grim, and `shoot`, `capture`, `stable` waits, failure
  pictures, `term --shoot` and the Python API work as they do on X11.
  `key`, `type`, `click`, `move`, `drag` and `park` speak sway's virtual
  keyboard and pointer protocols directly, reaching Xwayland's X clients
  too. See docs/wayland.md.
- **`frames(page)`**, a Playwright recording that comes out the same
  each run: the page's time stands still and moves a frame between
  screenshots, and `steady` is the Chromium flags that keep the frames
  alike. `gif()` takes the directory of frames it writes.

## 0.2.0 — 2026-09-27

Sessions can be driven, from the command line and from Python, and wait
for a picture to hold still. Terminal shots take one command. The Node
package grew from the pieces projects had copied into what a Playwright
recording needs: a sealed browser, a pointer and captions, a cut, and a
gif of it. The tests run in CI.

### Changes to check when upgrading

- **The Node package's `package.json` is at the top of the repository**,
  not in `node/`, since npm installs a git dependency from the top and
  nowhere else. Depend on `github:mishan/shotbox`, or on `file:../shotbox`
  for a checkout beside yours; `file:../shotbox/node` no longer works.

### Added

- **Input.** Inside a session, `shotbox key`, `type`, `click`, `move` and
  `drag` drive the display, at a point on the screen or inside a window,
  speaking XTEST directly. `shotbox park` moves the pointer off whatever
  it was hovering. GTK apps in a session no longer blink or animate.
- **`stable` waits** for the display or a window to look the same for a
  while, for what has no other sign it is done. A failed wait leaves a
  picture of the screen as it was.
- **A Python API.** `shotbox.Session` starts a session and
  `shotbox.here()` is the one a script runs inside; both wait, drive the
  display and take pictures over one X connection.
- **`shotbox term --shoot`** starts the session and takes the picture in
  one command, and `--crop COLSxROWS` crops by cells, not pixels.
- **`shotbox compare` on directories**, picture by picture, with `--max`
  and `--fuzz` for one picture by name.
- **`gif()` takes `from`, `colors` and `dither`**: a cut off the start, a
  smaller palette, and no dither for a flat page with something moving on
  it.
- **`sealed()`**, an environment for a headless browser that nothing of
  yours gets into: your fonts, fontconfig and time zone stay out of the
  pictures.
- **`dress(page)`** draws a pointer and captions into a recording, since
  a browser records neither its cursor nor a key pressed.
- **`film(page)`** says where a recording's loop starts, for `gif()`'s
  `from`.
- **`shotbox-serve [DIR] [PORT] [PAGE]`**, `serve()` as a command.
- **TypeScript declarations** for the Node package.

### Fixed

- `shotbox compare` with a missing picture says which, rather than
  failing with a traceback.

## 0.1.0 — 2026-09-25

The first version: `shotbox shoot`, `run`, `wait`, `capture` and `term`
in a sealed session, and a Node package for Playwright checks with a
static server, a check reporter, page errors, process-group launch and
webm to GIF.
