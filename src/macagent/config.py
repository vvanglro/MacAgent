from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    parser_backend: str = "rule"
    require_send_confirmation: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        backend = os.getenv("MACAGENT_PARSER_BACKEND", "rule").strip().lower()
        confirmation_flag = os.getenv("MACAGENT_REQUIRE_SEND_CONFIRMATION", "true").strip().lower()
        return cls(
            parser_backend=backend if backend in {"rule", "openai"} else "rule",
            require_send_confirmation=confirmation_flag in {"1", "true", "yes", "on"},
        )
