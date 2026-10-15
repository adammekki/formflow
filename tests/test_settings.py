from app.config import Settings


def test_cors_origins_parses_comma_separated(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://a:3000,http://b:3000")
    assert Settings().cors_origins == ["http://a:3000", "http://b:3000"]


def test_cors_origins_parses_json_list(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", '["http://c:3000"]')
    assert Settings().cors_origins == ["http://c:3000"]
