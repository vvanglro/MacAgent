from __future__ import annotations

import base64
import json
import os
import re
import tempfile
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

from macagent.domain.errors import ExecutionError
from macagent.domain.models import Action, ActionName, ActionResult
from macagent.reporting import Reporter, emit_progress
from macagent.tools.executor import CommandExecutor


@dataclass(frozen=True)
class OCRTextBlock:
    text: str
    min_x: float
    min_y: float
    max_x: float
    max_y: float


@dataclass(frozen=True)
class VisualReadResult:
    incoming_messages: list[str]
    ocr_text: list[str]
    summary: str | None = None
    reply_suggestion: str | None = None


class WeChatChatVisionReader:
    def __init__(
        self,
        model: str | None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        if not model:
            raise ExecutionError("vision model is required")

        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ExecutionError("Vision model requested but dependency is not installed") from exc

        client_kwargs: dict[str, str] = {}
        if api_key:
            client_kwargs["api_key"] = api_key
        if base_url:
            client_kwargs["base_url"] = base_url

        self.client = OpenAI(**client_kwargs)
        self.model = model

    def read_messages(self, image_path: Path, mode: str = "all", instruction: str | None = None) -> VisualReadResult:
        payload = self._request_payload(image_path, mode=mode, instruction=instruction)
        incoming_messages = _clean_text_list(payload.get("incoming_messages"))
        ocr_text = _clean_text_list(payload.get("ocr_text"))
        summary = str(payload.get("summary", "")).strip() or None
        reply_suggestion = str(payload.get("reply_suggestion", "")).strip() or None

        if mode not in {"summary", "reply_advice"} and not incoming_messages:
            raise ExecutionError("Vision model could not find any incoming messages in the chat screenshot")

        if not ocr_text:
            ocr_text = incoming_messages.copy()

        return VisualReadResult(
            incoming_messages=incoming_messages,
            ocr_text=ocr_text,
            summary=summary,
            reply_suggestion=reply_suggestion,
        )

    def _request_payload(self, image_path: Path, mode: str, instruction: str | None) -> dict[str, Any]:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": self._system_prompt()},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": self._user_prompt(mode=mode, instruction=instruction),
                            },
                            {"type": "image_url", "image_url": {"url": _image_path_to_data_url(image_path)}},
                        ],
                    },
                ],
            )
        except Exception as exc:  # pragma: no cover - SDK/provider failures
            raise ExecutionError("Vision model request failed") from exc

        try:
            content = response.choices[0].message.content
            payload = json.loads(content)
        except Exception as exc:  # pragma: no cover - network + provider failures
            raise ExecutionError("Vision model output was not valid JSON") from exc

        if not isinstance(payload, dict):
            raise ExecutionError("Vision model output must be a JSON object")
        return payload

    def _system_prompt(self) -> str:
        return (
            "You analyze a WeChat desktop chat screenshot. "
            "Return JSON only with keys incoming_messages, ocr_text, summary, and reply_suggestion. "
            "incoming_messages must be an array of visible left-side received messages only, ordered from oldest to newest. "
            "If a left-side bubble is an emoji, sticker, image, or other non-text content, describe it briefly in Chinese instead of omitting it. "
            "ocr_text must be an array of all visible readable text snippets from the screenshot, ordered from top to bottom. "
            "summary must be a concise Chinese summary of the visible conversation when the user asks for a summary; otherwise return an empty string. "
            "reply_suggestion must be a concise, natural Chinese suggestion for what the user could say next when they ask how to continue chatting; otherwise return an empty string. "
            "Ignore timestamps as messages."
        )

    def _user_prompt(self, mode: str, instruction: str | None) -> str:
        intent_text = instruction.strip() if instruction else ""
        if mode == "last":
            goal = "Return the latest visible incoming message from the left side."
        elif mode == "summary":
            goal = "Summarize what the visible conversation is about, using both left-side and right-side content."
        elif mode == "reply_advice":
            goal = "Understand what both sides are talking about and suggest a natural next reply in Chinese for the current user."
        else:
            goal = "Return all visible incoming messages from the left side."

        return (
            "Read this WeChat chat screenshot. "
            f"{goal} "
            "Treat right-side bubbles as messages sent by the current user. "
            "Ignore avatars and app chrome. "
            f"User request: {intent_text or '读取当前聊天内容'}"
        )


class WeChatOpenHandler:
    def __init__(self, executor: CommandExecutor, reporter: Reporter | None = None) -> None:
        self.executor = executor
        self.reporter = reporter

    def handle(self, action: Action) -> ActionResult:
        emit_progress(self.reporter, "正在打开并激活微信")
        self.executor.run_or_raise(["open", "-a", "WeChat"])
        script = 'tell application "WeChat" to activate'
        self.executor.run_or_raise(["osascript", "-e", script], timeout=20)
        return ActionResult(ok=True, action=ActionName.WECHAT_OPEN, message="微信已打开")


