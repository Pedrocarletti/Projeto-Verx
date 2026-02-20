from typing import List

from bs4 import BeautifulSoup, Tag

from yahoo_crawler.domain.models import EquityQuote


class ScreenerParser:
    ROW_SELECTOR = "tr[data-testid='data-table-v2-row']"

    def parse_quotes(self, html: str) -> List[EquityQuote]:
        soup = BeautifulSoup(html, "lxml")
        rows = soup.select(self.ROW_SELECTOR)

        quotes = []
        for row in rows:
            symbol = self._extract_symbol(row)
            name = self._extract_name(row)
            price = self._extract_price(row)
            if not symbol or not name:
                continue
            quotes.append(EquityQuote(symbol=symbol, name=name, price=price))

        return quotes

    def _extract_symbol(self, row: Tag) -> str:
        symbol_tag = row.select_one("td[data-testid-cell='ticker'] span.symbol")
        if not symbol_tag:
            symbol_tag = row.select_one("td[data-testid-cell='ticker'] a[data-testid='table-cell-ticker']")
        if not symbol_tag:
            return ""
        return symbol_tag.get_text(strip=True)

    def _extract_name(self, row: Tag) -> str:
        name_tag = row.select_one("td[data-testid-cell='companyshortname.raw'] div")
        if not name_tag:
            return ""
        title = name_tag.get("title")
        if title:
            return title.strip()
        return name_tag.get_text(strip=True)

    def _extract_price(self, row: Tag) -> str:
        price_tag = row.select_one(
            "td[data-testid-cell='intradayprice'] span[data-testid='change']"
        )
        raw_text = ""
        if price_tag:
            raw_text = price_tag.get_text(" ", strip=True)
        else:
            cell = row.select_one("td[data-testid-cell='intradayprice']")
            if cell:
                raw_text = cell.get_text(" ", strip=True)
        return self._normalize_price(raw_text)

    def _normalize_price(self, raw_text: str) -> str:
        if not raw_text:
            return ""
        cleaned = raw_text.replace("\xa0", " ").replace(",", "").strip()
        if cleaned in ("--", "N/A", "n/a"):
            return ""
        return cleaned
