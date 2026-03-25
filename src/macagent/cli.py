from __future__ import annotations

from pathlib import Path

import typer

from macagent.config import ParserBackend, Settings
from macagent.domain.errors import MacAgentError
from macagent.domain.models import ActionName
from macagent.loop_agent import WeChatLoopAgent
from macagent.nlu.fallback_parser import RuleBasedParser
from macagent.nlu.llm_parser import OpenAIParser
from macagent.orchestrator.agent import MacAgent
from macagent.orchestrator.react import ReActPlanner
from macagent.orchestrator.registry import ActionRegistry
from macagent.reporting import Reporter
from macagent.tools.chrome import ChromeFocusAddressBarHandler, ChromeSearchHandler
from macagent.tools.executor import CommandExecutor
from macagent.tools.wechat import (
    WeChatChatVisionReader,
    WeChatOpenHandler,
    WeChatReadLastMessageHandler,
    WeChatSendMessageHandler,
)

app = typer.Typer(help="MacAgent CLI", no_args_is_help=True)


@app.callback()
def main() -> None:
    """MacAgent CLI."""


def build_agent(settings: Settings, reporter: Reporter | None = None) -> MacAgent:
    executor = CommandExecutor()
    registry = ActionRegistry(reporter=reporter)
    vision_reader = _build_vision_reader(settings)

    registry.register(action_name=ActionName.WECHAT_OPEN, handler=WeChatOpenHandler(executor, reporter=reporter))
    registry.register(
        action_name=ActionName.WECHAT_READ_LAST_MESSAGE,
        handler=WeChatReadLastMessageHandler(executor, vision_reader=vision_reader, reporter=reporter),
    )
    registry.register(
        action_name=ActionName.CHROME_FOCUS_ADDRESS_BAR,
        handler=ChromeFocusAddressBarHandler(executor, reporter=reporter),
    )
    registry.register(action_name=ActionName.CHROME_SEARCH, handler=ChromeSearchHandler(executor, reporter=reporter))
    registry.register(
        action_name=ActionName.WECHAT_SEND_MESSAGE,
        handler=WeChatSendMessageHandler(executor, reporter=reporter),
    )

    parser = (
        OpenAIParser(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
        if settings.parser_backend == ParserBackend.OPENAI
        else RuleBasedParser()
    )
    return MacAgent(
        parser=parser,
        registry=registry,
        require_confirmation=settings.require_send_confirmation,
        reporter=reporter,
        planner=ReActPlanner(),
    )


def build_loop_agent(settings: Settings, reporter: Reporter | None = None) -> WeChatLoopAgent:
    executor = CommandExecutor()
    vision_reader = _build_vision_reader(settings)
    read_handler = WeChatReadLastMessageHandler(executor, vision_reader=vision_reader, reporter=reporter)
    send_handler = WeChatSendMessageHandler(executor, reporter=reporter)
    return WeChatLoopAgent(
        read_handler=read_handler,
        send_handler=send_handler,
        reporter=reporter,
    )


def _build_vision_reader(settings: Settings) -> WeChatChatVisionReader | None:
    return (
        WeChatChatVisionReader(
            model=settings.vision_model,
            api_key=settings.vision_api_key,
            base_url=settings.vision_base_url,
        )
        if settings.vision_model
        else None
    )


@app.command()
def run(text: str, yes: bool = typer.Option(False, "--yes", help="Auto confirm sensitive actions")) -> None:
    """Run one natural-language instruction."""
    settings = Settings.from_env()
    reporter = lambda message: typer.echo(f"• {message}")

    try:
        typer.echo("• 正在解析指令并构建执行计划")
        agent = build_agent(settings, reporter=reporter)
        typer.echo("• 开始执行")
        result = agent.run(text, auto_confirm=yes)
        if result.ok:
            typer.echo(f"✅ {result.message}")
            return

        typer.echo(f"⚠️  {result.message}")
        raise typer.Exit(code=2)
    except MacAgentError as exc:
        typer.echo(f"❌ {exc}")
        raise typer.Exit(code=1) from exc


@app.command()
def loop(
    contact: str,
    interval: int = typer.Option(60, "--interval", min=1, help="Polling interval in seconds"),
    rounds: int = typer.Option(5, "--rounds", min=0, help="How many rounds to run; 0 means keep looping"),
    cooldown: int = typer.Option(180, "--cooldown", min=0, help="Cooldown after we send a reply, in seconds"),
    context_rounds: int = typer.Option(3, "--context-rounds", min=0, help="How many recent rounds to feed back as context"),
    yes: bool = typer.Option(False, "--yes", help="Auto send the generated reply suggestion"),
    log_file: Path | None = typer.Option(None, "--log-file", help="Markdown log path; defaults to current directory"),
) -> None:
    """Loop over one WeChat chat: read, log, and optionally auto-reply."""
    settings = Settings.from_env()
    reporter = lambda message: typer.echo(f"• {message}")

    try:
        typer.echo("• 正在构建 loop agent")
        agent = build_loop_agent(settings, reporter=reporter)
        typer.echo("• 开始执行 loop 轮询")
        summary = agent.run(
            contact=contact,
            interval_seconds=interval,
            rounds=rounds,
            auto_send=yes,
            log_path=log_file,
            cooldown_seconds=cooldown,
            context_rounds=context_rounds,
        )
        typer.echo(
            f"✅ loop 完成，已记录 {summary.rounds_completed} 轮，自动发送 {summary.replies_sent} 次，日志文件：{summary.log_path}"
        )
    except MacAgentError as exc:
        typer.echo(f"❌ {exc}")
        raise typer.Exit(code=1) from exc


if __name__ == "__main__":
    app()
