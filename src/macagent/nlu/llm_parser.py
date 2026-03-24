from __future__ import annotations

import json

from macagent.domain.errors import ParseError
from macagent.domain.models import Action


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
        prompt = (
            "You map user text into action JSON with keys: name, params, requires_confirmation. "
            "Allowed names: wechat.send_message, chrome.focus_address_bar, chrome.search."
        )
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": text}],
        )

        try:
            content = response.choices[0].message.content
            payload = json.loads(content)
            return Action.model_validate(payload)
        except Exception as exc:  # pragma: no cover - network + schema failures
            raise ParseError("LLM 输出不是合法 action JSON") from exc
