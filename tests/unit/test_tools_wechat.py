import json
import sys
from pathlib import Path
from subprocess import CompletedProcess
from types import SimpleNamespace

import pytest

from macagent.domain.errors import ExecutionError
from macagent.domain.models import Action, ActionName
from macagent.tools.wechat import (
    OCRTextBlock,
    VisualReadResult,
    WeChatChatVisionReader,
    WeChatOpenHandler,
    WeChatReadLastMessageHandler,
    WeChatSendMessageHandler,
    _chat_capture_region,
    _collect_ocr_text,
    _extract_incoming_messages,
    _format_messages_output,
    _is_incoming_message_block,
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


def test_extract_incoming_messages_joins_multiline_left_bubble_only() -> None:
    messages = _extract_incoming_messages(
        [
            OCRTextBlock(text="第二行", min_x=0.18, min_y=0.08, max_x=0.34, max_y=0.12),
            OCRTextBlock(text="第一行", min_x=0.18, min_y=0.13, max_x=0.34, max_y=0.17),
            OCRTextBlock(text="我发的", min_x=0.72, min_y=0.06, max_x=0.88, max_y=0.10),
            OCRTextBlock(text="更早的消息", min_x=0.10, min_y=0.35, max_x=0.30, max_y=0.39),
        ]
    )

    assert messages == ["更早的消息", "第一行 第二行"]


def test_extract_incoming_messages_ignores_centered_timestamp_labels() -> None:
    messages = _extract_incoming_messages(
        [
            OCRTextBlock(text="14:28", min_x=0.45, min_y=0.08, max_x=0.55, max_y=0.12),
            OCRTextBlock(text="hello", min_x=0.20, min_y=0.07, max_x=0.37, max_y=0.11),
            OCRTextBlock(text="更早的消息", min_x=0.10, min_y=0.30, max_x=0.30, max_y=0.34),
        ]
    )

    assert messages == ["更早的消息", "hello"]


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


def test_is_incoming_message_block_prefers_left_side_only() -> None:
    assert _is_incoming_message_block(
        OCRTextBlock(text="左侧", min_x=0.12, min_y=0.20, max_x=0.30, max_y=0.24)
    ) is True
    assert _is_incoming_message_block(
        OCRTextBlock(text="右侧", min_x=0.70, min_y=0.20, max_x=0.88, max_y=0.24)
    ) is False


def test_format_messages_output_numbers_all_messages() -> None:
    assert _format_messages_output(["第一条", "第二条"]) == "1. 第一条\n2. 第二条"


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


def test_wechat_read_last_message_handler_reads_all_incoming_messages_by_default(monkeypatch) -> None:
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
                {"text": "hello", "minX": 0.18, "minY": 0.08, "maxX": 0.35, "maxY": 0.12},
                {"text": "earlier", "minX": 0.12, "minY": 0.30, "maxX": 0.28, "maxY": 0.34},
            ]
        ),
        stderr="",
    )
    handler = WeChatReadLastMessageHandler(executor)
    captured_regions: list[tuple[int, int, int, int]] = []
    monkeypatch.setattr(
        handler,
        "_read_chat_messages",
        lambda region, mode, instruction: captured_regions.append(region) or (
            VisualReadResult(incoming_messages=["earlier", "hello"], ocr_text=["earlier", "hello"]),
            "macos_vision",
        ),
    )

    result = handler.handle(Action(name=ActionName.WECHAT_READ_LAST_MESSAGE))

    assert result.ok is True
    assert result.metadata["last_message"] == "hello"
    assert result.metadata["incoming_messages"] == ["earlier", "hello"]
    assert result.message == "当前聊天收到的消息:\n1. earlier\n2. hello"
    assert result.metadata["ocr_text"] == ["earlier", "hello"]
    assert captured_regions == [(400, 296, 670, 528)]
    assert executor.commands[0] == ["open", "-a", "WeChat"]
    assert executor.commands[1] == ["osascript", "-e", 'tell application "WeChat" to activate']
    assert executor.commands[2][0] == "osascript"
    assert len(executor.commands) == 3


