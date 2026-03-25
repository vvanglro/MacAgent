from __future__ import annotations

import re

from macagent.domain.errors import ParseError
from macagent.domain.models import Action, ActionName, ActionPlan


class RuleBasedParser:
    """Simple parser for offline/local development and testing."""

    OPEN_WECHAT_PATTERN = re.compile(r"(打开|启动)(?:一下)?微信")
    WECHAT_PATTERN = re.compile(r"给(?P<contact>.+?)发微信[：: ]?(说)?(?P<text>.+)")
    READ_CURRENT_LAST_MESSAGE_PATTERN = re.compile(
        r"((读取|查看|看看)(?:一下)?(?:微信)?(?:当前聊天|当前会话|当前对话)?(?:的)?最后一条消息)"
    )
    READ_CONTACT_LAST_MESSAGE_PATTERN = re.compile(
        r"^(?:读取|查看|看看)(?:一下)?(?:微信(?:里|中)?(?:和)?|微信)?(?P<contact>.+?)(?:的)?最后一条消息$"
    )

    def parse(self, text: str) -> ActionPlan:
        raw = text.strip()
        lowered = raw.lower()
        actions: list[Action] = []

        if self.OPEN_WECHAT_PATTERN.search(raw):
            actions.append(Action(name=ActionName.WECHAT_OPEN))

        match = self.WECHAT_PATTERN.search(raw)
        if match:
            actions.append(
                Action(
                    name=ActionName.WECHAT_SEND_MESSAGE,
                    params={
                        "contact": match.group("contact").strip(),
                        "text": match.group("text").strip(),
                    },
                    requires_confirmation=True,
                )
            )
            return ActionPlan(actions=actions)

        if actions:
            return ActionPlan(actions=actions)

        contact_match = self.READ_CONTACT_LAST_MESSAGE_PATTERN.search(raw)
        if contact_match:
            contact = contact_match.group("contact").strip()
            if contact and contact not in {"当前聊天", "当前会话", "当前对话"}:
                return ActionPlan(
                    actions=[
                        Action(
                            name=ActionName.WECHAT_READ_LAST_MESSAGE,
                            params={"contact": contact},
                        )
                    ]
                )

        if self.READ_CURRENT_LAST_MESSAGE_PATTERN.search(raw):
            return ActionPlan(actions=[Action(name=ActionName.WECHAT_READ_LAST_MESSAGE)])

        if "聚焦" in raw and ("地址栏" in raw or "搜索栏" in raw):
            return ActionPlan(actions=[Action(name=ActionName.CHROME_FOCUS_ADDRESS_BAR)])

        if "搜索" in raw:
            query = raw.split("搜索", maxsplit=1)[-1].strip() or "macagent"
            return ActionPlan(actions=[Action(name=ActionName.CHROME_SEARCH, params={"query": query})])

        if "chrome" in lowered and "address" in lowered:
            return ActionPlan(actions=[Action(name=ActionName.CHROME_FOCUS_ADDRESS_BAR)])

        raise ParseError(f"无法解析指令: {text}")
