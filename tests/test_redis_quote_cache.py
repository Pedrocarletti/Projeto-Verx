import json
from datetime import datetime, timedelta, timezone

from yahoo_crawler.cache.redis_quote_cache import RedisQuoteCache
from yahoo_crawler.domain.models import EquityQuote


class FakeRedisClient:
    def __init__(self) -> None:
        self.storage = {}

    def get(self, key: str):
        return self.storage.get(key)

    def set(self, key: str, value: str) -> None:
        self.storage[key] = value


def test_redis_quote_cache_save_and_load() -> None:
    client = FakeRedisClient()
    cache = RedisQuoteCache(
        redis_url="redis://localhost:6379/0",
        key_prefix="test:quotes",
        client=client,
    )
    records = [
        EquityQuote(symbol="AMX.BA", name="America Movil, S.A.B. de C.V.", price="2089.00"),
        EquityQuote(symbol="NOKA.BA", name="Nokia Corporation", price="557.50"),
    ]

    key = cache.save("Argentina", records)
    cached = cache.load("Argentina", ttl_minutes=30)

    assert key == "test:quotes:argentina"
    assert cached is not None
    assert [item.symbol for item in cached] == ["AMX.BA", "NOKA.BA"]


def test_redis_quote_cache_respects_ttl() -> None:
    client = FakeRedisClient()
    cache = RedisQuoteCache(
        redis_url="redis://localhost:6379/0",
        key_prefix="test:quotes",
        client=client,
    )
    cache.save(
        "Argentina",
        [EquityQuote(symbol="AMX.BA", name="America Movil, S.A.B. de C.V.", price="2089.00")],
    )

    payload = json.loads(client.storage["test:quotes:argentina"])
    payload["created_at"] = (datetime.now(timezone.utc) - timedelta(minutes=120)).isoformat()
    client.storage["test:quotes:argentina"] = json.dumps(payload)

    cached = cache.load("Argentina", ttl_minutes=30)

    assert cached is None