def test_wechat_read_last_message_handler_returns_latest_incoming_message_only_when_requested(monkeypatch) -> None:
    executor = FakeExecutor()
    executor.responses["osascript"] = CompletedProcess(
        ["osascript"],
        0,
        stdout="100,200,1000,800",
        stderr="",
    )
    handler = WeChatReadLastMessageHandler(executor)
    captured_regions: list[tuple[int, int, int, int]] = []
    monkeypatch.setattr(
        handler,
        "_read_chat_messages",
        lambda region, mode, instruction: captured_regions.append(region) or (
            VisualReadResult(
                incoming_messages=["earlier", "hello"],
                ocr_text=["earlier", "我发的", "hello"],
            ),
            "macos_vision",
        ),
    )

    result = handler.handle(Action(name=ActionName.WECHAT_READ_LAST_MESSAGE, params={"mode": "last"}))

    assert result.ok is True
    assert result.metadata["last_message"] == "hello"
    assert result.metadata["incoming_messages"] == ["earlier", "hello"]
    assert result.message == "当前聊天最后一条消息: hello"
    assert result.metadata["mode"] == "last"
    assert captured_regions == [(400, 296, 670, 528)]


def test_wechat_read_last_message_handler_prefers_visual_reader_when_configured(tmp_path) -> None:
    executor = FakeExecutor()
    executor.responses["osascript"] = CompletedProcess(
        ["osascript"],
        0,
        stdout="100,200,1000,800",
        stderr="",
    )
    screenshot_path = tmp_path / "wechat.png"
    screenshot_path.write_bytes(b"fake-image")

    class FakeVisionReader:
        def __init__(self) -> None:
            self.paths: list[Path] = []

        def read_messages(self, image_path: Path, mode: str = "all", instruction: str | None = None) -> VisualReadResult:
            self.paths.append(image_path)
            return VisualReadResult(
                incoming_messages=["第一条", "第二条"],
                ocr_text=["全部识别文本", "第二条"],
            )

    vision_reader = FakeVisionReader()
    handler = WeChatReadLastMessageHandler(executor, vision_reader=vision_reader)
    handler._capture_region_image = lambda _region: screenshot_path  # type: ignore[method-assign]
    handler._recognize_text_blocks = lambda _image_path: (_ for _ in ()).throw(AssertionError("should not use local OCR"))  # type: ignore[method-assign]

    result = handler.handle(Action(name=ActionName.WECHAT_READ_LAST_MESSAGE))

    assert result.ok is True
    assert result.message == "当前聊天收到的消息:\n1. 第一条\n2. 第二条"
    assert result.metadata["incoming_messages"] == ["第一条", "第二条"]
    assert result.metadata["ocr_text"] == ["全部识别文本", "第二条"]
    assert result.metadata["reader_backend"] == "vision_model"
    assert vision_reader.paths == [screenshot_path]


def test_wechat_read_last_message_handler_falls_back_to_local_ocr_when_visual_reader_fails(tmp_path) -> None:
    executor = FakeExecutor()
    executor.responses["osascript"] = CompletedProcess(
        ["osascript"],
        0,
        stdout="100,200,1000,800",
        stderr="",
    )
    screenshot_path = tmp_path / "wechat.png"
    screenshot_path.write_bytes(b"fake-image")

    class FailingVisionReader:
        def read_messages(self, image_path: Path, mode: str = "all", instruction: str | None = None) -> VisualReadResult:
            raise ExecutionError(f"vision failed for {image_path.name}")

    handler = WeChatReadLastMessageHandler(executor, vision_reader=FailingVisionReader())
    handler._capture_region_image = lambda _region: screenshot_path  # type: ignore[method-assign]
    handler._recognize_text_blocks = lambda _image_path: [  # type: ignore[method-assign]
        OCRTextBlock(text="收到的", min_x=0.18, min_y=0.08, max_x=0.35, max_y=0.12),
        OCRTextBlock(text="我发的", min_x=0.72, min_y=0.16, max_x=0.88, max_y=0.20),
    ]

    result = handler.handle(Action(name=ActionName.WECHAT_READ_LAST_MESSAGE, params={"mode": "last"}))

    assert result.ok is True
    assert result.message == "当前聊天最后一条消息: 收到的"
    assert result.metadata["reader_backend"] == "macos_vision"


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
                {"text": "晚上早点睡", "minX": 0.18, "minY": 0.08, "maxX": 0.44, "maxY": 0.12},
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
                OCRTextBlock(text="晚上早点睡", min_x=0.18, min_y=0.08, max_x=0.44, max_y=0.12),
            ]
        ),
    )
    monkeypatch.setattr(
        handler,
        "_read_chat_messages",
        lambda region, mode, instruction: captured_regions.append(region) or (
            VisualReadResult(incoming_messages=["晚上早点睡"], ocr_text=["晚上早点睡"]),
            "macos_vision",
        ),
    )
    monkeypatch.setattr(handler, "_click_at", lambda x, y: clicked_points.append((x, y)))

    result = handler.handle(Action(name=ActionName.WECHAT_READ_LAST_MESSAGE, params={"contact": "纯洁友谊户", "mode": "last"}))

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


