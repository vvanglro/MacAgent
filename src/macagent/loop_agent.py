from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from macagent.domain.errors import ExecutionError
from macagent.domain.models import Action, ActionName, ActionResult
from macagent.reporting import Reporter, emit_progress
from macagent.tools.wechat import WeChatReadLastMessageHandler, WeChatSendMessageHandler


Clock = Callable[[], datetime]
Sleeper = Callable[[float], None]


@dataclass(frozen=True)
class LoopRunSummary:
    log_path: Path
    rounds_completed: int
    replies_sent: int
    contact: str


@dataclass(frozen=True)
class LoopContextEntry:
    timestamp: str
    incoming_messages: list[str]
    summary: str | None = None
    sent_reply: str | None = None


class WeChatLoopAgent:
    def __init__(
        self,
        read_handler: WeChatReadLastMessageHandler,
        send_handler: WeChatSendMessageHandler,
        reporter: Reporter | None = None,
        sleep_fn: Sleeper = time.sleep,
        clock: Clock | None = None,
    ) -> None:
        self.read_handler = read_handler
        self.send_handler = send_handler
        self.reporter = reporter
        self.sleep_fn = sleep_fn
        self.clock = clock or datetime.now

    def run(
        self,
        contact: str,
        interval_seconds: int,
        rounds: int = 5,
        auto_send: bool = False,
        log_path: Path | None = None,
        cooldown_seconds: int = 180,
        context_rounds: int = 3,
        persona_file: Path | None = None,
    ) -> LoopRunSummary:
        normalized_contact = contact.strip()
        if not normalized_contact:
            raise ExecutionError("contact is required")
        if interval_seconds < 1:
            raise ExecutionError("interval_seconds must be at least 1")
        if rounds < 0:
            raise ExecutionError("rounds must be zero or a positive integer")
        if cooldown_seconds < 0:
            raise ExecutionError("cooldown_seconds must be zero or a positive integer")
        if context_rounds < 0:
            raise ExecutionError("context_rounds must be zero or a positive integer")

        started_at = self.clock()
        resolved_log_path = log_path or (
            Path.cwd() / f"macagent-loop-{_slugify_filename(normalized_contact)}-{_timestamp_slug(started_at)}.md"
        )
        resolved_persona_file = persona_file or (Path.cwd() / "macagent-wechat-owner-profile.md")
        context_entries = _load_context_entries(resolved_log_path)[-context_rounds:] if context_rounds else []
        persona_text = _load_persona_text(resolved_persona_file, required=persona_file is not None)
        if persona_text:
            emit_progress(self.reporter, f"已加载微信主人风格档案：{resolved_persona_file.name}")
        else:
            emit_progress(self.reporter, "未找到微信主人风格档案，使用默认回复风格")
        self._ensure_log_header(resolved_log_path, normalized_contact, interval_seconds, auto_send, started_at)

        last_signature: str | None = None
        last_incoming_signature = _incoming_signature_from_entries(context_entries)
        last_reply_at = _last_reply_timestamp(context_entries)
        successful_rounds = 0
        replies_sent = 0
        round_index = 0

        while rounds == 0 or round_index < rounds:
            round_index += 1
            round_time = self.clock()
            emit_progress(self.reporter, f"Loop 第 {round_index} 轮：正在读取 {normalized_contact} 的聊天内容")

            try:
                instruction = _build_loop_instruction(
                    contact=normalized_contact,
                    persona_text=persona_text,
                    context_entries=context_entries[-context_rounds:] if context_rounds else [],
                )
                read_result = self.read_handler.handle(
                    Action(
                        name=ActionName.WECHAT_READ_LAST_MESSAGE,
                        params={
                            "contact": normalized_contact,
                            "mode": "reply_advice",
                            "instruction": instruction,
                        },
                    )
                )
                successful_rounds += 1
            except ExecutionError as exc:
                self._append_log_entry(
                    resolved_log_path,
                    round_number=round_index,
                    round_time=round_time,
                    contact=normalized_contact,
                    changed=False,
                    read_result=None,
                    sent_reply=None,
                    error_text=str(exc),
                )
                emit_progress(self.reporter, f"第 {round_index} 轮读取失败：{exc}")
                if rounds != 0 and round_index >= rounds:
                    break
                emit_progress(self.reporter, f"等待 {interval_seconds} 秒后继续下一轮")
                self.sleep_fn(interval_seconds)
                continue

            signature = _content_signature(read_result)
            has_changed = signature != last_signature
            incoming_signature = _incoming_signature(read_result)
            has_new_incoming = incoming_signature != last_incoming_signature
            cooldown_active = (
                auto_send
                and last_reply_at is not None
                and cooldown_seconds > 0
                and (round_time - last_reply_at).total_seconds() < cooldown_seconds
            )
            sent_reply: str | None = None

            if has_changed:
                emit_progress(self.reporter, "检测到新的聊天内容或新的分析结果")
                last_signature = signature
                suggested_reply = str(read_result.metadata.get("reply_suggestion", "")).strip()
                if auto_send and not has_new_incoming:
                    emit_progress(self.reporter, "这轮没有检测到对方的新消息，跳过自动发送")
                elif auto_send and cooldown_active:
                    remaining = max(0, int(cooldown_seconds - (round_time - last_reply_at).total_seconds()))
                    emit_progress(self.reporter, f"仍在冷却期内，还需等待约 {remaining} 秒，跳过自动发送")
                elif auto_send and suggested_reply:
                    emit_progress(self.reporter, f"正在自动回复 {normalized_contact}")
                    send_result = self.send_handler.handle(
                        Action(
                            name=ActionName.WECHAT_SEND_MESSAGE,
                            params={"contact": normalized_contact, "text": suggested_reply},
                        )
                    )
                    sent_reply = suggested_reply
                    replies_sent += 1
                    last_reply_at = round_time
                    emit_progress(self.reporter, send_result.message)
                elif auto_send:
                    emit_progress(self.reporter, "这轮没有生成可发送的回复建议，跳过自动发送")
                else:
                    emit_progress(self.reporter, "已生成回复建议，当前为观察模式，未自动发送")
            else:
                emit_progress(self.reporter, "这一轮没有识别到新的聊天变化，跳过回复")

            last_incoming_signature = incoming_signature
            context_entry = LoopContextEntry(
                timestamp=round_time.isoformat(timespec="seconds"),
                incoming_messages=_clean_string_list(read_result.metadata.get("incoming_messages", [])),
                summary=str(read_result.metadata.get("summary", "")).strip() or None,
                sent_reply=sent_reply,
            )
            if context_rounds:
                context_entries.append(context_entry)
                context_entries = context_entries[-context_rounds:]

            self._append_log_entry(
                resolved_log_path,
                round_number=round_index,
                round_time=round_time,
                contact=normalized_contact,
                changed=has_changed,
                has_new_incoming=has_new_incoming,
                cooldown_active=cooldown_active,
                read_result=read_result,
                sent_reply=sent_reply,
                error_text=None,
            )

            if rounds != 0 and round_index >= rounds:
                break

            emit_progress(self.reporter, f"等待 {interval_seconds} 秒后继续下一轮")
            self.sleep_fn(interval_seconds)

        if successful_rounds == 0:
            raise ExecutionError("Loop agent did not complete any successful read rounds")

        return LoopRunSummary(
            log_path=resolved_log_path,
            rounds_completed=round_index,
            replies_sent=replies_sent,
            contact=normalized_contact,
        )

    def _ensure_log_header(
        self,
        log_path: Path,
        contact: str,
        interval_seconds: int,
        auto_send: bool,
        started_at: datetime,
    ) -> None:
        if log_path.exists():
            return

        log_path.write_text(
            "\n".join(
                [
                    f"# MacAgent Loop Log - {contact}",
                    "",
                    f"- Started At: {started_at.isoformat(timespec='seconds')}",
                    f"- Interval Seconds: {interval_seconds}",
                    f"- Auto Send: {'yes' if auto_send else 'no'}",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    def _append_log_entry(
        self,
        log_path: Path,
        round_number: int,
        round_time: datetime,
        contact: str,
        changed: bool,
        read_result: ActionResult | None,
        sent_reply: str | None,
        error_text: str | None,
        has_new_incoming: bool = False,
        cooldown_active: bool = False,
    ) -> None:
        lines = [
            f"## Round {round_number} - {round_time.isoformat(timespec='seconds')}",
            f"- Contact: {contact}",
            f"- Changed: {'yes' if changed else 'no'}",
            f"- New Incoming: {'yes' if has_new_incoming else 'no'}",
            f"- Cooldown Active: {'yes' if cooldown_active else 'no'}",
        ]

        if error_text:
            lines.append(f"- Error: {error_text}")
        elif read_result is not None:
            lines.extend(
                [
                    f"- Reader Backend: {read_result.metadata.get('reader_backend', 'unknown')}",
                    f"- Mode: {read_result.metadata.get('mode', 'unknown')}",
                    "",
                    "### Summary",
                    read_result.metadata.get("summary") or "_none_",
                    "",
                    "### Incoming Messages",
                    *_format_markdown_list(read_result.metadata.get("incoming_messages", [])),
                    "",
                    "### Reply Suggestion",
                    read_result.metadata.get("reply_suggestion") or "_none_",
                    "",
                    "### Sent Reply",
                    sent_reply or "_not sent_",
                    "",
                    "### Result Message",
                    read_result.message,
                    "",
                    _context_comment(
                        LoopContextEntry(
                            timestamp=round_time.isoformat(timespec="seconds"),
                            incoming_messages=_clean_string_list(read_result.metadata.get("incoming_messages", [])),
                            summary=str(read_result.metadata.get("summary", "")).strip() or None,
                            sent_reply=sent_reply,
                        )
                    ),
                ]
            )

        lines.extend(["", ""])
        with log_path.open("a", encoding="utf-8") as file:
            file.write("\n".join(lines))


def _format_markdown_list(items: object) -> list[str]:
    if not isinstance(items, list) or not items:
        return ["- _none_"]
    return [f"- {str(item).strip()}" for item in items if str(item).strip()] or ["- _none_"]


def _content_signature(result: ActionResult) -> str:
    payload = {
        "last_message": result.metadata.get("last_message"),
        "incoming_messages": result.metadata.get("incoming_messages"),
        "summary": result.metadata.get("summary"),
        "reply_suggestion": result.metadata.get("reply_suggestion"),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _slugify_filename(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in value.strip())
    compact = "-".join(part for part in cleaned.split("-") if part)
    return compact or "wechat-loop"


def _timestamp_slug(value: datetime) -> str:
    return value.strftime("%Y%m%d-%H%M%S")


def _incoming_signature(result: ActionResult) -> str:
    return json.dumps(_clean_string_list(result.metadata.get("incoming_messages", [])), ensure_ascii=False)


def _incoming_signature_from_entries(entries: list[LoopContextEntry]) -> str | None:
    if not entries:
        return None
    return json.dumps(entries[-1].incoming_messages, ensure_ascii=False)


def _last_reply_timestamp(entries: list[LoopContextEntry]) -> datetime | None:
    for entry in reversed(entries):
        if not entry.sent_reply:
            continue
        try:
            return datetime.fromisoformat(entry.timestamp)
        except ValueError:
            return None
    return None


def _clean_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _build_loop_instruction(contact: str, persona_text: str | None, context_entries: list[LoopContextEntry]) -> str:
    base = f"读取一下{contact}说了些什么，我该怎么继续聊天。"
    lines = [base]
    if persona_text:
        lines.extend(
            [
                "微信主人长期风格档案：",
                persona_text,
            ]
        )
    if not context_entries:
        return "\n".join(lines)

    lines.append("最近几轮历史上下文：")
    for index, entry in enumerate(context_entries, start=1):
        incoming = "；".join(entry.incoming_messages) or "无明确来信"
        summary = entry.summary or "无摘要"
        sent_reply = entry.sent_reply or "未发送"
        lines.append(
            f"{index}. 时间 {entry.timestamp}；对方消息：{incoming}；摘要：{summary}；我上次发送：{sent_reply}"
        )
    lines.append("请结合最近历史上下文，避免重复回复，并自然衔接当前话题。")
    return "\n".join(lines)


def _context_comment(entry: LoopContextEntry) -> str:
    payload = {
        "timestamp": entry.timestamp,
        "incoming_messages": entry.incoming_messages,
        "summary": entry.summary or "",
        "sent_reply": entry.sent_reply or "",
    }
    return f"<!-- MACAGENT_CONTEXT {json.dumps(payload, ensure_ascii=False)} -->"


def _load_context_entries(log_path: Path) -> list[LoopContextEntry]:
    if not log_path.exists():
        return []

    matches = re.findall(r"<!-- MACAGENT_CONTEXT (.+?) -->", log_path.read_text(encoding="utf-8"))
    entries: list[LoopContextEntry] = []
    for item in matches:
        try:
            payload = json.loads(item)
        except json.JSONDecodeError:
            continue
        timestamp = str(payload.get("timestamp", "")).strip()
        incoming_messages = _clean_string_list(payload.get("incoming_messages", []))
        summary = str(payload.get("summary", "")).strip() or None
        sent_reply = str(payload.get("sent_reply", "")).strip() or None
        if not timestamp:
            continue
        entries.append(
            LoopContextEntry(
                timestamp=timestamp,
                incoming_messages=incoming_messages,
                summary=summary,
                sent_reply=sent_reply,
            )
        )
    return entries


def _load_persona_text(persona_file: Path, required: bool) -> str | None:
    if not persona_file.exists():
        if required:
            raise ExecutionError(f"persona file not found: {persona_file}")
        return None

    content = persona_file.read_text(encoding="utf-8").strip()
    return content or None
