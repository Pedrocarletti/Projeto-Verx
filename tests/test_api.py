import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from yahoo_crawler import api
from yahoo_crawler.application.crawl_service import CrawlExecutionResult


def test_health_endpoint_returns_ok() -> None:
    assert api.health() == {"status": "ok"}


def test_openapi_schema_generation() -> None:
    schema = api.app.openapi()
    assert "CrawlRequest" in schema["components"]["schemas"]


def test_options_endpoint_exposes_defaults_and_endpoints() -> None:
    payload = api.options()

    assert "/crawl" in payload["endpoints"]
    assert "/crawl/submit" not in payload["endpoints"]
    assert "/crawl/jobs/{job_id}" not in payload["endpoints"]
    assert payload["defaults"]["region"] == "Argentina"
    assert payload["defaults"]["timeout_seconds"] == 45
    assert payload["defaults"]["use_cache"] is False
    assert "cache_backend" not in payload["defaults"]
    assert "cache_dir" not in payload["defaults"]
    assert "cache_ttl_minutes" not in payload["defaults"]
    assert "redis_url" not in payload["defaults"]
    assert "redis_key_prefix" not in payload["defaults"]


def test_crawl_endpoint_returns_result_payload(monkeypatch) -> None:
    captured = {}
    monkeypatch.delenv("YAHOO_CRAWLER_CACHE_TTL_MINUTES", raising=False)
    monkeypatch.delenv("YAHOO_CRAWLER_REDIS_URL", raising=False)
    monkeypatch.delenv("YAHOO_CRAWLER_REDIS_KEY_PREFIX", raising=False)

    def _fake_run(_params):
        captured["params"] = _params
        return CrawlExecutionResult(
            output_path="output/test.csv",
            total_records=2,
            source="live",
        )

    monkeypatch.setattr(api, "run_crawl_job", _fake_run)

    response = api.crawl(api.CrawlRequest(region="Argentina"))

    assert response.success is True
    assert response.source == "live"
    assert response.total_records == 2
    assert response.output_path == "output/test.csv"
    assert captured["params"].use_cache is False
    assert captured["params"].cache_ttl_minutes == 30
    assert captured["params"].redis_url == "redis://localhost:6379/0"
    assert captured["params"].redis_key_prefix == "yahoo_crawler:quotes"


def test_crawl_endpoint_maps_redis_fields_from_env(monkeypatch) -> None:
    captured = {}

    def _fake_run(_params):
        captured["params"] = _params
        return CrawlExecutionResult(
            output_path="output/redis.csv",
            total_records=1,
            source="cache",
        )

    monkeypatch.setattr(api, "run_crawl_job", _fake_run)
    monkeypatch.setenv("YAHOO_CRAWLER_CACHE_TTL_MINUTES", "15")
    monkeypatch.setenv("YAHOO_CRAWLER_REDIS_URL", "redis://localhost:6379/9")
    monkeypatch.setenv("YAHOO_CRAWLER_REDIS_KEY_PREFIX", "verx:cache")

    request = api.CrawlRequest(
        region="Argentina",
        use_cache=True,
    )
    response = api.crawl(request)

    assert response.source == "cache"
    assert captured["params"].use_cache is True
    assert captured["params"].cache_ttl_minutes == 15
    assert captured["params"].redis_url == "redis://localhost:6379/9"
    assert captured["params"].redis_key_prefix == "verx:cache"


def test_crawl_endpoint_raises_http_500_when_execution_fails(monkeypatch) -> None:
    def _failing_run(_params):
        raise RuntimeError("crawler error")

    monkeypatch.setattr(api, "run_crawl_job", _failing_run)

    with pytest.raises(HTTPException) as excinfo:
        api.crawl(api.CrawlRequest(region="Argentina"))

    assert excinfo.value.status_code == 500
    assert excinfo.value.detail == "crawler error"


def test_crawl_request_validates_required_region() -> None:
    with pytest.raises(ValidationError):
        api.CrawlRequest()


def test_crawl_request_rejects_legacy_cache_fields() -> None:
    with pytest.raises(ValidationError):
        api.CrawlRequest(region="Argentina", cache_backend="redis")
