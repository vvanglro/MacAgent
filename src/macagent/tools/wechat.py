from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from macagent.domain.errors import ExecutionError
from macagent.domain.models import Action, ActionName, ActionResult
from macagent.tools.executor import CommandExecutor


@dataclass(frozen=True)
class OCRTextBlock:
    text: str
    min_x: float
    min_y: float
    max_x: float
    max_y: float


class WeChatOpenHandler:
    def __init__(self, executor: CommandExecutor) -> None:
        self.executor = executor

    def handle(self, action: Action) -> ActionResult:
        self.executor.run_or_raise(["open", "-a", "WeChat"])
        script = 'tell application "WeChat" to activate'
        self.executor.run_or_raise(["osascript", "-e", script], timeout=20)
        return ActionResult(ok=True, action=ActionName.WECHAT_OPEN, message="微信已打开")


class WeChatReadLastMessageHandler:
    def __init__(self, executor: CommandExecutor) -> None:
        self.executor = executor

    def handle(self, action: Action) -> ActionResult:
        contact = str(action.params.get("contact", "")).strip()
        self.executor.run_or_raise(["open", "-a", "WeChat"])
        self.executor.run_or_raise(["osascript", "-e", _wechat_activate_script()], timeout=20)
        window_bounds = None
        if contact:
            bounds_result = self.executor.run_or_raise(["osascript", "-e", _wechat_window_bounds_script()], timeout=20)
            window_bounds = _parse_window_bounds(bounds_result.stdout)
            self._open_chat_from_search(contact, window_bounds)

        bounds_result = self.executor.run_or_raise(["osascript", "-e", _wechat_window_bounds_script()], timeout=20)
        window_bounds = _parse_window_bounds(bounds_result.stdout)
        capture_region = _chat_capture_region(window_bounds)
        blocks = self._capture_region_text_blocks(capture_region)
        message = _extract_last_message(blocks)
        ocr_text = _collect_ocr_text(blocks)

        return ActionResult(
            ok=True,
            action=ActionName.WECHAT_READ_LAST_MESSAGE,
            message=(
                f"{contact} 最后一条消息: {message}"
                if contact
                else f"当前聊天最后一条消息: {message}"
            ),
            metadata={
                "last_message": message,
                "contact": contact or None,
                "ocr_text": ocr_text,
            },
        )

    def _recognize_text_blocks(self, image_path: Path) -> list[OCRTextBlock]:
        with resources.as_file(resources.files("macagent.tools").joinpath("vision_ocr.swift")) as script_path:
            result = self.executor.run_or_raise(
                ["swift", str(script_path), str(image_path)],
                timeout=30,
            )
        return _parse_ocr_blocks(result.stdout)

    def _capture_region_text_blocks(self, region: tuple[int, int, int, int]) -> list[OCRTextBlock]:
        temp_fd, temp_path = tempfile.mkstemp(prefix="macagent-wechat-", suffix=".png")
        os.close(temp_fd)
        screenshot_path = Path(temp_path)
        try:
            self.executor.run_or_raise(
                ["screencapture", "-x", "-R", _format_region(region), str(screenshot_path)],
                timeout=20,
            )
            return self._recognize_text_blocks(screenshot_path)
        finally:
            screenshot_path.unlink(missing_ok=True)

    def _click_at(self, x: int, y: int) -> None:
        with resources.as_file(resources.files("macagent.tools").joinpath("mouse_click.swift")) as script_path:
            self.executor.run_or_raise(
                ["swift", str(script_path), str(x), str(y)],
                timeout=10,
            )

    def _open_chat_from_search(self, contact: str, window_bounds: tuple[int, int, int, int]) -> None:
        self.executor.run_or_raise(["osascript", "-e", _wechat_fill_search_box_script(contact)], timeout=30)
        search_region = _search_results_region(window_bounds)
        blocks = self._capture_region_text_blocks(search_region)
        target = _pick_contact_search_result(blocks, contact)
        if target is None:
            self.executor.run_or_raise(["osascript", "-e", _wechat_open_chat_script(contact)], timeout=30)
            return

        click_x, click_y = _search_result_click_point(target, search_region)
        self._click_at(click_x, click_y)
        self.executor.run_or_raise(["osascript", "-e", 'delay 1'], timeout=5)


class WeChatSendMessageHandler:
    def __init__(self, executor: CommandExecutor) -> None:
        self.executor = executor

    def handle(self, action: Action) -> ActionResult:
        contact = str(action.params.get("contact", "")).strip()
        text = str(action.params.get("text", "")).strip()
        if not contact:
            raise ExecutionError("contact is required")
        if not text:
            raise ExecutionError("text is required")

        self.executor.run_or_raise(["open", "-a", "WeChat"])
        script = _wechat_send_message_script(contact, text)
        self.executor.run_or_raise(["osascript", "-e", script], timeout=30)
        return ActionResult(ok=True, action=ActionName.WECHAT_SEND_MESSAGE, message=f"消息已发送给 {contact}")


