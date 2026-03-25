from typer.testing import CliRunner

from macagent import cli
from macagent.domain.errors import ParseError
from macagent.domain.models import ActionName, ActionResult


def test_cli_handles_build_agent_errors(monkeypatch) -> None:
    runner = CliRunner()

    def _raise(_settings, reporter=None):
        raise ParseError("OpenAI parser requested but dependency is not installed")

    monkeypatch.setattr(cli, "build_agent", _raise)

    result = runner.invoke(cli.app, ["run", "搜索 macagent"])

    assert result.exit_code == 1
    assert "❌ OpenAI parser requested but dependency is not installed" in result.stdout


def test_cli_run_accepts_text_and_yes_flag(monkeypatch) -> None:
    runner = CliRunner()
    captured: dict[str, object] = {}

    class FakeAgent:
        def run(self, text: str, auto_confirm: bool = False) -> ActionResult:
            captured["text"] = text
            captured["auto_confirm"] = auto_confirm
            return ActionResult(
                ok=True,
                action=ActionName.WECHAT_SEND_MESSAGE,
                message="sent",
            )

    monkeypatch.setattr(cli, "build_agent", lambda _settings, reporter=None: FakeAgent())

    result = runner.invoke(cli.app, ["run", "给小桃有点运气发微信说hello", "--yes"])

    assert result.exit_code == 0
    assert captured == {
        "text": "给小桃有点运气发微信说hello",
        "auto_confirm": True,
    }
    assert "• 正在解析指令并构建执行计划" in result.stdout
    assert "• 开始执行" in result.stdout
    assert "✅ sent" in result.stdout
