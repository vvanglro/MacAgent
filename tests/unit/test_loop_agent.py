from __future__ import annotations

from datetime import datetime
from pathlib import Path

from macagent.domain.models import Action, ActionName, ActionResult
from macagent.loop_agent import WeChatLoopAgent


class SequencedReadHandler:
    def __init__(self, results: list[ActionResult]) -> None:
        self.results = results
        self.calls: list[Action] = []

    def handle(self, action: Action) -> ActionResult:
        self.calls.append(action)
        index = min(len(self.calls) - 1, len(self.results) - 1)
        return self.results[index]


class RecordingSendHandler:
    def __init__(self) -> None:
        self.calls: list[Action] = []

    def handle(self, action: Action) -> ActionResult:
        self.calls.append(action)
        return ActionResult(ok=True, action=action.name, message=f"sent to {action.params['contact']}")


def test_loop_agent_logs_rounds_and_sends_only_on_new_content(tmp_path: Path) -> None:
    read_handler = SequencedReadHandler(
        [
            ActionResult(
                ok=True,
                action=ActionName.WECHAT_READ_LAST_MESSAGE,
                message="沪上小牛爷 继续聊天建议：...",
                metadata={
                    "last_message": "那我也写个700字？",
                    "incoming_messages": ["一张表情图", "那我也写个700字？"],
                    "summary": "对方在接梗，还问要不要也写个 700 字。",
                    "reply_suggestion": "可以回“那你先来个提纲版？”",
                    "reader_backend": "vision_model",
                    "mode": "reply_advice",
                },
            ),
            ActionResult(
                ok=True,
                action=ActionName.WECHAT_READ_LAST_MESSAGE,
                message="沪上小牛爷 继续聊天建议：...",
                metadata={
                    "last_message": "那我也写个700字？",
                    "incoming_messages": ["一张表情图", "那我也写个700字？"],
                    "summary": "对方在接梗，还问要不要也写个 700 字。",
                    "reply_suggestion": "可以回“那你先来个提纲版？”",
                    "reader_backend": "vision_model",
                    "mode": "reply_advice",
                },
            ),
        ]
    )
    send_handler = RecordingSendHandler()
    messages: list[str] = []
    sleeps: list[float] = []
    timestamps = iter(
        [
            datetime(2026, 3, 25, 10, 0, 0),
            datetime(2026, 3, 25, 10, 0, 1),
            datetime(2026, 3, 25, 10, 1, 0),
        ]
    )
    log_path = tmp_path / "loop.md"

    agent = WeChatLoopAgent(
        read_handler=read_handler,
        send_handler=send_handler,
        reporter=messages.append,
        sleep_fn=sleeps.append,
        clock=lambda: next(timestamps),
    )

    summary = agent.run(
        contact="沪上小牛爷",
        interval_seconds=30,
        rounds=2,
        auto_send=True,
        log_path=log_path,
    )

    assert summary.rounds_completed == 2
    assert summary.replies_sent == 1
    assert send_handler.calls[0].params["text"] == "可以回“那你先来个提纲版？”"
    assert sleeps == [30]
    assert any("检测到新的聊天内容或新的分析结果" in message for message in messages)
    assert any("这一轮没有识别到新的聊天变化" in message for message in messages)

    content = log_path.read_text(encoding="utf-8")
    assert "# MacAgent Loop Log - 沪上小牛爷" in content
    assert "## Round 1" in content
    assert "## Round 2" in content
    assert "可以回“那你先来个提纲版？”" in content
    assert "_not sent_" in content
    assert "<!-- MACAGENT_CONTEXT " in content


def test_loop_agent_uses_default_log_file_in_current_directory(tmp_path: Path, monkeypatch) -> None:
    read_handler = SequencedReadHandler(
        [
            ActionResult(
                ok=True,
                action=ActionName.WECHAT_READ_LAST_MESSAGE,
                message="ok",
                metadata={
                    "last_message": "hello",
                    "incoming_messages": ["hello"],
                    "summary": "对方打了个招呼。",
                    "reply_suggestion": "可以回 hi",
                    "reader_backend": "vision_model",
                    "mode": "reply_advice",
                },
            )
        ]
    )
    send_handler = RecordingSendHandler()
    monkeypatch.chdir(tmp_path)

    agent = WeChatLoopAgent(
        read_handler=read_handler,
        send_handler=send_handler,
        sleep_fn=lambda _seconds: None,
        clock=lambda: datetime(2026, 3, 25, 10, 0, 0),
    )
    summary = agent.run(contact="沪上小牛爷", interval_seconds=10, rounds=1, auto_send=False)

    assert summary.log_path == tmp_path / "macagent-loop-沪上小牛爷-20260325-100000.md"
    assert summary.log_path.exists() is True


