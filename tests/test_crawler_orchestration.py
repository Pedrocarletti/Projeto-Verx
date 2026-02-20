from typing import List, Optional, Tuple

from yahoo_crawler.application.screener_crawler import ScreenerCrawler
from yahoo_crawler.parsing.screener_parser import ScreenerParser


def _build_page(rows: List[Tuple[str, str, str]]) -> str:
    lines = ["<html><body><table><tbody>"]
    for symbol, name, price in rows:
        lines.append(
            """
            <tr data-testid="data-table-v2-row">
              <td data-testid-cell="ticker"><span class="symbol">{symbol}</span></td>
              <td data-testid-cell="companyshortname.raw"><div title="{name}">{name}</div></td>
              <td data-testid-cell="intradayprice"><span data-testid="change">{price}</span></td>
            </tr>
            """.format(
                symbol=symbol, name=name, price=price
            )
        )
    lines.append("</tbody></table></body></html>")
    return "\n".join(lines)


class FakeYahooClient:
    def __init__(self, pages: List[str]) -> None:
        self._pages = pages
        self._index = 0
        self.loaded = False
        self.region_applied: Optional[str] = None
        self.total_label = "1-25 of 50"
        self.next_page_calls = 0

    def load_page(self) -> None:
        self.loaded = True

    def apply_region_filter(self, region: str) -> None:
        self.region_applied = region

    def get_current_page_html(self) -> str:
        return self._pages[self._index]

    def has_next_page(self) -> bool:
        return self._index < len(self._pages) - 1

    def go_to_next_page(self) -> None:
        self._index += 1
        self.next_page_calls += 1

    def get_total_label(self) -> str:
        return self.total_label


def test_crawler_paginates_and_deduplicates() -> None:
    pages = [
        _build_page(
            [
                ("BBB.BA", "Beta Corp", "20.00"),
                ("AAA.BA", "Alpha Corp", "10.00"),
            ]
        ),
        _build_page(
            [
                ("BBB.BA", "Beta Corp", "20.00"),
                ("CCC.BA", "Gamma Corp", "30.00"),
            ]
        ),
    ]
    client = FakeYahooClient(pages)
    parser = ScreenerParser()
    crawler = ScreenerCrawler(client, parser)

    records = crawler.crawl(region="Argentina")

    assert client.loaded is True
    assert client.region_applied == "Argentina"
    assert [record.symbol for record in records] == ["AAA.BA", "BBB.BA", "CCC.BA"]


def test_crawler_respects_max_pages_limit() -> None:
    pages = [
        _build_page([("BBB.BA", "Beta Corp", "20.00")]),
        _build_page([("CCC.BA", "Gamma Corp", "30.00")]),
        _build_page([("DDD.BA", "Delta Corp", "40.00")]),
    ]
    client = FakeYahooClient(pages)
    parser = ScreenerParser()
    crawler = ScreenerCrawler(client, parser)

    records = crawler.crawl(region="Argentina", max_pages=2)

    assert [record.symbol for record in records] == ["BBB.BA", "CCC.BA"]
    assert client.next_page_calls == 1


def test_crawler_breaks_on_repeated_signature_and_reuses_parse_cache(monkeypatch) -> None:
    repeated_page = _build_page(
        [
            ("AAA.BA", "Alpha Corp", "10.00"),
            ("BBB.BA", "Beta Corp", "20.00"),
        ]
    )
    pages = [repeated_page, repeated_page, repeated_page]
    client = FakeYahooClient(pages)
    parser = ScreenerParser()
    original_parse_quotes = parser.parse_quotes
    parse_calls = {"count": 0}

    def _counting_parse(html: str):
        parse_calls["count"] += 1
        return original_parse_quotes(html)

    monkeypatch.setattr(parser, "parse_quotes", _counting_parse)

    crawler = ScreenerCrawler(client, parser)
    records = crawler.crawl(region="Argentina")

    assert [record.symbol for record in records] == ["AAA.BA", "BBB.BA"]
    assert client.next_page_calls == 1
    assert parse_calls["count"] == 1
