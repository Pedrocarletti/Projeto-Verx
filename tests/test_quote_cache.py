import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from yahoo_crawler.cache.quote_cache import QuoteCache
from yahoo_crawler.domain.models import EquityQuote


def test_quote_cache_save_and_load(tmp_path: Path) -> None:
    cache = QuoteCache(str(tmp_path))
    records = [
        EquityQuote(symbol="AMX.BA", name="America Movil, S.A.B. de C.V.", price="2089.00"),
        EquityQuote(symbol="NOKA.BA", name="Nokia Corporation", price="557.50"),
    ]

    cache.save("Argentina", records)
    cached = cache.load("Argentina", ttl_minutes=30)

    assert cached is not None
    assert [item.symbol for item in cached] == ["AMX.BA", "NOKA.BA"]


def test_quote_cache_respects_ttl(tmp_path: Path) -> None:
    cache = QuoteCache(str(tmp_path))
    records = [EquityQuote(symbol="AMX.BA", name="America Movil, S.A.B. de C.V.", price="2089.00")]
    cache_file = cache.save("Argentina", records)

    payload = json.loads(cache_file.read_text(encoding="utf-8"))
    payload["created_at"] = (datetime.now(timezone.utc) - timedelta(minutes=120)).isoformat()
    cache_file.write_text(json.dumps(payload), encoding="utf-8")

    cached = cache.load("Argentina", ttl_minutes=30)
    assert cached is None
