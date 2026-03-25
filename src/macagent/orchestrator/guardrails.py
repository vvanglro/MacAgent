from __future__ import annotations

from macagent.domain.errors import GuardrailError
from macagent.domain.models import Action, ActionName


ALLOWED_ACTIONS = {
    ActionName.WECHAT_SEND_MESSAGE,
    ActionName.CHROME_FOCUS_ADDRESS_BAR,
    ActionName.CHROME_SEARCH,
}


def get_clean_param(action: Action, key: str) -> str:
    return str(action.params.get(key, "")).strip()


def validate_action(action: Action) -> None:
    if action.name not in ALLOWED_ACTIONS:
        raise GuardrailError(f"Action not allowed: {action.name}")

    if action.name == ActionName.WECHAT_SEND_MESSAGE:
        contact = get_clean_param(action, "contact")
        text = get_clean_param(action, "text")
        if not contact:
            raise GuardrailError("contact is required")
        if not text:
            raise GuardrailError("text is required")
        if len(text) > 500:
            raise GuardrailError("message too long")

    if action.name == ActionName.CHROME_SEARCH:
        query = get_clean_param(action, "query")
        if not query:
            raise GuardrailError("query is required")
