from __future__ import annotations

import typer

from macagent.config import ParserBackend, Settings
from macagent.domain.errors import MacAgentError
from macagent.domain.models import ActionName
from macagent.nlu.fallback_parser import RuleBasedParser
from macagent.nlu.llm_parser import OpenAIParser
from macagent.orchestrator.agent import MacAgent
from macagent.orchestrator.registry import ActionRegistry
from macagent.tools.chrome import ChromeFocusAddressBarHandler, ChromeSearchHandler
from macagent.tools.executor import CommandExecutor
from macagent.tools.wechat import (
    WeChatOpenHandler,
    WeChatReadLastMessageHandler,
    WeChatSendMessageHandler,
)

app = typer.Typer(help="MacAgent CLI", no_args_is_help=True)


@app.callback()
def main() -> None:
    """MacAgent CLI."""


def build_agent(settings: Settings) -> MacAgent:
    executor = CommandExecutor()
    registry = ActionRegistry()

    registry.register(action_name=ActionName.WECHAT_OPEN, handler=WeChatOpenHandler(executor))
    registry.register(action_name=ActionName.WECHAT_READ_LAST_MESSAGE, handler=WeChatReadLastMessageHandler(executor))
    registry.register(action_name=ActionName.CHROME_FOCUS_ADDRESS_BAR, handler=ChromeFocusAddressBarHandler(executor))
    registry.register(action_name=ActionName.CHROME_SEARCH, handler=ChromeSearchHandler(executor))
    registry.register(action_name=ActionName.WECHAT_SEND_MESSAGE, handler=WeChatSendMessageHandler(executor))

    parser = (
        OpenAIParser(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
        if settings.parser_backend == ParserBackend.OPENAI
        else RuleBasedParser()
    )
    return MacAgent(parser=parser, registry=registry, require_confirmation=settings.require_send_confirmation)


@app.command()
def run(text: str, yes: bool = typer.Option(False, "--yes", help="Auto confirm sensitive actions")) -> None:
    """Run one natural-language instruction."""
    settings = Settings.from_env()

    try:
        agent = build_agent(settings)
        result = agent.run(text, auto_confirm=yes)
        if result.ok:
            typer.echo(f"✅ {result.message}")
            return

        typer.echo(f"⚠️  {result.message}")
        raise typer.Exit(code=2)
    except MacAgentError as exc:
        typer.echo(f"❌ {exc}")
        raise typer.Exit(code=1) from exc


if __name__ == "__main__":
    app()
