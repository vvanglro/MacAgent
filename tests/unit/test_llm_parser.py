import json
import sys
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

    plan = parser.parse("搜索 macagent")
    assert len(plan.actions) == 1
    assert plan.actions[0].name == ActionName.CHROME_SEARCH
    assert plan.actions[0].params["query"] == "macagent"

    call_kwargs = parser.client.chat.completions.calls[0]
    assert call_kwargs["response_format"] == {"type": "json_object"}


def test_llm_parser_accepts_plan_payload() -> None:
    parser = OpenAIParser.__new__(OpenAIParser)
    parser.model = "gpt-4o-mini"
    parser.client = FakeClient(
        json.dumps(
            {
                "actions": [
                    {"name": "wechat.open", "params": {}, "requires_confirmation": False},
                    {
                        "name": "wechat.send_message",
                        "params": {"contact": "hulk", "text": "hello"},
                        "requires_confirmation": True,
                    },
                ]
            }
        )
    )

    plan = parser.parse("打开微信并给 hulk 发微信说 hello")

    assert [action.name for action in plan.actions] == [
        ActionName.WECHAT_OPEN,
        ActionName.WECHAT_SEND_MESSAGE,
    ]


def test_llm_parser_accepts_read_last_message_action() -> None:
    parser = OpenAIParser.__new__(OpenAIParser)
    parser.model = "gpt-4o-mini"
    parser.client = FakeClient(
        json.dumps(
            {
                "name": "wechat.read_last_message",
                "params": {"mode": "last"},
                "requires_confirmation": False,
            }
        )
    )

    plan = parser.parse("读取当前聊天最后一条消息")

    assert [action.name for action in plan.actions] == [ActionName.WECHAT_READ_LAST_MESSAGE]
    assert plan.actions[0].params == {"mode": "last"}


def test_llm_parser_accepts_read_last_message_action_with_contact() -> None:
    parser = OpenAIParser.__new__(OpenAIParser)
    parser.model = "gpt-4o-mini"
    parser.client = FakeClient(
        json.dumps(
            {
                "name": "wechat.read_last_message",
                "params": {"contact": "不熬夜", "mode": "last"},
                "requires_confirmation": False,
            }
        )
    )

    plan = parser.parse("读取不熬夜最后一条消息")

    assert [action.name for action in plan.actions] == [ActionName.WECHAT_READ_LAST_MESSAGE]
    assert plan.actions[0].params == {"contact": "不熬夜", "mode": "last"}


def test_llm_parser_accepts_read_all_messages_action_with_contact() -> None:
    parser = OpenAIParser.__new__(OpenAIParser)
    parser.model = "gpt-4o-mini"
    parser.client = FakeClient(
        json.dumps(
            {
                "name": "wechat.read_last_message",
                "params": {"contact": "不熬夜", "mode": "all"},
                "requires_confirmation": False,
            }
        )
    )

    plan = parser.parse("读取不熬夜消息")

    assert [action.name for action in plan.actions] == [ActionName.WECHAT_READ_LAST_MESSAGE]
    assert plan.actions[0].params == {"contact": "不熬夜", "mode": "all"}


def test_llm_parser_accepts_summary_read_action_with_contact() -> None:
    parser = OpenAIParser.__new__(OpenAIParser)
    parser.model = "gpt-4o-mini"
    parser.client = FakeClient(
        json.dumps(
            {
                "name": "wechat.read_last_message",
                "params": {
                    "contact": "沪上小牛爷",
                    "mode": "summary",
                    "instruction": "读取一下我和 沪上小牛爷 都聊了些什么内容",
                },
                "requires_confirmation": False,
            }
        )
    )

    plan = parser.parse("读取一下我和 沪上小牛爷 都聊了些什么内容")

    assert [action.name for action in plan.actions] == [ActionName.WECHAT_READ_LAST_MESSAGE]
    assert plan.actions[0].params == {
        "contact": "沪上小牛爷",
        "mode": "summary",
        "instruction": "读取一下我和 沪上小牛爷 都聊了些什么内容",
    }


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


def test_llm_parser_init_passes_openai_compatible_config(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeOpenAI:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))

    parser = OpenAIParser(
        model="qwen-plus",
        api_key="provider-key",
        base_url="https://example.com/v1",
    )

    assert parser.model == "qwen-plus"
    assert captured == {
        "api_key": "provider-key",
        "base_url": "https://example.com/v1",
    }
