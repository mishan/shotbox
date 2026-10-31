"""shotbox mutate: run a test against small changes to the page it
tests, to find a test that fails on a change that shouldn't matter
(brittle) or passes on one that should (blind).
"""

import json
import re

from .screen import SessionError

# Whether each kind of change should fail a test that checks what it's for.
MATTERS = {"size": False, "move": False, "hide": True, "dead": True, "number": True}

FORMS = 'ROLE "NAME", ROLE /RE/, text:"TEXT", text:/RE/ or css:SELECTOR'
NAMED = re.compile(r'("(?:[^"\\]|\\.)*")|/(.*)/')


def target(spec):
    """What a --target names, for the page to find: an ARIA role and its
    exact name, or a JavaScript regex its name matches in full; text the
    same ways; or a CSS selector. The page checks the regex, being the
    one to read it."""
    spec = spec.strip()
    if spec.startswith("css:"):
        if not spec[4:].strip():
            raise SessionError(f"target {spec!r}: its selector is empty")
        return {"by": "css", "css": spec[4:]}
    by, role, rest = ("text", None, spec[5:]) if spec.startswith("text:") else (
        "role", *(spec.split(" ", 1) if " " in spec else (spec, "")))
    m = NAMED.fullmatch(rest)
    if not m or (role is not None and not re.fullmatch(r"[a-z]+", role)):
        raise SessionError(f"target {spec!r} isn't one of {FORMS}")
    try:
        name = json.loads(m[1]) if m[1] else None
    except ValueError as e:
        raise SessionError(f"target {spec!r}: its name isn't a JSON string: {e}") from None
    if not (name.strip() if m[1] else m[2]):
        raise SessionError(f"target {spec!r}: its name is empty")
    return {"by": by, **({"role": role} if role else {}),
            **({"name": name} if m[1] else {"re": m[2]})}


def verdict(kind, ended, proven, confirmed=None):
    """What a run says about the test: `ended` is pass, fail or timeout;
    `proven`, whether the page showed the change was made; `confirmed`,
    for a failure on a change that shouldn't matter, whether it failed
    again on a rerun while a clean rerun passed."""
    if not proven:
        return "UNAPPLIED"
    if MATTERS[kind]:
        return {"pass": "BLIND", "fail": "caught", "timeout": "caught (timeout)"}[ended]
    if ended == "pass":
        return "robust"
    return "BRITTLE" if ended == "fail" and confirmed else "inconclusive"