def _escape(value: str) -> str:
    return value.replace('\\', '\\\\').replace('"', '\\"')


def _wechat_activate_script() -> str:
    return 'tell application "WeChat" to activate'


def _wechat_open_chat_script(contact: str) -> str:
    return (
        'set savedClipboard to the clipboard\n'
        'try\n'
        f'  set contactName to "{_escape(contact)}"\n'
        f'{_wechat_focus_contact_steps()}\n'
        '  set the clipboard to savedClipboard\n'
        'on error errMsg number errNum\n'
        '  set the clipboard to savedClipboard\n'
        '  error errMsg number errNum\n'
        'end try\n'
        f'{_wechat_search_helpers()}'
    )


def _wechat_fill_search_box_script(contact: str) -> str:
    return (
        'set savedClipboard to the clipboard\n'
        'try\n'
        f'  set contactName to "{_escape(contact)}"\n'
        '  tell application "WeChat" to activate\n'
        '  delay 1.5\n'
        '  tell application "System Events"\n'
        '    set the clipboard to contactName\n'
        '    keystroke "f" using command down\n'
        '    delay 0.5\n'
        '    keystroke "v" using command down\n'
        '  end tell\n'
        '  delay 1\n'
        '  set the clipboard to savedClipboard\n'
        'on error errMsg number errNum\n'
        '  set the clipboard to savedClipboard\n'
        '  error errMsg number errNum\n'
        'end try'
    )


def _wechat_send_message_script(contact: str, text: str) -> str:
    return (
        'set savedClipboard to the clipboard\n'
        'try\n'
        f'  set contactName to "{_escape(contact)}"\n'
        f'  set msgText to "{_escape(text)}"\n'
        f'{_wechat_focus_contact_steps()}\n'
        '  tell application "System Events"\n'
        '    set the clipboard to msgText\n'
        '    keystroke "v" using command down\n'
        '    delay 0.5\n'
        '    key code 36\n'
        '  end tell\n'
        '  set the clipboard to savedClipboard\n'
        'on error errMsg number errNum\n'
        '  set the clipboard to savedClipboard\n'
        '  error errMsg number errNum\n'
        'end try\n'
        f'{_wechat_search_helpers()}'
    )


def _wechat_focus_contact_steps() -> str:
    return (
        '  tell application "WeChat" to activate\n'
        '  delay 1.5\n'
        '  tell application "System Events"\n'
        '    set the clipboard to contactName\n'
        '    keystroke "f" using command down\n'
        '    delay 0.5\n'
        '    keystroke "v" using command down\n'
        '    delay 1\n'
        '    key code 36\n'
        '    delay 0.8\n'
        '    if my searchFieldStillVisible(contactName) then\n'
        '      key code 48\n'
        '      delay 0.2\n'
        '      key code 36\n'
        '      delay 0.8\n'
        '    end if\n'
        '    if my searchFieldStillVisible(contactName) then\n'
        '      key code 125\n'
        '      delay 0.2\n'
        '      key code 36\n'
        '      delay 0.8\n'
        '    end if\n'
        '  end tell\n'
        '  delay 1'
    )


def _wechat_search_helpers() -> str:
    return (
        'on searchFieldStillVisible(expectedValue)\n'
        '  tell application "System Events"\n'
        '    tell process "WeChat"\n'
        '      try\n'
        '        repeat with fieldRef in text fields of front window\n'
        '          try\n'
        '            set fieldValue to value of fieldRef as text\n'
        '            if fieldValue contains expectedValue then return true\n'
        '          end try\n'
        '        end repeat\n'
        '      end try\n'
        '    end tell\n'
        '  end tell\n'
        '  return false\n'
        'end searchFieldStillVisible'
    )


def _wechat_window_bounds_script() -> str:
    return (
        'tell application "System Events"\n'
        '  tell process "WeChat"\n'
        '    if (count of windows) is 0 then error "WeChat window not found"\n'
        '    set frontWindow to front window\n'
        '    set {xPos, yPos} to position of frontWindow\n'
        '    set {winWidth, winHeight} to size of frontWindow\n'
        '    return (xPos as string) & "," & (yPos as string) & "," & (winWidth as string) & "," & (winHeight as string)\n'
        '  end tell\n'
        'end tell'
    )


