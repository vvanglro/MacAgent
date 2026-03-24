from __future__ import annotations

import re

from macagent.domain.errors import ParseError
from macagent.domain.models import Action, ActionName


class RuleBasedParser:
    """Simple parser for offline/local development and testing."""

    WECHAT_PATTERN = re.compile(r"给(?P<contact>[^发说\s]+)发微信[：: ]?(说)?(?P<text>.+)")

    def parse(self, text: str) -> Action:
        raw = text.strip()
        lowered = raw.lower()

        match = self.WECHAT_PATTERN.search(raw)
        if match:
            return Action(
                name=ActionName.WECHAT_SEND_MESSAGE,
                params={"contact": match.group("contact").strip(), "text": match.group("text").strip()},
                requires_confirmation=True,
            )

        if "聚焦" in raw and ("地址栏" in raw or "搜索栏" in raw):
            return Action(name=ActionName.CHROME_FOCUS_ADDRESS_BAR)

        if "搜索" in raw:
            query = raw.split("搜索", maxsplit=1)[-1].strip() or "macagent"
            return Action(name=ActionName.CHROME_SEARCH, params={"query": query})

        if "chrome" in lowered and "address" in lowered:
            return Action(name=ActionName.CHROME_FOCUS_ADDRESS_BAR)

        raise ParseError(f"无法解析指令: {text}")
