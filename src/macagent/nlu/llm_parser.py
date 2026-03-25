from __future__ import annotations

import json
import logging
from json import JSONDecodeError
from typing import Any

from pydantic import ValidationError

from macagent.domain.errors import ParseError
from macagent.domain.models import Action, ActionName

logger = logging.getLogger(__name__)

ACTION_SCHEMAS: dict[ActionName, dict[str, Any]] = {
    ActionName.WECHAT_SEND_MESSAGE: {
        "required": {"contact", "text"},
        "optional": set(),
        "description": "Send a WeChat message",
    },
    ActionName.CHROME_FOCUS_ADDRESS_BAR: {
        "required": set(),
        "optional": set(),
        "description": "Focus Chrome address bar",
    },
    ActionName.CHROME_SEARCH: {
        "required": {"query"},
        "optional": set(),
        "description": "Open Chrome search",
    },
}


class OpenAIParser:
    """Optional parser backend using OpenAI Chat Completions API.

    Requires `openai` extra dependency and `OPENAI_API_KEY` environment variable.
    """

    def __init__(self, model: str = "gpt-4o-mini") -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - dependency optional
            raise ParseError("OpenAI parser requested but dependency is not installed") from exc

        self.client = OpenAI()
        self.model = model

    def parse(self, text: str) -> Action:
        response = self.client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": text},
            ],
        )

        try:
            content = response.choices[0].message.content
            payload = json.loads(content)
            action = Action.model_validate(payload)
            self._validate_action_params(action)
            return action
        except (IndexError, KeyError, TypeError, JSONDecodeError, ValidationError, ParseError) as exc:
            logger.exception("Failed to parse LLM action output")
            raise ParseError("LLM 输出不是合法 action JSON") from exc

    def _validate_action_params(self, action: Action) -> None:
        schema = ACTION_SCHEMAS[action.name]
        keys = set(action.params.keys())

        missing = schema["required"] - keys
        if missing:
            missing_text = ", ".join(sorted(missing))
            raise ParseError(f"Action {action.name} missing params: {missing_text}")

        allowed = schema["required"] | schema["optional"]
        extra = keys - allowed
        if extra:
            extra_text = ", ".join(sorted(extra))
            raise ParseError(f"Action {action.name} has unsupported params: {extra_text}")

    def _system_prompt(self) -> str:
        return (
            "You map user text into a strict JSON action object with keys: "
            "name, params, requires_confirmation. "
            "Allowed actions and exact params: "
            "wechat.send_message => params {contact: string, text: string}, "
            "chrome.focus_address_bar => params {}, "
            "chrome.search => params {query: string}. "
            "Do not invent keys. Return JSON only."
        )
