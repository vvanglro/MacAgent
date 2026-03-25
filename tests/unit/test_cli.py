from typer.testing import CliRunner

from macagent import cli
from macagent.domain.errors import ParseError


def test_cli_handles_build_agent_errors(monkeypatch) -> None:
    runner = CliRunner()

    def _raise(_settings):
        raise ParseError("OpenAI parser requested but dependency is not installed")

    monkeypatch.setattr(cli, "build_agent", _raise)

    result = runner.invoke(cli.app, ["搜索 macagent"])

    assert result.exit_code == 1
    assert "❌ OpenAI parser requested but dependency is not installed" in result.stdout
