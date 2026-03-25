from macagent.domain.models import Action, ActionName, ActionPlan
from macagent.orchestrator.react import ReActPlanner


def test_react_planner_derives_send_goal_from_multi_action_plan() -> None:
    planner = ReActPlanner()
    goal = planner.derive_goal(
        ActionPlan(
            actions=[
                Action(name=ActionName.WECHAT_OPEN),
                Action(name=ActionName.WECHAT_SEND_MESSAGE, params={"contact": "hulk", "text": "hello"}),
            ]
        )
    )

    assert goal.name == ActionName.WECHAT_SEND_MESSAGE
    assert goal.params == {"contact": "hulk", "text": "hello"}


def test_react_planner_preview_for_read_goal_opens_then_reads() -> None:
    planner = ReActPlanner()
    preview = planner.preview(
        Action(
            name=ActionName.WECHAT_READ_LAST_MESSAGE,
            params={"contact": "不熬夜", "mode": "summary", "instruction": "读取一下我和 不熬夜 都聊了些什么内容"},
        )
    )

    assert [action.name for action in preview] == [
        ActionName.WECHAT_OPEN,
        ActionName.WECHAT_READ_LAST_MESSAGE,
    ]
    assert preview[1].params["contact"] == "不熬夜"
    assert preview[1].params["mode"] == "summary"