def test_wechat_chat_vision_reader_passes_openai_compatible_config(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeOpenAI:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)
            self.chat = None

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))

    reader = WeChatChatVisionReader(
        model="gpt-4.1-mini",
        api_key="vision-key",
        base_url="https://vision.example.com/v1",
    )

    assert reader.model == "gpt-4.1-mini"
    assert captured == {
        "api_key": "vision-key",
        "base_url": "https://vision.example.com/v1",
    }


def test_wechat_read_last_message_handler_summary_mode_uses_summary_text(monkeypatch) -> None:
    executor = FakeExecutor()
    executor.responses["osascript"] = CompletedProcess(
        ["osascript"],
        0,
        stdout="100,200,1000,800",
        stderr="",
    )
    handler = WeChatReadLastMessageHandler(executor)
    monkeypatch.setattr(handler, "_open_chat_from_search", lambda contact, window_bounds: None)

    monkeypatch.setattr(
        handler,
        "_read_chat_messages",
        lambda region, mode, instruction: (
            VisualReadResult(
                incoming_messages=["[表情: 可怜巴巴]", "[表情: 无语流汗]"],
                ocr_text=["得给你改个备注了", "emoji有点难搞"],
                summary="你们在聊给对方改备注，以及 emoji 不太好处理；对方主要发了两个表情回应。",
            ),
            "vision_model",
        ),
    )

    result = handler.handle(
        Action(
            name=ActionName.WECHAT_READ_LAST_MESSAGE,
            params={"contact": "沪上小牛爷", "mode": "summary", "instruction": "读取一下我和 沪上小牛爷 都聊了些什么内容"},
        )
    )

    assert result.ok is True
    assert result.message == "沪上小牛爷 可见聊天内容摘要: 你们在聊给对方改备注，以及 emoji 不太好处理；对方主要发了两个表情回应。"
    assert result.metadata["summary"] == "你们在聊给对方改备注，以及 emoji 不太好处理；对方主要发了两个表情回应。"
    assert result.metadata["reader_backend"] == "vision_model"


def test_wechat_read_last_message_handler_summary_mode_falls_back_to_visible_ocr_text() -> None:
    executor = FakeExecutor()
    executor.responses["osascript"] = CompletedProcess(
        ["osascript"],
        0,
        stdout="100,200,1000,800",
        stderr="",
    )
    handler = WeChatReadLastMessageHandler(executor)
    handler._capture_region_image = lambda _region: Path("/tmp/fake-wechat.png")  # type: ignore[method-assign]
    handler._recognize_text_blocks = lambda _image_path: [  # type: ignore[method-assign]
        OCRTextBlock(text="得给你改个备注了", min_x=0.70, min_y=0.18, max_x=0.88, max_y=0.24),
        OCRTextBlock(text="emoji有点难搞", min_x=0.70, min_y=0.28, max_x=0.88, max_y=0.34),
        OCRTextBlock(text="15:40", min_x=0.45, min_y=0.40, max_x=0.55, max_y=0.44),
    ]

    result = handler.handle(
        Action(
            name=ActionName.WECHAT_READ_LAST_MESSAGE,
            params={"mode": "summary", "instruction": "读取一下我和 沪上小牛爷 都聊了些什么内容"},
        )
    )

    assert result.ok is True
    assert result.message == "当前聊天可见内容摘要: emoji有点难搞；得给你改个备注了"
    assert result.metadata["reader_backend"] == "macos_vision"
