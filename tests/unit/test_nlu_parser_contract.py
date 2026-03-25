from macagent.domain.models import ActionName
from macagent.nlu.fallback_parser import RuleBasedParser


def test_rule_parser_outputs_wechat_action() -> None:
    parser = RuleBasedParser()
    plan = parser.parse("给hulk发微信说hello")

    assert len(plan.actions) == 1
    assert plan.actions[0].name == ActionName.WECHAT_SEND_MESSAGE
    assert plan.actions[0].params["contact"] == "hulk"
    assert plan.actions[0].params["text"] == "hello"


def test_rule_parser_accepts_contact_containing_fa_character() -> None:
    parser = RuleBasedParser()
    plan = parser.parse("给阿发发微信说hello")

    assert plan.actions[0].name == ActionName.WECHAT_SEND_MESSAGE
    assert plan.actions[0].params["contact"] == "阿发"
    assert plan.actions[0].params["text"] == "hello"


def test_rule_parser_outputs_multi_step_wechat_plan() -> None:
    parser = RuleBasedParser()
    plan = parser.parse("打开微信 给小桃有点运气发微信说hello")

    assert [action.name for action in plan.actions] == [
        ActionName.WECHAT_OPEN,
        ActionName.WECHAT_SEND_MESSAGE,
    ]
    assert plan.actions[1].params == {"contact": "小桃有点运气", "text": "hello"}


def test_rule_parser_outputs_wechat_read_last_message_action() -> None:
    parser = RuleBasedParser()
    plan = parser.parse("读取当前聊天最后一条消息")

    assert [action.name for action in plan.actions] == [ActionName.WECHAT_READ_LAST_MESSAGE]


def test_rule_parser_outputs_wechat_read_last_message_for_contact() -> None:
    parser = RuleBasedParser()
    plan = parser.parse("读取不熬夜最后一条消息")

    assert [action.name for action in plan.actions] == [ActionName.WECHAT_READ_LAST_MESSAGE]
    assert plan.actions[0].params == {"contact": "不熬夜"}
