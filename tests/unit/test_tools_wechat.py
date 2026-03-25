import json
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from macagent.domain.errors import ExecutionError
from macagent.domain.models import Action, ActionName
from macagent.tools.wechat import (
    OCRTextBlock,
    WeChatOpenHandler,
    WeChatReadLastMessageHandler,
    WeChatSendMessageHandler,
    _chat_capture_region,
    _collect_ocr_text,
    _extract_last_message,
    _is_probable_timestamp,
    _pick_contact_search_result,
    _parse_window_bounds,
    _search_result_click_point,
)


class FakeExecutor:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []
        self.responses: dict[str, CompletedProcess[str]] = {}

    def run_or_raise(self, command: list[str], timeout: int = 20):
        self.commands.append(command)
        return self.responses.get(
            command[0],
            CompletedProcess(command, 0, stdout="", stderr=""),
        )


def test_wechat_handler_invokes_osascript_and_restores_clipboard() -> None:
    executor = FakeExecutor()
    handler = WeChatSendMessageHandler(executor)

    handler.handle(Action(name=ActionName.WECHAT_SEND_MESSAGE, params={"contact": "hulk", "text": "hello"}))

    assert executor.commands
    assert executor.commands[0] == ["open", "-a", "WeChat"]
    assert executor.commands[1][0] == "osascript"
    assert "savedClipboard" in executor.commands[1][2]
    assert "set the clipboard to savedClipboard" in executor.commands[1][2]
    assert 'tell application "WeChat" to activate' in executor.commands[1][2]
    assert "searchFieldStillVisible" in executor.commands[1][2]
    assert "key code 48" in executor.commands[1][2]
    assert "key code 125" in executor.commands[1][2]


def test_wechat_handler_rejects_missing_contact_or_text() -> None:
    executor = FakeExecutor()
    handler = WeChatSendMessageHandler(executor)

    with pytest.raises(ExecutionError):
        handler.handle(Action(name=ActionName.WECHAT_SEND_MESSAGE, params={"text": "hello"}))

    with pytest.raises(ExecutionError):
        handler.handle(Action(name=ActionName.WECHAT_SEND_MESSAGE, params={"contact": "hulk"}))


def test_wechat_open_handler_launches_and_activates_wechat() -> None:
    executor = FakeExecutor()
    handler = WeChatOpenHandler(executor)

    result = handler.handle(Action(name=ActionName.WECHAT_OPEN))

    assert result.ok is True
    assert executor.commands == [
        ["open", "-a", "WeChat"],
        ["osascript", "-e", 'tell application "WeChat" to activate'],
    ]


def test_parse_window_bounds_accepts_four_numbers() -> None:
    assert _parse_window_bounds("120, 240, 900, 700") == (120, 240, 900, 700)


def test_chat_capture_region_focuses_message_area() -> None:
    assert _chat_capture_region((100, 200, 1000, 800)) == (400, 296, 670, 528)


def test_search_result_click_point_converts_normalized_ocr_box_to_screen_coordinates() -> None:
    point = _search_result_click_point(
        OCRTextBlock(text="群聊", min_x=0.20, min_y=0.10, max_x=0.60, max_y=0.20),
        (100, 200, 500, 400),
    )

    assert point == (300, 540)


def test_extract_last_message_joins_bottom_multiline_cluster() -> None:
    message = _extract_last_message(
        [
            OCRTextBlock(text="第二行", min_x=0.62, min_y=0.08, max_x=0.85, max_y=0.12),
            OCRTextBlock(text="第一行", min_x=0.62, min_y=0.13, max_x=0.85, max_y=0.17),
            OCRTextBlock(text="更早的消息", min_x=0.10, min_y=0.35, max_x=0.30, max_y=0.39),
        ]
    )

    assert message == "第一行 第二行"


def test_extract_last_message_ignores_centered_timestamp_labels() -> None:
    message = _extract_last_message(
        [
            OCRTextBlock(text="14:28", min_x=0.45, min_y=0.08, max_x=0.55, max_y=0.12),
            OCRTextBlock(text="hello", min_x=0.65, min_y=0.07, max_x=0.82, max_y=0.11),
            OCRTextBlock(text="更早的消息", min_x=0.10, min_y=0.30, max_x=0.30, max_y=0.34),
        ]
    )

    assert message == "hello"


def test_collect_ocr_text_returns_all_blocks_top_to_bottom() -> None:
    text = _collect_ocr_text(
        [
            OCRTextBlock(text="底部", min_x=0.60, min_y=0.08, max_x=0.82, max_y=0.12),
            OCRTextBlock(text="顶部", min_x=0.10, min_y=0.40, max_x=0.30, max_y=0.44),
        ]
    )

    assert text == ["顶部", "底部"]


def test_is_probable_timestamp_recognizes_centered_time_label() -> None:
    assert _is_probable_timestamp(
        OCRTextBlock(text="14:28", min_x=0.45, min_y=0.20, max_x=0.55, max_y=0.24)
    ) is True


def test_pick_contact_search_result_prefers_contact_match_before_group_section() -> None:
    result = _pick_contact_search_result(
        [
            OCRTextBlock(text="纯洁友谊户", min_x=0.10, min_y=0.70, max_x=0.30, max_y=0.76),
            OCRTextBlock(text="纯洁友谊户俱乐部", min_x=0.10, min_y=0.62, max_x=0.38, max_y=0.68),
            OCRTextBlock(text="群聊", min_x=0.05, min_y=0.18, max_x=0.12, max_y=0.22),
            OCRTextBlock(text="纯洁友谊户本圆⑤", min_x=0.16, min_y=0.06, max_x=0.45, max_y=0.12),
        ],
        "纯洁友谊户",
    )

    assert result is not None
    assert result.text == "纯洁友谊户"


