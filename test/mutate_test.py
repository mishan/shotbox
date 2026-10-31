#!/usr/bin/env python3
"""shotbox mutate's targets and verdicts, which need no display:
test/mutate_test.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shotbox.mutation import target, verdict  # noqa: E402
from shotbox.screen import SessionError  # noqa: E402

fails = 0


def check(ok, what):
    global fails
    print(("ok    " if ok else "FAIL  ") + what)
    fails += not ok


for spec, want in [
    ('button "Pay"', {"by": "role", "role": "button", "name": "Pay"}),
    ('link "Say \\"hi\\""', {"by": "role", "role": "link", "name": 'Say "hi"'}),
    ("button /Pay( now)?/", {"by": "role", "role": "button", "re": "Pay( now)?"}),
    ('button "Pay" ', {"by": "role", "role": "button", "name": "Pay"}),
    ("button / /", {"by": "role", "role": "button", "re": " "}),
    ('text:"Total: 42.50"', {"by": "text", "name": "Total: 42.50"}),
    ("text:/Total: .*/", {"by": "text", "re": "Total: .*"}),
    ("css:#pay > span", {"by": "css", "css": "#pay > span"}),
]:
    got = target(spec)
    check(got == want, f"target {spec!r}: {got}")

for spec, why in [
    ("Pay", "ROLE"),
    ('"Pay"', "ROLE"),
    ("button Pay", "ROLE"),
    ('button "Pay', "ROLE"),
    ("button //", "empty"),
    ('button ""', "empty"),
    ('button "   "', "empty"),
    ('button "\\x41"', "isn't"),
    ('button "tab\there"', "isn't"),
    ("css:", "empty"),
    ("text:", "ROLE"),
    ('Button "Pay"', "ROLE"),
]:
    try:
        got = target(spec)
    except SessionError as e:
        check(why in str(e), f"target {spec!r} refused: {e}")
    else:
        check(False, f"target {spec!r} refused, not {got}")

# Every cell: (kind, how the test ended, whether the change was proven,
# whether a failure held up on a rerun while a clean rerun passed).
for kind, ended, proven, confirmed, want in [
    ("move", "pass", True, None, "robust"),
    ("move", "fail", True, True, "BRITTLE"),
    ("move", "fail", True, False, "inconclusive"),
    ("move", "timeout", True, None, "inconclusive"),
    ("move", "timeout", True, True, "inconclusive"),
    ("size", "fail", True, True, "BRITTLE"),
    ("hide", "pass", True, None, "BLIND"),
    ("hide", "fail", True, None, "caught"),
    ("hide", "timeout", True, None, "caught (timeout)"),
    ("number", "pass", True, None, "BLIND"),
    ("dead", "fail", True, None, "caught"),
    *((k, e, False, None, "UNAPPLIED") for k in ("move", "hide") for e in ("pass", "fail", "timeout")),
]:
    got = verdict(kind, ended, proven, confirmed)
    check(got == want, f"{kind}, {ended}, {'proven' if proven else 'unproven'}"
          f"{'' if confirmed is None else ', confirmed' if confirmed else ', unconfirmed'}: {got}")

sys.exit(fails)