class WeChatReadLastMessageHandler:
    def __init__(
        self,
        executor: CommandExecutor,
        vision_reader: WeChatChatVisionReader | None = None,
        reporter: Reporter | None = None,
    ) -> None:
        self.executor = executor
        self.vision_reader = vision_reader
        self.reporter = reporter

    def handle(self, action: Action) -> ActionResult:
        contact = str(action.params.get("contact", "")).strip()
        mode = str(action.params.get("mode", "all")).strip().lower() or "all"
        instruction = str(action.params.get("instruction", "")).strip()
        emit_progress(self.reporter, f"准备读取微信聊天内容，模式：{_mode_display_name(mode)}")
        self.executor.run_or_raise(["open", "-a", "WeChat"])
        self.executor.run_or_raise(["osascript", "-e", _wechat_activate_script()], timeout=20)
        window_bounds = None
        if contact:
            emit_progress(self.reporter, f"正在搜索并打开聊天：{contact}")
            bounds_result = self.executor.run_or_raise(["osascript", "-e", _wechat_window_bounds_script()], timeout=20)
            window_bounds = _parse_window_bounds(bounds_result.stdout)
            self._open_chat_from_search(contact, window_bounds)

        bounds_result = self.executor.run_or_raise(["osascript", "-e", _wechat_window_bounds_script()], timeout=20)
        window_bounds = _parse_window_bounds(bounds_result.stdout)
        capture_region = _chat_capture_region(window_bounds)
        emit_progress(self.reporter, "正在截取微信聊天区域")
        read_result, reader_backend = self._read_chat_messages(capture_region, mode=mode, instruction=instruction)
        incoming_messages = read_result.incoming_messages
        ocr_text = read_result.ocr_text
        summary = read_result.summary
        reply_suggestion = read_result.reply_suggestion
        emit_progress(self.reporter, f"聊天分析完成，识别后端：{reader_backend}")

        if mode == "reply_advice":
            summary = summary or _fallback_summary_from_ocr_text(ocr_text)
            reply_suggestion = reply_suggestion or _fallback_reply_suggestion(summary, ocr_text, incoming_messages)
            if not summary and not reply_suggestion:
                raise ExecutionError("No readable chat content found in the current WeChat chat window")
            message = (
                f"对方刚才主要在说：{summary or '当前截图里主要是表情或非文字内容'}\n"
                f"你可以这样继续聊：{reply_suggestion or '先接住对方刚才的点，再顺着问一句。'}"
            )
        elif mode == "summary":
            message = summary or _fallback_summary_from_ocr_text(ocr_text)
            if not message:
                raise ExecutionError("No readable chat content found in the current WeChat chat window")
        elif mode == "last":
            if not incoming_messages:
                raise ExecutionError("No readable incoming message found in the current WeChat chat window")
            message = incoming_messages[-1]
        else:
            if not incoming_messages:
                raise ExecutionError("No readable incoming message found in the current WeChat chat window")
            message = _format_messages_output(incoming_messages)

        return ActionResult(
            ok=True,
            action=ActionName.WECHAT_READ_LAST_MESSAGE,
            message=(
                f"{contact} 继续聊天建议：\n{message}"
                if mode == "reply_advice" and contact
                else f"当前聊天继续聊天建议：\n{message}"
                if mode == "reply_advice"
                else f"{contact} 可见聊天内容摘要: {message}"
                if mode == "summary" and contact
                else f"当前聊天可见内容摘要: {message}"
                if mode == "summary"
                else f"{contact} 最后一条消息: {message}"
                if mode == "last" and contact
                else f"当前聊天最后一条消息: {message}"
                if mode == "last"
                else f"{contact} 收到的消息:\n{message}"
                if contact
                else f"当前聊天收到的消息:\n{message}"
            ),
            metadata={
                "last_message": incoming_messages[-1] if incoming_messages else None,
                "incoming_messages": incoming_messages,
                "contact": contact or None,
                "mode": mode,
                "ocr_text": ocr_text,
                "summary": summary or None,
                "reply_suggestion": reply_suggestion or None,
                "reader_backend": reader_backend,
            },
        )

    def _read_chat_messages(
        self,
        region: tuple[int, int, int, int],
        mode: str,
        instruction: str,
    ) -> tuple[VisualReadResult, str]:
        screenshot_path = self._capture_region_image(region)
        try:
            if self.vision_reader is not None:
                try:
                    emit_progress(self.reporter, "正在使用视觉模型分析截图")
                    result = self.vision_reader.read_messages(
                        screenshot_path,
                        mode=mode,
                        instruction=instruction,
                    )
                    return result, "vision_model"
                except ExecutionError:
                    emit_progress(self.reporter, "视觉模型分析失败，回退到本地 OCR")
                    pass

            emit_progress(self.reporter, "正在使用本地 OCR 识别截图")
            blocks = self._recognize_text_blocks(screenshot_path)
            incoming_messages = _extract_incoming_messages(blocks, strict=mode not in {"summary", "reply_advice"})
            ocr_text = _collect_ocr_text(blocks)
            summary = _fallback_summary_from_ocr_text(ocr_text) if mode in {"summary", "reply_advice"} else None
            reply_suggestion = (
                _fallback_reply_suggestion(summary, ocr_text, incoming_messages)
                if mode == "reply_advice"
                else None
            )
            return (
                VisualReadResult(
                    incoming_messages=incoming_messages,
                    ocr_text=ocr_text,
                    summary=summary,
                    reply_suggestion=reply_suggestion,
                ),
                "macos_vision",
            )
        finally:
            screenshot_path.unlink(missing_ok=True)

    def _recognize_text_blocks(self, image_path: Path) -> list[OCRTextBlock]:
        with resources.as_file(resources.files("macagent.tools").joinpath("vision_ocr.swift")) as script_path:
            result = self.executor.run_or_raise(
                ["swift", str(script_path), str(image_path)],
                timeout=30,
            )
        return _parse_ocr_blocks(result.stdout)

    def _capture_region_image(self, region: tuple[int, int, int, int]) -> Path:
        temp_fd, temp_path = tempfile.mkstemp(prefix="macagent-wechat-", suffix=".png")
        os.close(temp_fd)
        screenshot_path = Path(temp_path)
        self.executor.run_or_raise(
            ["screencapture", "-x", "-R", _format_region(region), str(screenshot_path)],
            timeout=20,
        )
        return screenshot_path

    def _capture_region_text_blocks(self, region: tuple[int, int, int, int]) -> list[OCRTextBlock]:
        screenshot_path = self._capture_region_image(region)
        try:
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
        emit_progress(self.reporter, f"正在输入搜索词：{contact}")
        self.executor.run_or_raise(["osascript", "-e", _wechat_fill_search_box_script(contact)], timeout=30)
        search_region = _search_results_region(window_bounds)
        emit_progress(self.reporter, "正在识别搜索结果并定位目标聊天")
        blocks = self._capture_region_text_blocks(search_region)
        target = _pick_contact_search_result(blocks, contact)
        if target is None:
            emit_progress(self.reporter, "未命中可点击的搜索结果，回退到键盘导航")
            self.executor.run_or_raise(["osascript", "-e", _wechat_open_chat_script(contact)], timeout=30)
            return

        click_x, click_y = _search_result_click_point(target, search_region)
        emit_progress(self.reporter, f"已定位到目标聊天：{target.text}")
        self._click_at(click_x, click_y)
        self.executor.run_or_raise(["osascript", "-e", 'delay 1'], timeout=5)


