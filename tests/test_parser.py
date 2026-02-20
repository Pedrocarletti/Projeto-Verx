from pathlib import Path

from yahoo_crawler.parsing.screener_parser import ScreenerParser


def _load_fixture(name: str) -> str:
    return (Path(__file__).parent / "fixtures" / name).read_text(encoding="utf-8")


def test_parser_extracts_symbol_name_price() -> None:
    parser = ScreenerParser()
    html = _load_fixture("equities_sample.html")

    quotes = parser.parse_quotes(html)

    assert len(quotes) == 2
    assert quotes[0].symbol == "AMX.BA"
    assert quotes[0].name == "America Movil, S.A.B. de C.V."
    assert quotes[0].price == "2089.00"
    assert quotes[1].symbol == "NOKA.BA"
    assert quotes[1].name == "Nokia Corporation"
    assert quotes[1].price == "557.50"


def test_parser_handles_missing_price() -> None:
    parser = ScreenerParser()
    html = _load_fixture("equities_missing_price.html")

    quotes = parser.parse_quotes(html)

    assert len(quotes) == 1
    assert quotes[0].symbol == "ABC.BA"
    assert quotes[0].price == ""
