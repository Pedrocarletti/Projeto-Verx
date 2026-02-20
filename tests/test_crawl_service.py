from pathlib import Path

import pytest

import yahoo_crawler.application.crawl_service as crawl_service
from yahoo_crawler.application.crawl_service import CrawlExecutionParams, run_crawl_job
from yahoo_crawler.cache.quote_cache import QuoteCache
from yahoo_crawler.domain.models import EquityQuote


def test_run_crawl_job_uses_cache_without_selenium(
    tmp_path: Path, monkeypatch
) -> None:
    cache_dir = tmp_path / "cache"
    output_file = tmp_path / "result.csv"
    cache = QuoteCache(str(cache_dir))
    cache.save(
        "Argentina",
        [EquityQuote(symbol="AMX.BA", name="America Movil, S.A.B. de C.V.", price="2089.00")],
    )

    def _raise_if_called(_self):  # pragma: no cover
        raise AssertionError("Nao deveria abrir Selenium quando ha cache HIT.")

    monkeypatch.setattr(
        "yahoo_crawler.infrastructure.webdriver_factory.WebDriverFactory.create",
        _raise_if_called,
    )

    result = run_crawl_job(
        CrawlExecutionParams(
            region="Argentina",
            out=str(output_file),
            use_cache=True,
            cache_dir=str(cache_dir),
            cache_ttl_minutes=30,
        )
    )

    assert result.source == "cache"
    assert result.total_records == 1
    assert output_file.exists()


def test_run_crawl_job_live_path_writes_csv_and_cache(
    tmp_path: Path, monkeypatch
) -> None:
    output_file = tmp_path / "live_result.csv"
    cache_dir = tmp_path / "cache"
    generated_records = [
        EquityQuote(symbol="AAA.BA", name="Alpha Corp", price="10.00"),
    ]
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

    class FakeCrawler:
        def __init__(self, _client, _parser) -> None:
            pass

        def crawl(self, region: str, max_pages: int = None):
            assert region == "Argentina"
            assert max_pages == 2
            return generated_records

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
            cache_dir=str(cache_dir),
            cache_ttl_minutes=30,
        )
    )

    cached = QuoteCache(str(cache_dir)).load("Argentina", ttl_minutes=30)

    assert result.source == "live"
    assert result.total_records == 1
    assert output_file.exists()
    assert cached is not None
    assert [item.symbol for item in cached] == ["AAA.BA"]
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
            raise RuntimeError("falha no crawl")

    monkeypatch.setattr(
        "yahoo_crawler.infrastructure.webdriver_factory.WebDriverFactory.create",
        lambda _self: object(),
    )
    monkeypatch.setattr(crawl_service, "YahooFinanceClient", _fake_client)
    monkeypatch.setattr(crawl_service, "ScreenerCrawler", FailingCrawler)

    with pytest.raises(RuntimeError, match="falha no crawl"):
        run_crawl_job(
            CrawlExecutionParams(
                region="Argentina",
                out=str(output_file),
                use_cache=False,
            )
        )

    assert created_clients and created_clients[0].closed is True


def test_run_crawl_job_uses_redis_cache_without_selenium(tmp_path: Path, monkeypatch) -> None:
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
        raise AssertionError("Nao deveria abrir Selenium quando ha cache HIT no Redis.")

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
            cache_backend="redis",
            redis_url="redis://localhost:6379/5",
            redis_key_prefix="verx:test",
            cache_ttl_minutes=30,
        )
    )

    assert result.source == "cache"
    assert result.total_records == 1
    assert output_file.exists()


def test_run_crawl_job_rejects_invalid_cache_backend(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="cache_backend invalido"):
        run_crawl_job(
            CrawlExecutionParams(
                region="Argentina",
                out=str(tmp_path / "result.csv"),
                use_cache=True,
                cache_backend="invalid",
            )
        )
