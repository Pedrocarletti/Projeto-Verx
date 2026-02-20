import logging
from hashlib import md5
from typing import Dict, List, Optional

from yahoo_crawler.domain.models import EquityQuote
from yahoo_crawler.infrastructure.yahoo_client import YahooFinanceClient
from yahoo_crawler.parsing.screener_parser import ScreenerParser

LOGGER = logging.getLogger(__name__)


class ScreenerCrawler:
    def __init__(self, client: YahooFinanceClient, parser: ScreenerParser) -> None:
        self._client = client
        self._parser = parser

    def crawl(self, region: str, max_pages: Optional[int] = None) -> List[EquityQuote]:
        self._client.load_page()
        self._client.apply_region_filter(region)

        by_symbol: Dict[str, EquityQuote] = {}
        parsed_pages_cache: Dict[str, List[EquityQuote]] = {}
        page_number = 1
        last_signature = None

        while True:
            page_html = self._client.get_current_page_html()
            page_key = md5(page_html.encode("utf-8")).hexdigest()
            quotes = parsed_pages_cache.get(page_key)
            if quotes is None:
                quotes = self._parser.parse_quotes(page_html)
                parsed_pages_cache[page_key] = quotes
            added_count = 0

            for quote in quotes:
                if quote.symbol not in by_symbol:
                    by_symbol[quote.symbol] = quote
                    added_count += 1

            has_next_page = self._client.has_next_page()
            LOGGER.info(
                "Page %s | extracted=%s | new=%s | total=%s | %s | next=%s | parse_cache=%s",
                page_number,
                len(quotes),
                added_count,
                len(by_symbol),
                self._client.get_total_label(),
                has_next_page,
                len(parsed_pages_cache),
            )

            current_signature = tuple([quote.symbol for quote in quotes[:3]])
            if current_signature and current_signature == last_signature and has_next_page:
                LOGGER.warning(
                    "Repeated page signature detected. Stopping to avoid loop."
                )
                break
            last_signature = current_signature

            if max_pages is not None and page_number >= max_pages:
                LOGGER.info("Page limit reached: %s", max_pages)
                break

            if not has_next_page:
                break

            self._client.go_to_next_page()
            page_number += 1

        return [by_symbol[symbol] for symbol in sorted(by_symbol)]