def test_loop_agent_passes_recent_history_context_into_next_round(tmp_path: Path) -> None:
    results = [
        ActionResult(
            ok=True,
            action=ActionName.WECHAT_READ_LAST_MESSAGE,
            message="ok-1",
            metadata={
                "last_message": "第一句",
                "incoming_messages": ["第一句"],
                "summary": "对方先打了个招呼。",
                "reply_suggestion": "可以回你好呀",
                "reader_backend": "vision_model",
                "mode": "reply_advice",
            },
        ),
        ActionResult(
            ok=True,
            action=ActionName.WECHAT_READ_LAST_MESSAGE,
            message="ok-2",
            metadata={
                "last_message": "第二句",
                "incoming_messages": ["第一句", "第二句"],
                "summary": "对方继续追问你怎么看。",
                "reply_suggestion": "可以回我也觉得挺有意思",
                "reader_backend": "vision_model",
                "mode": "reply_advice",
            },
        ),
    ]
    read_handler = SequencedReadHandler(results)
    send_handler = RecordingSendHandler()
    timestamps = iter(
        [
            datetime(2026, 3, 25, 10, 0, 0),
            datetime(2026, 3, 25, 10, 0, 1),
            datetime(2026, 3, 25, 10, 1, 0),
        ]
    )

    agent = WeChatLoopAgent(
        read_handler=read_handler,
        send_handler=send_handler,
        sleep_fn=lambda _seconds: None,
        clock=lambda: next(timestamps),
    )

    agent.run(
        contact="沪上小牛爷",
        interval_seconds=30,
        rounds=2,
        auto_send=False,
        context_rounds=2,
        log_path=tmp_path / "loop.md",
    )

    assert "最近几轮历史上下文：" in read_handler.calls[1].params["instruction"]
    assert "对方先打了个招呼。" in read_handler.calls[1].params["instruction"]
    assert "我上次发送：未发送" in read_handler.calls[1].params["instruction"]


def test_loop_agent_skips_auto_send_when_in_cooldown_even_with_new_incoming(tmp_path: Path) -> None:
    read_handler = SequencedReadHandler(
        [
            ActionResult(
                ok=True,
                action=ActionName.WECHAT_READ_LAST_MESSAGE,
                message="ok-1",
                metadata={
                    "last_message": "第一句",
                    "incoming_messages": ["第一句"],
                    "summary": "对方先说了一句。",
                    "reply_suggestion": "可以回第一句",
                    "reader_backend": "vision_model",
                    "mode": "reply_advice",
                },
            ),
            ActionResult(
                ok=True,
                action=ActionName.WECHAT_READ_LAST_MESSAGE,
                message="ok-2",
                metadata={
                    "last_message": "第二句",
                    "incoming_messages": ["第一句", "第二句"],
                    "summary": "对方又追发了一句。",
                    "reply_suggestion": "可以回第二句",
                    "reader_backend": "vision_model",
                    "mode": "reply_advice",
                },
            ),
        ]
    )
    send_handler = RecordingSendHandler()
    messages: list[str] = []
    timestamps = iter(
        [
            datetime(2026, 3, 25, 10, 0, 0),
            datetime(2026, 3, 25, 10, 0, 5),
            datetime(2026, 3, 25, 10, 0, 10),
        ]
    )

    agent = WeChatLoopAgent(
        read_handler=read_handler,
        send_handler=send_handler,
        reporter=messages.append,
        sleep_fn=lambda _seconds: None,
        clock=lambda: next(timestamps),
    )

    summary = agent.run(
        contact="沪上小牛爷",
        interval_seconds=5,
        rounds=2,
        auto_send=True,
        cooldown_seconds=30,
        log_path=tmp_path / "loop.md",
    )

    assert summary.replies_sent == 1
    assert len(send_handler.calls) == 1
    assert any("仍在冷却期内" in message for message in messages)
