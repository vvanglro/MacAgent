from macagent.config import ParserBackend, Settings


def test_settings_parser_backend_uses_enum() -> None:
    settings = Settings.from_env()
    assert isinstance(settings.parser_backend, ParserBackend)


def test_settings_parser_backend_falls_back_to_rule(monkeypatch) -> None:
    monkeypatch.setenv("MACAGENT_PARSER_BACKEND", "invalid")
    settings = Settings.from_env()
    assert settings.parser_backend == ParserBackend.RULE
