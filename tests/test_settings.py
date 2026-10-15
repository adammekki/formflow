from app.config import Settings


def test_log_level_defaults_to_info(monkeypatch):
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    assert Settings().log_level.upper() == "INFO"


def test_log_level_is_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    assert Settings().log_level.upper() == "DEBUG"


def test_cors_origins_parses_comma_separated(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://a:3000,http://b:3000")
    assert Settings().cors_origins == ["http://a:3000", "http://b:3000"]


def test_cors_origins_parses_json_list(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", '["http://c:3000"]')
    assert Settings().cors_origins == ["http://c:3000"]
