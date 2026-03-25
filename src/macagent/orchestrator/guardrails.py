from __future__ import annotations

from macagent.domain.errors import GuardrailError
from macagent.domain.models import Action, ActionName


ALLOWED_ACTIONS = {
    ActionName.WECHAT_OPEN,
    ActionName.WECHAT_READ_LAST_MESSAGE,
    ActionName.WECHAT_SEND_MESSAGE,
    ActionName.CHROME_FOCUS_ADDRESS_BAR,
    ActionName.CHROME_SEARCH,
}


def validate_action(action: Action) -> None:
    if action.name not in ALLOWED_ACTIONS:
        raise GuardrailError(f"Action not allowed: {action.name}")

    if action.name == ActionName.WECHAT_SEND_MESSAGE:
        contact = str(action.params.get("contact", "")).strip()
        text = str(action.params.get("text", "")).strip()
        if not contact:
            raise GuardrailError("contact is required")
        if not text:
            raise GuardrailError("text is required")
        if len(text) > 500:
            raise GuardrailError("message too long")

    if action.name == ActionName.CHROME_SEARCH:
        query = str(action.params.get("query", "")).strip()
        if not query:
            raise GuardrailError("query is required")

    if action.name == ActionName.WECHAT_READ_LAST_MESSAGE:
        contact = str(action.params.get("contact", "")).strip()
        if "contact" in action.params and not contact:
            raise GuardrailError("contact must not be empty")
        mode = str(action.params.get("mode", "all")).strip().lower()
        if mode not in {"all", "last", "summary"}:
            raise GuardrailError("mode must be one of: all, last, summary")
