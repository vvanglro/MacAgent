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


def test_cli_loop_accepts_contact_interval_and_yes_flag(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    captured: dict[str, object] = {}

    class FakeLoopAgent:
        def run(
            self,
            contact: str,
            interval_seconds: int,
            rounds: int = 5,
            auto_send: bool = False,
            log_path=None,
            cooldown_seconds: int = 180,
            context_rounds: int = 3,
        ):
            captured["contact"] = contact
            captured["interval_seconds"] = interval_seconds
            captured["rounds"] = rounds
            captured["auto_send"] = auto_send
            captured["log_path"] = log_path
            captured["cooldown_seconds"] = cooldown_seconds
            captured["context_rounds"] = context_rounds
            from pathlib import Path
            from macagent.loop_agent import LoopRunSummary

            return LoopRunSummary(
                log_path=Path(log_path),
                rounds_completed=rounds,
                replies_sent=1,
                contact=contact,
            )

    monkeypatch.setattr(cli, "build_loop_agent", lambda _settings, reporter=None: FakeLoopAgent())
    log_path = tmp_path / "loop.md"

    result = runner.invoke(
        cli.app,
        [
            "loop",
            "沪上小牛爷",
            "--interval",
            "30",
            "--rounds",
            "2",
            "--cooldown",
            "90",
            "--context-rounds",
            "4",
            "--yes",
            "--log-file",
            str(log_path),
        ],
    )

    assert result.exit_code == 0
    assert captured == {
        "contact": "沪上小牛爷",
        "interval_seconds": 30,
        "rounds": 2,
        "auto_send": True,
        "log_path": log_path,
        "cooldown_seconds": 90,
        "context_rounds": 4,
    }
    assert "• 正在构建 loop agent" in result.stdout
    assert "✅ loop 完成" in result.stdout
