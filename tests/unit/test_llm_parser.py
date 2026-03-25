import json
from types import SimpleNamespace

import pytest

from macagent.domain.errors import ParseError
from macagent.domain.models import ActionName
from macagent.nlu.llm_parser import OpenAIParser


class FakeCompletions:
    def __init__(self, content: str) -> None:
        self._content = content
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self._content))]
        )


class FakeChat:
    def __init__(self, content: str) -> None:
        self.completions = FakeCompletions(content)


class FakeClient:
    def __init__(self, content: str) -> None:
        self.chat = FakeChat(content)


@pytest.mark.parametrize(
    "payload",
    [
        {
            "name": "chrome.search",
            "params": {"query": "macagent"},
            "requires_confirmation": False,
        }
    ],
)
def test_llm_parser_uses_chat_completions_payload(payload) -> None:
    parser = OpenAIParser.__new__(OpenAIParser)
    parser.model = "gpt-4o-mini"
    parser.client = FakeClient(json.dumps(payload))

    action = parser.parse("搜索 macagent")
    assert action.name == ActionName.CHROME_SEARCH
    assert action.params["query"] == "macagent"

    call_kwargs = parser.client.chat.completions.calls[0]
    assert call_kwargs["response_format"] == {"type": "json_object"}


def test_llm_parser_raises_parse_error_on_bad_json() -> None:
    parser = OpenAIParser.__new__(OpenAIParser)
    parser.model = "gpt-4o-mini"
    parser.client = FakeClient("not-json")

    with pytest.raises(ParseError):
        parser.parse("anything")


def test_llm_parser_rejects_unsupported_param_keys() -> None:
    parser = OpenAIParser.__new__(OpenAIParser)
    parser.model = "gpt-4o-mini"
    parser.client = FakeClient(
        json.dumps(
            {
                "name": "chrome.search",
                "params": {"q": "macagent"},
                "requires_confirmation": False,
            }
        )
    )

    with pytest.raises(ParseError):
        parser.parse("搜索 macagent")
