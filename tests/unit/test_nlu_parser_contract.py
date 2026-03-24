from macagent.domain.models import ActionName
from macagent.nlu.fallback_parser import RuleBasedParser


def test_rule_parser_outputs_wechat_action() -> None:
    parser = RuleBasedParser()
    action = parser.parse("给hulk发微信说hello")

    assert action.name == ActionName.WECHAT_SEND_MESSAGE
    assert action.params["contact"] == "hulk"
    assert action.params["text"] == "hello"
