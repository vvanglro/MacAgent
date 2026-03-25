from __future__ import annotations

from collections.abc import Callable


Reporter = Callable[[str], None]


def emit_progress(reporter: Reporter | None, message: str) -> None:
    if reporter is None:
        return
    reporter(message)
