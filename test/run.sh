#!/bin/sh
# shotbox's own tests: the sealed session, the terminal, the pictures, and
# the Node helpers. Needs what shotbox needs: Xvfb, xauth, dbus-daemon,
# ImageMagick, and PyGObject with VTE for the terminal.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
sb=$here/../bin/shotbox
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
fails=0
ok() { echo "ok    $1"; }
fail() { echo "FAIL  $1"; fails=$((fails + 1)); }

# The session: none of ours gets in, and it cleans up after itself.
out=$(DISPLAY=:0 WAYLAND_DISPLAY=wayland-0 SSH_AUTH_SOCK=/nope SECRET=x \
  "$sb" run -- sh -c 'echo "D=$DISPLAY W=${WAYLAND_DISPLAY-} S=${SSH_AUTH_SOCK-} X=${SECRET-} H=$HOME"')
case $out in
  *"W= S= X= H=/tmp/shotbox-"*) ok "the environment is rebuilt, not inherited" ;;
  *) fail "the environment leaked: $out" ;;
esac
case $out in D=:0*) fail "DISPLAY is ours" ;; *) ok "a display of its own" ;; esac
scratch=$("$sb" run -- sh -c 'echo $SHOTBOX_SCRATCH')
[ ! -e "$scratch" ] && ok "the scratch dir is removed" || fail "left $scratch behind"
set +e; "$sb" run -- sh -c 'exit 7'; st=$?; set -e
[ $st = 7 ] && ok "run exits with the command's status" || fail "run exited $st"
names=$("$sb" run -- gdbus call --session --dest org.freedesktop.DBus \
  --object-path / --method org.freedesktop.DBus.ListActivatableNames)
[ "$names" = "(['org.freedesktop.DBus'],)" ] && ok "nothing activatable on the bus" \
  || fail "activatable: $names"
SHOTBOX_TEST=yes "$sb" run --pass SHOTBOX_TEST --env A=b -- \
  sh -c '[ "$A" = b ] && [ "$SHOTBOX_TEST" = yes ]' \
  && ok "--env sets one, --pass lets one through" || fail "--env and --pass"

# The terminal: steps, the ready file, the log, and the same picture twice.
cat > "$tmp/scheme.json" <<'JSON'
{"foreground": "#ebe6f0", "background": "#0f0d14", "cursor": "#ff2d95",
 "palette": ["#2a2438", "#ff7b72", "#7ee787", "#e5c07b", "#8ca3ff", "#b48cff",
             "#7ed9e7", "#c4bcce", "#9c93ab", "#f7a6a4", "#aae7b1", "#e7cfaa",
             "#b2bef9", "#cab0f9", "#aadeeb", "#ebe6f0"]}
JSON
shot() {
  "$sb" shoot "$1" --window shotbox-term --wait ready -- \
    "$sb" term --scheme "$tmp/scheme.json" --size 40x6 --log "$tmp/pty.log" \
      --when 'name\?' --type 'doll\r' --when 'hi, doll' -- \
      bash --norc -c 'printf "\033[35mname?\033[0m "; read n; echo "hi, $n"; sleep 60' >/dev/null
}
shot "$tmp/a.png" && ok "shoot waits for the steps and takes the window" || fail "shoot"
shot "$tmp/b.png"
[ "$(identify -format %wx%h "$tmp/a.png")" != "" ] && cmp -s "$tmp/a.png" "$tmp/b.png" \
  && ok "two runs, the same bytes" || fail "two runs differ"
grep -q "$(printf '\033')\[35mname?" "$tmp/pty.log" && ok "the log keeps the escape codes" \
  || fail "no escape codes in the log"
set +e
"$sb" shoot "$tmp/c.png" --window shotbox-term --wait ready --timeout 3 -- \
  "$sb" term --timeout 1 --when 'never' -- sh -c 'echo nope; sleep 60' 2> "$tmp/err"
st=$?; set -e
[ $st != 0 ] && grep -q "exited\|gave up" "$tmp/err" && ok "a step that never comes fails, saying why" \
  || fail "a stuck step: status $st"
