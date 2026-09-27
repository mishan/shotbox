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

# Compare.
"$sb" compare "$tmp/a.png" "$tmp/b.png" >/dev/null && ok "compare: the same" || fail "compare same"
convert "$tmp/a.png" -fill red -draw 'point 3,3' "$tmp/d.png"
set +e; n=$("$sb" compare "$tmp/a.png" "$tmp/d.png" --diff "$tmp/diff.png"); st=$?; set -e
[ $st = 1 ] && [ "$n" = "1 pixels differ" ] && [ -s "$tmp/diff.png" ] \
  && ok "compare: one pixel off, found" || fail "compare: $st $n"

# Node.
node --test "$here"/node.test.mjs >"$tmp/node.log" 2>&1 && ok "node helpers" \
  || { fail "node helpers"; cat "$tmp/node.log"; }

echo
[ $fails = 0 ] && echo "all passed" || { echo "$fails failed"; exit 1; }
