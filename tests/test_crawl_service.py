from pathlib import Path

import pytest

import yahoo_crawler.application.crawl_service as crawl_service
from yahoo_crawler.application.crawl_service import CrawlExecutionParams, run_crawl_job
from yahoo_crawler.domain.models import EquityQuote


def test_run_crawl_job_uses_redis_cache_without_selenium(
    tmp_path: Path, monkeypatch
) -> None:
    output_file = tmp_path / "result.csv"
    cached_records = [
        EquityQuote(symbol="AMX.BA", name="America Movil, S.A.B. de C.V.", price="2089.00")
    ]

    class FakeRedisCache:
        def __init__(self, redis_url: str, key_prefix: str) -> None:
            assert redis_url == "redis://localhost:6379/5"
            assert key_prefix == "verx:test"

        def load(self, region: str, ttl_minutes: int):
            assert region == "Argentina"
            assert ttl_minutes == 30
            return cached_records

        def save(self, region: str, records):
            return "ignored:{0}:{1}".format(region, len(records))

    def _raise_if_called(_self):  # pragma: no cover
        raise AssertionError("Selenium should not start when Redis cache HIT exists.")

    monkeypatch.setattr(crawl_service, "RedisQuoteCache", FakeRedisCache)
    monkeypatch.setattr(
        "yahoo_crawler.infrastructure.webdriver_factory.WebDriverFactory.create",
        _raise_if_called,
    )

    result = run_crawl_job(
        CrawlExecutionParams(
            region="Argentina",
            out=str(output_file),
            use_cache=True,
            redis_url="redis://localhost:6379/5",
            redis_key_prefix="verx:test",
            cache_ttl_minutes=30,
        )
    )

    assert result.source == "cache"
    assert result.total_records == 1
    assert output_file.exists()


def test_run_crawl_job_live_path_writes_csv_and_redis_cache(
    tmp_path: Path, monkeypatch
) -> None:
    output_file = tmp_path / "live_result.csv"
    generated_records = [
        EquityQuote(symbol="AAA.BA", name="Alpha Corp", price="10.00"),
    ]
    created_clients = []
    saved_cache = {}

    class FakeRedisCache:
        def __init__(self, redis_url: str, key_prefix: str) -> None:
            assert redis_url == "redis://localhost:6379/6"
            assert key_prefix == "verx:prod"

        def load(self, region: str, ttl_minutes: int):
            assert region == "Argentina"
            assert ttl_minutes == 30
            return None

        def save(self, region: str, records):
            saved_cache["region"] = region
            saved_cache["count"] = len(records)
            return "verx:prod:argentina"

    class FakeYahooClient:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    def _fake_client(_driver, _config):
        client = FakeYahooClient()
        created_clients.append(client)
        return client

    class FakeCrawler:
        def __init__(self, _client, _parser) -> None:
            pass

        def crawl(self, region: str, max_pages: int = None):
            assert region == "Argentina"
            assert max_pages == 2
            return generated_records

    monkeypatch.setattr(crawl_service, "RedisQuoteCache", FakeRedisCache)
    monkeypatch.setattr(
        "yahoo_crawler.infrastructure.webdriver_factory.WebDriverFactory.create",
        lambda _self: object(),
    )
    monkeypatch.setattr(crawl_service, "YahooFinanceClient", _fake_client)
    monkeypatch.setattr(crawl_service, "ScreenerCrawler", FakeCrawler)

    result = run_crawl_job(
        CrawlExecutionParams(
            region="Argentina",
            out=str(output_file),
            max_pages=2,
            use_cache=True,
            redis_url="redis://localhost:6379/6",
            redis_key_prefix="verx:prod",
            cache_ttl_minutes=30,
        )
    )

    assert result.source == "live"
    assert result.total_records == 1
    assert output_file.exists()
    assert saved_cache["region"] == "Argentina"
    assert saved_cache["count"] == 1
    assert created_clients and created_clients[0].closed is True


def test_run_crawl_job_closes_client_on_error(tmp_path: Path, monkeypatch) -> None:
    output_file = tmp_path / "failed_result.csv"
    created_clients = []

    class FakeYahooClient:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    def _fake_client(_driver, _config):
        client = FakeYahooClient()
        created_clients.append(client)
        return client

    class FailingCrawler:
        def __init__(self, _client, _parser) -> None:
            pass

        def crawl(self, region: str, max_pages: int = None):
            raise RuntimeError("crawl failed")

    monkeypatch.setattr(
        "yahoo_crawler.infrastructure.webdriver_factory.WebDriverFactory.create",
        lambda _self: object(),
    )
    monkeypatch.setattr(crawl_service, "YahooFinanceClient", _fake_client)
    monkeypatch.setattr(crawl_service, "ScreenerCrawler", FailingCrawler)

    with pytest.raises(RuntimeError, match="crawl failed"):
        run_crawl_job(
            CrawlExecutionParams(
                region="Argentina",
                out=str(output_file),
                use_cache=False,
            )
        )

    assert created_clients and created_clients[0].closed is True
