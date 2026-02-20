import argparse
import logging
import sys
from typing import Optional

from yahoo_crawler.application.crawl_service import CrawlExecutionParams, run_crawl_job
from yahoo_crawler.utils.logging_config import configure_logging


def _build_args(argv: Optional[list] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Yahoo Finance crawler (equity screener) with Selenium + BeautifulSoup."
        )
    )
    parser.add_argument(
        "--region",
        required=True,
        help='Region name exactly as displayed in Yahoo filter. Example: "Argentina"',
    )
    parser.add_argument(
        "--out",
        default="output/equities.csv",
        help="Output CSV path. Default: output/equities.csv",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Page limit for crawl (optional).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=45,
        help="Selenium wait timeout in seconds.",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Run browser with UI.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Log level (DEBUG, INFO, WARNING, ERROR).",
    )
    parser.add_argument(
        "--use-cache",
        action="store_true",
        help="Enable region cache to avoid recrawls in repeated runs.",
    )
    parser.add_argument(
        "--cache-ttl-minutes",
        type=int,
        default=30,
        help="Cache time-to-live in minutes. Default: 30.",
    )
    parser.add_argument(
        "--redis-url",
        default="redis://localhost:6379/0",
        help="Redis connection URL. Example: redis://localhost:6379/0",
    )
    parser.add_argument(
        "--redis-key-prefix",
        default="yahoo_crawler:quotes",
        help="Redis key prefix. Default: yahoo_crawler:quotes",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list] = None) -> int:
    args = _build_args(argv)
    configure_logging(args.log_level)
    logger = logging.getLogger(__name__)

    params = CrawlExecutionParams(
        region=args.region,
        out=args.out,
        max_pages=args.max_pages,
        timeout_seconds=args.timeout,
        headless=not args.no_headless,
        log_level=args.log_level,
        use_cache=args.use_cache,
        cache_ttl_minutes=args.cache_ttl_minutes,
        redis_url=args.redis_url,
        redis_key_prefix=args.redis_key_prefix,
    )

    try:
        result = run_crawl_job(params)
        logger.info("Result source: %s", result.source)
        logger.info("CSV generated at: %s", result.output_path)
        logger.info("Total records written: %s", result.total_records)
        return 0
    except Exception as exc:
        logger.exception("Crawler execution failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