class WeChatSendMessageHandler:
    def __init__(self, executor: CommandExecutor, reporter: Reporter | None = None) -> None:
        self.executor = executor
        self.reporter = reporter

    def handle(self, action: Action) -> ActionResult:
        contact = str(action.params.get("contact", "")).strip()
        text = str(action.params.get("text", "")).strip()
        if not contact:
            raise ExecutionError("contact is required")
        if not text:
            raise ExecutionError("text is required")

        emit_progress(self.reporter, f"正在打开微信并准备给 {contact} 发送消息")
        self.executor.run_or_raise(["open", "-a", "WeChat"])
        self.executor.run_or_raise(["osascript", "-e", _wechat_activate_script()], timeout=20)
        self.executor.run_or_raise(["osascript", "-e", _wechat_open_chat_script(contact)], timeout=30)
        bounds_result = self.executor.run_or_raise(["osascript", "-e", _wechat_window_bounds_script()], timeout=20)
        window_bounds = _parse_window_bounds(bounds_result.stdout)
        emit_progress(self.reporter, "正在聚焦微信输入框")
        self._focus_input_box(window_bounds)
        emit_progress(self.reporter, "正在粘贴消息并发送")
        self.executor.run_or_raise(["osascript", "-e", _wechat_paste_and_send_script(text)], timeout=30)
        return ActionResult(ok=True, action=ActionName.WECHAT_SEND_MESSAGE, message=f"消息已发送给 {contact}")

    def _focus_input_box(self, window_bounds: tuple[int, int, int, int]) -> None:
        click_x, click_y = _chat_input_click_point(window_bounds)
        self._click_at(click_x, click_y)
        self.executor.run_or_raise(["osascript", "-e", "delay 0.3"], timeout=5)

    def _click_at(self, x: int, y: int) -> None:
        with resources.as_file(resources.files("macagent.tools").joinpath("mouse_click.swift")) as script_path:
            self.executor.run_or_raise(
                ["swift", str(script_path), str(x), str(y)],
                timeout=10,
            )


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


