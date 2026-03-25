from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum


class ParserBackend(str, Enum):
    RULE = "rule"
    OPENAI = "openai"


@dataclass(frozen=True)
class Settings:
    parser_backend: ParserBackend = ParserBackend.RULE
    require_send_confirmation: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        backend_raw = os.getenv("MACAGENT_PARSER_BACKEND", ParserBackend.RULE.value).strip().lower()
        confirmation_flag = os.getenv("MACAGENT_REQUIRE_SEND_CONFIRMATION", "true").strip().lower()

        try:
            backend = ParserBackend(backend_raw)
        except ValueError:
            backend = ParserBackend.RULE

        return cls(
            parser_backend=backend,
            require_send_confirmation=confirmation_flag in {"1", "true", "yes", "on"},
        )
