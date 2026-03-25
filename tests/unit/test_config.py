from macagent.config import ParserBackend, Settings


def test_settings_parser_backend_uses_enum() -> None:
    settings = Settings.from_env()
    assert isinstance(settings.parser_backend, ParserBackend)


def test_settings_parser_backend_falls_back_to_rule(monkeypatch) -> None:
    monkeypatch.setenv("MACAGENT_PARSER_BACKEND", "invalid")
    settings = Settings.from_env()
    assert settings.parser_backend == ParserBackend.RULE


def test_settings_reads_openai_compatible_overrides(monkeypatch) -> None:
    monkeypatch.setenv("MACAGENT_PARSER_BACKEND", "openai")
    monkeypatch.setenv("MACAGENT_OPENAI_MODEL", "qwen-plus")
    monkeypatch.setenv("MACAGENT_OPENAI_BASE_URL", "https://example.com/v1")
    monkeypatch.setenv("MACAGENT_OPENAI_API_KEY", "test-key")

    settings = Settings.from_env()

    assert settings.parser_backend == ParserBackend.OPENAI
    assert settings.openai_model == "qwen-plus"
    assert settings.openai_base_url == "https://example.com/v1"
    assert settings.openai_api_key == "test-key"


def test_settings_falls_back_to_openai_api_key_env(monkeypatch) -> None:
    monkeypatch.delenv("MACAGENT_OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "fallback-key")

    settings = Settings.from_env()

    assert settings.openai_api_key == "fallback-key"
