import json
import logging
import re
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from redis import Redis  # type: ignore[import]
from redis.exceptions import RedisError  # type: ignore[import]

from yahoo_crawler.domain.models import EquityQuote

LOGGER = logging.getLogger(__name__)


class RedisQuoteCache:
    CACHE_VERSION = 1

    def __init__(
        self,
        redis_url: str,
        key_prefix: str = "yahoo_crawler:quotes",
        client: Optional[Redis] = None,
    ) -> None:
        self._key_prefix = key_prefix.rstrip(":") or "yahoo_crawler:quotes"
        self._client = client or Redis.from_url(redis_url, decode_responses=True)

    def load(self, region: str, ttl_minutes: int) -> Optional[List[EquityQuote]]:
        key = self._cache_key(region)
        try:
            payload_raw = self._client.get(key)
        except RedisError as exc:
            LOGGER.warning("Falha ao consultar cache Redis (%s): %s", key, exc)
            return None

        if not payload_raw:
            return None

        try:
            payload = json.loads(payload_raw)
        except Exception:  # noqa: BLE001
            LOGGER.warning("Payload invalido no cache Redis (%s).", key)
            return None

        if payload.get("version") != self.CACHE_VERSION:
            return None

        created_at_raw = payload.get("created_at")
        if not created_at_raw:
            return None

        try:
            created_at = datetime.fromisoformat(created_at_raw)
        except ValueError:
            return None

        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        ttl = timedelta(minutes=max(ttl_minutes, 0))
        if datetime.now(timezone.utc) - created_at > ttl:
            return None

        records = payload.get("records", [])
        quotes = []
        for record in records:
            symbol = str(record.get("symbol", "")).strip()
            name = str(record.get("name", "")).strip()
            price = str(record.get("price", "")).strip()
            if not symbol or not name:
                continue
            quotes.append(EquityQuote(symbol=symbol, name=name, price=price))

        return quotes

    def save(self, region: str, records: List[EquityQuote]) -> str:
        key = self._cache_key(region)
        payload = {
            "version": self.CACHE_VERSION,
            "region": region,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "records": [asdict(record) for record in records],
        }

        try:
            self._client.set(
                key,
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            )
        except RedisError as exc:
            LOGGER.warning("Falha ao salvar cache Redis (%s): %s", key, exc)

        return key

    def _cache_key(self, region: str) -> str:
        normalized = self._normalize_region(region)
        return "{0}:{1}".format(self._key_prefix, normalized)

    def _normalize_region(self, region: str) -> str:
        normalized = region.strip().lower()
        normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
        normalized = normalized.strip("_")
        return normalized or "unknown_region"
