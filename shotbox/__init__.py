"""shotbox, from Python: `Session` starts a sealed session, `here()` is the
display of the `shotbox run` a script is inside, and both are a `Screen`, to
wait on, drive and take pictures of. See shotbox/screen.py."""

from .screen import Screen, SessionError, here
from .session import Session

__all__ = ["Screen", "Session", "SessionError", "here"]
