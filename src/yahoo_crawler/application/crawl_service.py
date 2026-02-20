import logging
from dataclasses import dataclass
from typing import Any, Optional

from yahoo_crawler.application.screener_crawler import ScreenerCrawler
from yahoo_crawler.cache.quote_cache import QuoteCache
from yahoo_crawler.cache.redis_quote_cache import RedisQuoteCache
from yahoo_crawler.config import CrawlerConfig
from yahoo_crawler.infrastructure.webdriver_factory import WebDriverFactory
from yahoo_crawler.infrastructure.yahoo_client import YahooFinanceClient
from yahoo_crawler.output.csv_writer import CsvWriter
from yahoo_crawler.parsing.screener_parser import ScreenerParser
from yahoo_crawler.utils.logging_config import configure_logging

LOGGER = logging.getLogger(__name__)


@dataclass
class CrawlExecutionParams:
    region: str
    out: str = "output/equities.csv"
    max_pages: Optional[int] = None
    timeout_seconds: int = 45
    headless: bool = True
    log_level: str = "INFO"
    use_cache: bool = False
    cache_backend: str = "local"
    cache_dir: str = ".cache/yahoo_crawler"
    cache_ttl_minutes: int = 30
    redis_url: str = "redis://localhost:6379/0"
    redis_key_prefix: str = "yahoo_crawler:quotes"


@dataclass
class CrawlExecutionResult:
    output_path: str
    total_records: int
    source: str  # cache | live


def run_crawl_job(params: CrawlExecutionParams) -> CrawlExecutionResult:
    configure_logging(params.log_level)

    cache_backend = params.cache_backend.strip().lower() or "local"
    config = CrawlerConfig(
        timeout_seconds=params.timeout_seconds,
        headless=params.headless,
        cache_enabled=params.use_cache,
        cache_backend=cache_backend,
        cache_dir=params.cache_dir,
        cache_ttl_minutes=params.cache_ttl_minutes,
        redis_url=params.redis_url,
        redis_key_prefix=params.redis_key_prefix,
    )

    cache = _build_cache(config)

    if config.cache_enabled:
        cached_records = cache.load(params.region, config.cache_ttl_minutes)
        if cached_records is not None:
            CsvWriter.write(params.out, cached_records)
            LOGGER.info("Cache HIT para regiao '%s'.", params.region)
            return CrawlExecutionResult(
                output_path=params.out,
                total_records=len(cached_records),
                source="cache",
            )

    driver_factory = WebDriverFactory(config)
    driver = driver_factory.create()
    client = YahooFinanceClient(driver, config)
    parser = ScreenerParser()
    crawler = ScreenerCrawler(client, parser)

    try:
        records = crawler.crawl(region=params.region, max_pages=params.max_pages)
        if config.cache_enabled:
            cache_path = cache.save(params.region, records)
            LOGGER.info("Cache salvo em: %s", cache_path)
        CsvWriter.write(params.out, records)
        return CrawlExecutionResult(
            output_path=params.out,
            total_records=len(records),
            source="live",
        )
    finally:
        client.close()


def _build_cache(config: CrawlerConfig) -> Any:
    if not config.cache_enabled:
        return QuoteCache(config.cache_dir)

    if config.cache_backend == "redis":
        return RedisQuoteCache(
            redis_url=config.redis_url,
            key_prefix=config.redis_key_prefix,
        )

    if config.cache_backend == "local":
        return QuoteCache(config.cache_dir)

    raise ValueError(
        "cache_backend invalido: '{0}'. Use 'local' ou 'redis'.".format(
            config.cache_backend
        )
    )