def test_pick_contact_search_result_falls_back_to_group_when_no_contact_match() -> None:
    result = _pick_contact_search_result(
        [
            OCRTextBlock(text="群聊", min_x=0.05, min_y=0.18, max_x=0.12, max_y=0.22),
            OCRTextBlock(text="纯洁友谊户本圆⑤", min_x=0.16, min_y=0.06, max_x=0.45, max_y=0.12),
        ],
        "纯洁友谊户",
    )

    assert result is not None
    assert result.text == "纯洁友谊户本圆⑤"


def test_wechat_read_last_message_handler_reads_chat_region(monkeypatch) -> None:
    executor = FakeExecutor()
    executor.responses["osascript"] = CompletedProcess(
        ["osascript"],
        0,
        stdout="100,200,1000,800",
        stderr="",
    )
    executor.responses["swift"] = CompletedProcess(
        ["swift"],
        0,
        stdout=json.dumps(
            [
                {"text": "hello", "minX": 0.65, "minY": 0.08, "maxX": 0.82, "maxY": 0.12},
                {"text": "earlier", "minX": 0.12, "minY": 0.30, "maxX": 0.28, "maxY": 0.34},
            ]
        ),
        stderr="",
    )
    handler = WeChatReadLastMessageHandler(executor)
    captured_regions: list[tuple[int, int, int, int]] = []

    class FakeResources:
        def __enter__(self) -> Path:
            return Path("/tmp/fake_vision_ocr.swift")

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    monkeypatch.setattr(
        "macagent.tools.wechat.resources.as_file",
        lambda _path: FakeResources(),
    )
    monkeypatch.setattr(
        "macagent.tools.wechat.resources.files",
        lambda _package: Path("/tmp"),
    )
    monkeypatch.setattr(
        handler,
        "_capture_region_text_blocks",
        lambda region: captured_regions.append(region) or [
            OCRTextBlock(text="hello", min_x=0.65, min_y=0.08, max_x=0.82, max_y=0.12),
            OCRTextBlock(text="earlier", min_x=0.12, min_y=0.30, max_x=0.28, max_y=0.34),
        ],
    )

    result = handler.handle(Action(name=ActionName.WECHAT_READ_LAST_MESSAGE))

    assert result.ok is True
    assert result.metadata["last_message"] == "hello"
    assert result.message == "当前聊天最后一条消息: hello"
    assert result.metadata["ocr_text"] == ["earlier", "hello"]
    assert captured_regions == [(400, 296, 670, 528)]
    assert executor.commands[0] == ["open", "-a", "WeChat"]
    assert executor.commands[1] == ["osascript", "-e", 'tell application "WeChat" to activate']
    assert executor.commands[2][0] == "osascript"
    assert len(executor.commands) == 3


def test_wechat_read_last_message_handler_opens_target_chat_before_reading(monkeypatch) -> None:
    executor = FakeExecutor()
    executor.responses["osascript"] = CompletedProcess(
        ["osascript"],
        0,
        stdout="100,200,1000,800",
        stderr="",
    )
    executor.responses["swift"] = CompletedProcess(
        ["swift"],
        0,
        stdout=json.dumps(
            [
                {"text": "晚上早点睡", "minX": 0.65, "minY": 0.08, "maxX": 0.90, "maxY": 0.12},
            ]
        ),
        stderr="",
    )
    handler = WeChatReadLastMessageHandler(executor)
    captured_regions: list[tuple[int, int, int, int]] = []
    clicked_points: list[tuple[int, int]] = []

    class FakeResources:
        def __enter__(self) -> Path:
            return Path("/tmp/fake_vision_ocr.swift")

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    monkeypatch.setattr(
        "macagent.tools.wechat.resources.as_file",
        lambda _path: FakeResources(),
    )
    monkeypatch.setattr(
        "macagent.tools.wechat.resources.files",
        lambda _package: Path("/tmp"),
    )
    monkeypatch.setattr(
        handler,
        "_capture_region_text_blocks",
        lambda region: captured_regions.append(region) or (
            [
                OCRTextBlock(text="纯洁友谊户", min_x=0.10, min_y=0.72, max_x=0.28, max_y=0.78),
                OCRTextBlock(text="群聊", min_x=0.05, min_y=0.18, max_x=0.12, max_y=0.22),
                OCRTextBlock(text="纯洁友谊户本圆⑤", min_x=0.16, min_y=0.06, max_x=0.45, max_y=0.12),
            ]
            if len(captured_regions) == 1
            else [
                OCRTextBlock(text="晚上早点睡", min_x=0.65, min_y=0.08, max_x=0.90, max_y=0.12),
            ]
        ),
    )
    monkeypatch.setattr(handler, "_click_at", lambda x, y: clicked_points.append((x, y)))

    result = handler.handle(Action(name=ActionName.WECHAT_READ_LAST_MESSAGE, params={"contact": "纯洁友谊户"}))

    assert result.ok is True
    assert result.metadata["contact"] == "纯洁友谊户"
    assert result.message == "纯洁友谊户 最后一条消息: 晚上早点睡"
    assert captured_regions == [
        (120, 216, 520, 576),
        (400, 296, 670, 528),
    ]
    assert clicked_points == [(218, 360)]
    search_scripts = [command for command in executor.commands if command[0] == "osascript" and "contactName" in command[2]]
    assert len(search_scripts) == 1
    assert "纯洁友谊户" in search_scripts[0][2]
    assert ["osascript", "-e", "delay 1"] in executor.commands