def _parse_window_bounds(raw: str) -> tuple[int, int, int, int]:
    parts = [part.strip() for part in raw.strip().split(",") if part.strip()]
    if len(parts) != 4:
        raise ExecutionError(f"Unable to parse WeChat window bounds: {raw.strip() or '<empty>'}")

    try:
        x, y, width, height = (int(float(part)) for part in parts)
    except ValueError as exc:
        raise ExecutionError(f"Unable to parse WeChat window bounds: {raw.strip() or '<empty>'}") from exc

    if width <= 0 or height <= 0:
        raise ExecutionError("WeChat window bounds are invalid")

    return (x, y, width, height)


def _chat_capture_region(window_bounds: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    x, y, width, height = window_bounds
    left = x + int(width * 0.30)
    top = y + int(height * 0.12)
    capture_width = max(1, int(width * 0.67))
    capture_height = max(1, int(height * 0.66))
    return (left, top, capture_width, capture_height)


def _search_results_region(window_bounds: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    x, y, width, height = window_bounds
    left = x + int(width * 0.02)
    top = y + int(height * 0.02)
    capture_width = max(1, int(width * 0.52))
    capture_height = max(1, int(height * 0.72))
    return (left, top, capture_width, capture_height)


def _format_region(region: tuple[int, int, int, int]) -> str:
    return ",".join(str(value) for value in region)


def _parse_ocr_blocks(raw: str) -> list[OCRTextBlock]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ExecutionError("OCR output was not valid JSON") from exc

    blocks: list[OCRTextBlock] = []
    for item in payload:
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        blocks.append(
            OCRTextBlock(
                text=text,
                min_x=float(item["minX"]),
                min_y=float(item["minY"]),
                max_x=float(item["maxX"]),
                max_y=float(item["maxY"]),
            )
        )
    return blocks


def _extract_last_message(blocks: list[OCRTextBlock]) -> str:
    message_blocks = [block for block in blocks if not _is_probable_timestamp(block)]
    if not message_blocks:
        raise ExecutionError("No readable message found in the current WeChat chat window")

    sorted_blocks = sorted(message_blocks, key=lambda block: (block.min_y, block.min_x))
    anchor = sorted_blocks[0]
    cluster = [anchor]

    for block in sorted_blocks[1:]:
        vertical_gap = block.min_y - cluster[-1].max_y
        if vertical_gap > 0.045:
            break
        cluster.append(block)

    cluster.sort(key=lambda block: (-block.min_y, block.min_x))
    message = " ".join(block.text for block in cluster).strip()
    if not message:
        raise ExecutionError("No readable message found in the current WeChat chat window")
    return message


def _collect_ocr_text(blocks: list[OCRTextBlock]) -> list[str]:
    return [block.text for block in sorted(blocks, key=lambda block: (-block.min_y, block.min_x))]


def _is_probable_timestamp(block: OCRTextBlock) -> bool:
    text = block.text.strip()
    if not re.fullmatch(r"\d{1,2}:\d{2}", text):
        return False
    center_x = (block.min_x + block.max_x) / 2
    return 0.15 <= center_x <= 0.85


def _pick_contact_search_result(blocks: list[OCRTextBlock], contact: str) -> OCRTextBlock | None:
    normalized_contact = contact.strip()
    if not normalized_contact:
        return None

    candidates = [
        block
        for block in blocks
        if normalized_contact in block.text and _block_center_y(block) < 0.88
    ]
    if not candidates:
        return None

    group_heading = next((block for block in blocks if block.text.strip() == "群聊"), None)
    if group_heading is not None:
        contact_candidates = [
            block
            for block in candidates
            if _block_center_y(block) > _block_center_y(group_heading)
        ]
        if contact_candidates:
            return min(contact_candidates, key=lambda block: _search_result_rank(block, normalized_contact))

        group_candidates = [
            block
            for block in candidates
            if _block_center_y(block) < _block_center_y(group_heading)
        ]
        if group_candidates:
            return min(group_candidates, key=lambda block: _search_result_rank(block, normalized_contact))

    return min(candidates, key=lambda block: _search_result_rank(block, normalized_contact))


def _search_result_click_point(
    block: OCRTextBlock,
    region: tuple[int, int, int, int],
) -> tuple[int, int]:
    left, top, width, height = region
    center_x = (block.min_x + block.max_x) / 2
    center_y = (block.min_y + block.max_y) / 2
    absolute_x = left + int(width * center_x)
    absolute_y = top + int(height * (1 - center_y))
    return (absolute_x, absolute_y)


def _block_center_y(block: OCRTextBlock) -> float:
    return (block.min_y + block.max_y) / 2


def _search_result_rank(block: OCRTextBlock, contact: str) -> tuple[int, int, float]:
    text = block.text.strip()
    if text == contact:
        match_priority = 0
    elif text.startswith(contact):
        match_priority = 1
    else:
        match_priority = 2

    return (match_priority, len(text), -_block_center_y(block))
