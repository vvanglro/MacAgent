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
    READ_CURRENT_MESSAGES_PATTERN = re.compile(
        r"((读取|查看|看看)(?:一下)?(?:微信)?(?:当前聊天|当前会话|当前对话)?(?:的)?消息)"
    )
    READ_CONTACT_MESSAGES_PATTERN = re.compile(
        r"^(?:读取|查看|看看)(?:一下)?(?:微信(?:里|中)?(?:和)?|微信)?(?P<contact>.+?)(?:的)?消息$"
    )
    READ_CONTACT_REPLY_ADVICE_PATTERN = re.compile(
        r"^(?:读取|查看|看看|分析|总结)?(?:一下)?(?:我和|微信(?:里|中)?(?:和)?|微信)?\s*(?P<contact>.+?)\s*"
        r"(?:说了些什么|说了什么|都说了些什么|都说了什么|聊了些什么|聊了什么)"
        r"(?:，|,|\s+)?我(?:改|该)怎么(?:继续聊天|继续聊|回|回复|接话).*$"
    )
    READ_CURRENT_REPLY_ADVICE_PATTERN = re.compile(
        r"^(?:读取|查看|看看|分析|总结)?(?:一下)?(?:微信)?(?:当前聊天|当前会话|当前对话)?(?:里)?"
        r"(?:说了些什么|说了什么|都说了些什么|都说了什么|聊了些什么|聊了什么)"
        r"(?:，|,|\s+)?我(?:改|该)怎么(?:继续聊天|继续聊|回|回复|接话).*$"
    )
    READ_CONTACT_SUMMARY_PATTERN = re.compile(
        r"^(?:读取|查看|看看|总结)(?:一下)?(?:我和|微信(?:里|中)?(?:和)?|微信)?\s*(?P<contact>.+?)\s*(?:的)?(?:聊天内容|都聊了些什么内容|都聊了什么内容|都聊了些什么|都聊了什么)$"
    )
    READ_CURRENT_SUMMARY_PATTERN = re.compile(
        r"^(?:读取|查看|看看|总结)(?:一下)?(?:微信)?(?:当前聊天|当前会话|当前对话)?(?:的)?(?:聊天内容|都聊了些什么内容|都聊了什么内容|都聊了些什么|都聊了什么)$"
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
                            params={"contact": contact, "mode": "last", "instruction": raw},
                        )
                    ]
                )

        if self.READ_CURRENT_LAST_MESSAGE_PATTERN.search(raw):
            return ActionPlan(
                actions=[Action(name=ActionName.WECHAT_READ_LAST_MESSAGE, params={"mode": "last", "instruction": raw})]
            )

        contact_reply_advice_match = self.READ_CONTACT_REPLY_ADVICE_PATTERN.search(raw)
        if contact_reply_advice_match:
            contact = contact_reply_advice_match.group("contact").strip()
            if contact and contact not in {"当前聊天", "当前会话", "当前对话"}:
                return ActionPlan(
                    actions=[
                        Action(
                            name=ActionName.WECHAT_READ_LAST_MESSAGE,
                            params={"contact": contact, "mode": "reply_advice", "instruction": raw},
                        )
                    ]
                )

        if self.READ_CURRENT_REPLY_ADVICE_PATTERN.search(raw):
            return ActionPlan(
                actions=[
                    Action(
                        name=ActionName.WECHAT_READ_LAST_MESSAGE,
                        params={"mode": "reply_advice", "instruction": raw},
                    )
                ]
            )

        contact_messages_match = self.READ_CONTACT_MESSAGES_PATTERN.search(raw)
        if contact_messages_match:
            contact = contact_messages_match.group("contact").strip()
            if contact and contact not in {"当前聊天", "当前会话", "当前对话"}:
                return ActionPlan(
                    actions=[
                        Action(
                            name=ActionName.WECHAT_READ_LAST_MESSAGE,
                            params={"contact": contact, "mode": "all", "instruction": raw},
                        )
                    ]
                )

        if self.READ_CURRENT_MESSAGES_PATTERN.search(raw):
            return ActionPlan(
                actions=[Action(name=ActionName.WECHAT_READ_LAST_MESSAGE, params={"mode": "all", "instruction": raw})]
            )

        contact_summary_match = self.READ_CONTACT_SUMMARY_PATTERN.search(raw)
        if contact_summary_match:
            contact = contact_summary_match.group("contact").strip()
            if contact and contact not in {"当前聊天", "当前会话", "当前对话"}:
                return ActionPlan(
                    actions=[
                        Action(
                            name=ActionName.WECHAT_READ_LAST_MESSAGE,
                            params={"contact": contact, "mode": "summary", "instruction": raw},
                        )
                    ]
                )

        if self.READ_CURRENT_SUMMARY_PATTERN.search(raw):
            return ActionPlan(
                actions=[Action(name=ActionName.WECHAT_READ_LAST_MESSAGE, params={"mode": "summary", "instruction": raw})]
            )

        if "聚焦" in raw and ("地址栏" in raw or "搜索栏" in raw):
            return ActionPlan(actions=[Action(name=ActionName.CHROME_FOCUS_ADDRESS_BAR)])

        if "搜索" in raw:
            query = raw.split("搜索", maxsplit=1)[-1].strip() or "macagent"
            return ActionPlan(actions=[Action(name=ActionName.CHROME_SEARCH, params={"query": query})])

        if "chrome" in lowered and "address" in lowered:
            return ActionPlan(actions=[Action(name=ActionName.CHROME_FOCUS_ADDRESS_BAR)])

        raise ParseError(f"无法解析指令: {text}")