def _wechat_paste_and_send_script(text: str) -> str:
    return (
        'set savedClipboard to the clipboard\n'
        'try\n'
        f'  set msgText to "{_escape(text)}"\n'
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
        'end try'
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


def _chat_input_click_point(window_bounds: tuple[int, int, int, int]) -> tuple[int, int]:
    x, y, width, height = window_bounds
    click_x = x + int(width * 0.62)
    click_y = y + int(height * 0.92)
    return (click_x, click_y)


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


def _extract_incoming_messages(blocks: list[OCRTextBlock], strict: bool = True) -> list[str]:
    message_blocks = [
        block
        for block in blocks
        if not _is_probable_timestamp(block) and _is_incoming_message_block(block)
    ]
    if not message_blocks and strict:
        raise ExecutionError("No readable message found in the current WeChat chat window")
    if not message_blocks:
        return []

    sorted_blocks = sorted(message_blocks, key=lambda block: (block.min_y, block.min_x))
    clusters: list[list[OCRTextBlock]] = []
    current_cluster: list[OCRTextBlock] = []

    for block in sorted_blocks:
        if not current_cluster:
            current_cluster = [block]
            continue

        vertical_gap = block.min_y - current_cluster[-1].max_y
        if vertical_gap > 0.045:
            clusters.append(current_cluster)
            current_cluster = [block]
            continue

        current_cluster.append(block)

    if current_cluster:
        clusters.append(current_cluster)

    messages: list[str] = []
    for cluster in reversed(clusters):
        cluster.sort(key=lambda block: (-block.min_y, block.min_x))
        message = " ".join(block.text for block in cluster).strip()
        if message:
            messages.append(message)

    if not messages and strict:
        raise ExecutionError("No readable message found in the current WeChat chat window")
    if not messages:
        return []

    return messages


def _collect_ocr_text(blocks: list[OCRTextBlock]) -> list[str]:
    return [block.text for block in sorted(blocks, key=lambda block: (-block.min_y, block.min_x))]


def _is_probable_timestamp(block: OCRTextBlock) -> bool:
    text = block.text.strip()
    if not re.fullmatch(r"\d{1,2}:\d{2}", text):
        return False
    center_x = (block.min_x + block.max_x) / 2
    return 0.15 <= center_x <= 0.85


def _is_incoming_message_block(block: OCRTextBlock) -> bool:
    center_x = (block.min_x + block.max_x) / 2
    return center_x < 0.55


def _format_messages_output(messages: list[str]) -> str:
    return "\n".join(f"{index}. {message}" for index, message in enumerate(messages, start=1))


def _fallback_summary_from_ocr_text(ocr_text: list[str]) -> str:
    filtered: list[str] = []
    seen: set[str] = set()
    for text in ocr_text:
        cleaned = text.strip()
        if not cleaned or re.fullmatch(r"\d{1,2}:\d{2}", cleaned):
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        filtered.append(cleaned)

    if not filtered:
        return ""

    if len(filtered) == 1:
        return filtered[0]

    preview = "；".join(filtered[:5])
    if len(filtered) > 5:
        preview += "；……"
    return preview


def _fallback_reply_suggestion(
    summary: str | None,
    ocr_text: list[str],
    incoming_messages: list[str],
) -> str:
    latest_incoming = incoming_messages[-1] if incoming_messages else ""
    if latest_incoming:
        return f"可以先接住对方刚才这句“{latest_incoming}”，再顺着问一句你的想法或者补充一个轻松回应。"

    if summary:
        return f"可以先回应“{summary[:18]}”这个点，再补一句你的看法，顺势把话题继续下去。"

    if ocr_text:
        return f"可以先接住截图里提到的“{ocr_text[0]}”，再问一句对方现在怎么想。"

    return "可以先接住对方刚才的情绪或表情，再顺着问一句近况或想法。"


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


def _image_path_to_data_url(image_path: Path) -> str:
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _clean_text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    cleaned: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            cleaned.append(text)
    return cleaned


def _mode_display_name(mode: str) -> str:
    return {
        "last": "最后一条消息",
        "all": "全部收到的消息",
        "summary": "聊天摘要",
        "reply_advice": "聊天续聊建议",
    }.get(mode, mode)
