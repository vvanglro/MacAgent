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
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str | None = None
    openai_api_key: str | None = None
    vision_model: str | None = None
    vision_base_url: str | None = None
    vision_api_key: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        backend = os.getenv("MACAGENT_PARSER_BACKEND", "rule").strip().lower()
        confirmation_flag = os.getenv("MACAGENT_REQUIRE_SEND_CONFIRMATION", "true").strip().lower()
        openai_model = os.getenv("MACAGENT_OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
        openai_base_url = _clean_optional_env("MACAGENT_OPENAI_BASE_URL")
        openai_api_key = _clean_optional_env("MACAGENT_OPENAI_API_KEY") or _clean_optional_env("OPENAI_API_KEY")
        vision_model = _clean_optional_env("MACAGENT_VISION_MODEL")
        vision_base_url = _clean_optional_env("MACAGENT_VISION_BASE_URL") or openai_base_url
        vision_api_key = (
            _clean_optional_env("MACAGENT_VISION_API_KEY")
            or openai_api_key
            or _clean_optional_env("OPENAI_API_KEY")
        )
        return cls(
            parser_backend=ParserBackend(backend) if backend in {item.value for item in ParserBackend} else ParserBackend.RULE,
            require_send_confirmation=confirmation_flag in {"1", "true", "yes", "on"},
            openai_model=openai_model,
            openai_base_url=openai_base_url,
            openai_api_key=openai_api_key,
            vision_model=vision_model,
            vision_base_url=vision_base_url,
            vision_api_key=vision_api_key,
        )


def _clean_optional_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None

    cleaned = value.strip()
    return cleaned or None
