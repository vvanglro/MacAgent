from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ActionName(str, Enum):
    WECHAT_OPEN = "wechat.open"
    WECHAT_READ_LAST_MESSAGE = "wechat.read_last_message"
    WECHAT_SEND_MESSAGE = "wechat.send_message"
    CHROME_FOCUS_ADDRESS_BAR = "chrome.focus_address_bar"
    CHROME_SEARCH = "chrome.search"


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: ActionName
    params: dict[str, Any] = Field(default_factory=dict)
    requires_confirmation: bool = False


class ActionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actions: list[Action] = Field(min_length=1)


class ActionResult(BaseModel):
    ok: bool
    action: ActionName
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)
