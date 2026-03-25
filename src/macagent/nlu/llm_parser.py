from __future__ import annotations

import json
from typing import Any

from macagent.domain.errors import ParseError
from macagent.domain.models import Action, ActionName, ActionPlan

ACTION_SCHEMAS: dict[ActionName, dict[str, Any]] = {
    ActionName.WECHAT_OPEN: {
        "required": set(),
        "optional": set(),
        "description": "Open or activate WeChat",
    },
    ActionName.WECHAT_READ_LAST_MESSAGE: {
        "required": set(),
        "optional": {"contact", "mode"},
        "description": "Read the last visible message in the current WeChat chat window",
    },
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

    Supports OpenAI-compatible providers via custom `base_url`, `api_key`, and `model`.
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - dependency optional
            raise ParseError("OpenAI parser requested but dependency is not installed") from exc

        client_kwargs: dict[str, str] = {}
        if api_key:
            client_kwargs["api_key"] = api_key
        if base_url:
            client_kwargs["base_url"] = base_url

        self.client = OpenAI(**client_kwargs)
        self.model = model

    def parse(self, text: str) -> ActionPlan:
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
            if "actions" in payload:
                plan = ActionPlan.model_validate(payload)
            else:
                plan = ActionPlan(actions=[Action.model_validate(payload)])
            self._validate_action_plan(plan)
            return plan
        except Exception as exc:  # pragma: no cover - network + schema failures
            raise ParseError("LLM 输出不是合法 action JSON") from exc

    def _validate_action_plan(self, plan: ActionPlan) -> None:
        for action in plan.actions:
            self._validate_action_params(action)

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
            "You map user text into a strict JSON object. "
            "Return either a single action object with keys name, params, requires_confirmation, "
            "or a plan object with key actions containing a list of action objects. "
            "Allowed actions and exact params: "
            "wechat.open => params {}, "
            "wechat.read_last_message => params {mode: \"all\"|\"last\"} with optional contact: string, "
            "wechat.send_message => params {contact: string, text: string}, "
            "chrome.focus_address_bar => params {}, "
            "chrome.search => params {query: string}. "
            "Use multiple actions when the user requests a sequence such as opening WeChat "
            "and then sending a message. Do not invent keys. Return JSON only."
        )
