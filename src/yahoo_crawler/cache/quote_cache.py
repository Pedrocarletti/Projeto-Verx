import json
import logging
import re
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

from yahoo_crawler.domain.models import EquityQuote

LOGGER = logging.getLogger(__name__)


class QuoteCache:
    CACHE_VERSION = 1

    def __init__(self, cache_dir: str) -> None:
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def load(self, region: str, ttl_minutes: int) -> Optional[List[EquityQuote]]:
        path = self._cache_file(region)
        if not path.exists():
            return None

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            LOGGER.warning("Arquivo de cache invalido: %s", path)
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

    def save(self, region: str, records: List[EquityQuote]) -> Path:
        path = self._cache_file(region)
        payload = {
            "version": self.CACHE_VERSION,
            "region": region,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "records": [asdict(record) for record in records],
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        return path

    def _cache_file(self, region: str) -> Path:
        normalized = self._normalize_region(region)
        return self._cache_dir / "{0}.json".format(normalized)

    def _normalize_region(self, region: str) -> str:
        normalized = region.strip().lower()
        normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
        normalized = normalized.strip("_")
        return normalized or "unknown_region"