[ -s "$tmp/c-failed.png" ] && grep -q "c-failed.png" "$tmp/err" \
  && ok "a failed shoot leaves a picture of the screen" || fail "no -failed.png"

# term --shoot, --crop in cells, and a program that's done before the picture.
"$sb" term --shoot "$tmp/full.png" --size 40x10 --when there -- sh -c 'echo hi; echo there' >/dev/null \
  && ok "term --shoot, and the terminal outlives its program" || fail "term --shoot"
"$sb" term --shoot "$tmp/cells.png" --size 40x10 --crop 12x3 --when there -- \
  sh -c 'echo hi; echo there' >/dev/null
full=$(identify -format %wx%h "$tmp/full.png"); cells=$(identify -format %wx%h "$tmp/cells.png")
[ "${cells%x*}" -lt $((${full%x*} / 3 + 2)) ] && [ "${cells#*x}" -lt $((${full#*x} / 3 + 2)) ] \
  && ok "term --crop takes the top-left cells ($cells of $full)" || fail "term --crop: $cells of $full"
set +e; "$sb" term --env A=b -- true 2>/dev/null; st=$?; set -e
[ $st = 2 ] && ok "term takes session options only with --shoot" || fail "term --env: status $st"

# Stable: waits out a burst of output, and gives up on output that never stops.
"$sb" run -- sh -c "
  '$sb' term --size 30x5 --log '$tmp/burst.log' -- \
    bash --norc -c 'for i in 1 2 3 4 5 6 7 8; do echo \$i; sleep 0.2; done; echo over; sleep 60' &
  '$sb' wait window shotbox-term && '$sb' wait stable --window shotbox-term" \
  && grep -aq '^over' "$tmp/burst.log" && ok "stable waits for the screen to stop changing" \
  || fail "stable came early"
set +e
"$sb" run -- sh -c "
  '$sb' term --size 30x5 -- bash --norc -c 'while :; do date +%N; sleep 0.1; done' &
  '$sb' wait window shotbox-term && '$sb' wait stable --timeout 2 --failed '$tmp/busy.png'" 2> "$tmp/err"
st=$?; set -e
[ $st != 0 ] && grep -q "hold still" "$tmp/err" && [ -s "$tmp/busy.png" ] \
  && ok "stable gives up on a busy screen, with a picture of it" || fail "busy: status $st"

# Input: a click for focus, typed text with shifted symbols, and chords.
"$sb" run -- sh -c "
  '$sb' term --size 40x6 --log '$tmp/input.log' -- sh -c cat & t=\$!
  '$sb' wait window shotbox-term && sleep 0.5 &&
  '$sb' click 20 20 --window shotbox-term &&
  '$sb' type 'Hi, you! 1+1=2 ~/a_b <x>' && '$sb' key Return ctrl+d
  st=\$?; sleep 0.5; kill \$t 2>/dev/null; exit \$st" \
  && grep -aq 'Hi, you! 1+1=2 ~/a_b <x>' "$tmp/input.log" \
  && ok "click, type and key reach the program" || fail "input"
set +e; "$sb" key ctrl+comma 2>/dev/null; st=$?; set -e
[ $st != 0 ] && ok "input needs a session" || fail "key ran outside a session"

# The Python API, and parking the pointer.
set +e; python3 "$here/api.py" "$sb" > "$tmp/api.log" 2>&1; st=$?; set -e
cat "$tmp/api.log"
fails=$((fails + $(grep -c '^FAIL' "$tmp/api.log" || true)))
[ $st = 0 ] || grep -q "^FAIL" "$tmp/api.log" || fail "api.py: status $st"

# Wayland: a headless sway, and Xwayland in it. They need sway, grim and
# Xwayland, or they skip, unless SHOTBOX_WAYLAND=required.
win=$here/window.py
if command -v sway >/dev/null && command -v grim >/dev/null && command -v Xwayland >/dev/null; then
  out=$(WAYLAND_DISPLAY=wayland-0 DISPLAY=:0 "$sb" run --wayland -- \
    sh -c 'echo "W=$WAYLAND_DISPLAY D=${DISPLAY-} S=$SWAYSOCK R=$XDG_RUNTIME_DIR"')
  case $out in
    "W=wayland-"*" D= S=/tmp/shotbox-"*/run/sway-ipc.*" R=/tmp/shotbox-"*) ok "wayland: a sway of its own, and no X" ;;
    *) fail "wayland: the environment: $out" ;;
  esac
  "$sb" shoot "$tmp/w1.png" --wayland --window wl-test -- "$win" wl-test >/dev/null
  "$sb" shoot "$tmp/w2.png" --wayland --window wl-test -- "$win" wl-test >/dev/null
  [ "$(identify -format %wx%h "$tmp/w1.png")" = 200x120 ] && cmp -s "$tmp/w1.png" "$tmp/w2.png" \
    && ok "wayland: shoot takes the window, the same bytes twice" || fail "wayland: shoot"
  "$sb" shoot "$tmp/w3.png" --wayland --wait window:wl-test --wait stable -- "$win" wl-test >/dev/null \
    && [ "$(identify -format %wx%h "$tmp/w3.png")" = 1280x800 ] \
    && ok "wayland: a stable wait, and the whole output" || fail "wayland: stable"
  set +e
  "$sb" shoot "$tmp/w4.png" --wayland --window never --timeout 2 -- "$win" wl-test 2> "$tmp/err"
  st=$?; set -e
  [ $st != 0 ] && [ -s "$tmp/w4-failed.png" ] && ok "wayland: a failed wait leaves a picture" \
    || fail "wayland: no -failed.png ($st)"
  "$sb" run --xwayland -- sh -c "[ -n \"\$DISPLAY\" ] && GDK_BACKEND=x11 '$win' wl-x11 &
    '$sb' wait window wl-x11 && '$sb' capture '$tmp/w5.png' --window wl-x11" \
    && [ "$(identify -format %wx%h "$tmp/w5.png")" = 200x120 ] \
    && ok "xwayland: an X client found and taken" || fail "xwayland"
  "$sb" term --shoot "$tmp/w6.png" --wayland --size 30x5 --crop 12x3 --when there -- \
    sh -c 'echo hi; echo there' >/dev/null \
    && ok "wayland: term --shoot, cropped ($(identify -format %wx%h "$tmp/w6.png"))" \
    || fail "wayland: term --shoot"
  # Input: the same as X11's, then a new keyboard for every key, which is
  # where a keyboard's first key can go missing, then an X client.
  "$sb" run --wayland -- sh -c "
    '$sb' term --size 40x6 --log '$tmp/wl-in.log' -- sh -c cat & t=\$!
    '$sb' wait window shotbox-term && '$sb' wait stable --window shotbox-term &&
    '$sb' click 20 20 --window shotbox-term &&
    '$sb' type 'Hi, you! 1+1=2 ~/a_b <x>' && '$sb' key Return ctrl+d
    st=\$?; sleep 0.5; kill \$t 2>/dev/null; exit \$st" \
    && grep -aq 'Hi, you! 1+1=2 ~/a_b <x>' "$tmp/wl-in.log" \
    && ok "wayland: click, type and key reach the program" || fail "wayland: input"
  "$sb" run --wayland -- sh -c "
    '$sb' term --size 40x6 --log '$tmp/wl-keys.log' -- sh -c cat & t=\$!
    '$sb' wait window shotbox-term && '$sb' wait stable --window shotbox-term &&
    for c in a b c d e f g h i j k l m n o p q r s t; do '$sb' type \$c; done
    '$sb' key Return; sleep 0.5; kill \$t 2>/dev/null"
  tr -d '\r' < "$tmp/wl-keys.log" | grep -aqx abcdefghijklmnopqrst \
    && ok "wayland: twenty keyboards, no first key lost" || fail "wayland: a key went missing"
  "$sb" run --xwayland -- sh -c "
    GDK_BACKEND=x11 '$sb' term --size 40x6 --log '$tmp/xw-in.log' -- sh -c cat & t=\$!
    '$sb' wait window shotbox-term && '$sb' wait stable --window shotbox-term &&
    '$sb' click 20 20 --window shotbox-term && '$sb' type 'over X' && '$sb' key Return
    st=\$?; sleep 0.5; kill \$t 2>/dev/null; exit \$st" \
    && grep -aq 'over X' "$tmp/xw-in.log" \
    && ok "xwayland: typing reaches an X client" || fail "xwayland: input"
  pgrep -f "shotbox-.*/sway.conf" >/dev/null && fail "wayland: sway left running" \
    || ok "wayland: sway stops with the session"
else
  [ "${SHOTBOX_WAYLAND-}" = required ] && fail "wayland skipped: no sway, grim or Xwayland" \
    || echo "skip  wayland: no sway, grim or Xwayland"
fi

# Compare.
"$sb" compare "$tmp/a.png" "$tmp/b.png" >/dev/null && ok "compare: the same" || fail "compare same"
convert "$tmp/a.png" -fill red -draw 'point 3,3' "$tmp/d.png"
set +e; n=$("$sb" compare "$tmp/a.png" "$tmp/d.png" --diff "$tmp/diff.png"); st=$?; set -e
[ $st = 1 ] && [ "$n" = "1 pixels differ" ] && [ -s "$tmp/diff.png" ] \
  && ok "compare: one pixel off, found" || fail "compare: $st $n"

mkdir -p "$tmp/ref" "$tmp/new"
cp "$tmp/a.png" "$tmp/ref/same.png"; cp "$tmp/a.png" "$tmp/new/same.png"
cp "$tmp/a.png" "$tmp/ref/off.png"; cp "$tmp/d.png" "$tmp/new/off.png"
cp "$tmp/a.png" "$tmp/ref/gone.png"
set +e; out=$("$sb" compare "$tmp/ref" "$tmp/new" --diff "$tmp/diffs"); st=$?; set -e
[ $st = 1 ] && echo "$out" | grep -q "^same: the same" && echo "$out" | grep -q "^off: 1 pixels" \
  && echo "$out" | grep -q "^gone: no" && [ -s "$tmp/diffs/off-diff.png" ] \
  && ok "compare: directories, picture by picture" || fail "compare dirs: $st $out"
"$sb" compare "$tmp/ref" "$tmp/new" same off --max 0 --max off=1 >/dev/null \
  && ok "compare: NAMEs, and --max for one" || fail "compare NAME=N"
set +e; "$sb" compare "$tmp/a.png" "$tmp/nope.png" 2> "$tmp/err"; st=$?; set -e
[ $st = 2 ] && grep -q "no .*nope.png" "$tmp/err" && ok "compare: a missing picture, said plainly" \
  || fail "compare missing: $st $(cat "$tmp/err")"

# Node.
node --test --test-reporter=spec "$here"/node.test.mjs >"$tmp/node.log" 2>&1 && ok "node helpers" \
  || { fail "node helpers"; cat "$tmp/node.log"; }
# The declarations, which are hand-written, against a file that uses them.
tsc=$here/../node_modules/.bin/tsc
if [ -x "$tsc" ]; then
  (cd "$here/.." && "$tsc") >"$tmp/tsc.log" 2>&1 && ok "the declarations" \
    || { fail "the declarations"; cat "$tmp/tsc.log"; }
else
  echo "skip  the declarations: no TypeScript (npm install)"
fi

# And the ones that need a browser: Playwright's Chromium, from
# `npm install && npx playwright install chromium`, or they skip, unless
# SHOTBOX_BROWSER=required.
node --test --test-reporter=spec "$here"/browser.test.mjs >"$tmp/browser.log" 2>&1 || {
  fail "browser helpers"; cat "$tmp/browser.log"; }
if grep -q '^ℹ skipped [1-9]' "$tmp/browser.log"; then
  # CI says it has to run, so there a skip is a failure.
  why=$(grep -m1 -o 'no Playwright[^)]*)\|no ffmpeg' "$tmp/browser.log")
  [ "${SHOTBOX_BROWSER-}" = required ] && fail "browser helpers skipped: $why" \
    || echo "skip  browser helpers: $why"
elif ! grep -q '^ℹ fail [1-9]' "$tmp/browser.log"; then
  ok "browser helpers"
fi

echo
[ $fails = 0 ] && echo "all passed" || { echo "$fails failed"; exit 1; }
