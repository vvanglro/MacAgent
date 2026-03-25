import pytest

from macagent.domain.errors import GuardrailError
from macagent.domain.models import Action, ActionName
from macagent.orchestrator.guardrails import validate_action


def test_guardrails_reject_empty_query() -> None:
    action = Action(name=ActionName.CHROME_SEARCH, params={"query": ""})
    with pytest.raises(GuardrailError):
        validate_action(action)


def test_guardrails_accept_wechat_message() -> None:
    action = Action(name=ActionName.WECHAT_SEND_MESSAGE, params={"contact": "hulk", "text": "hello"})
    validate_action(action)


def test_guardrails_accept_wechat_open() -> None:
    action = Action(name=ActionName.WECHAT_OPEN)
    validate_action(action)


def test_guardrails_accept_wechat_read_last_message() -> None:
    action = Action(name=ActionName.WECHAT_READ_LAST_MESSAGE)
    validate_action(action)
