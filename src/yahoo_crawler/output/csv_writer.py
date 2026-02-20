import csv
from pathlib import Path
from typing import Iterable

from yahoo_crawler.domain.models import EquityQuote


class CsvWriter:
    @staticmethod
    def write(output_path: str, records: Iterable[EquityQuote]) -> Path:
        path = Path(output_path)
        if path.parent and not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", encoding="utf-8", newline="") as csvfile:
            writer = csv.DictWriter(
                csvfile,
                fieldnames=["symbol", "name", "price"],
                quoting=csv.QUOTE_ALL,
            )
            writer.writeheader()
            for record in records:
                writer.writerow(
                    {
                        "symbol": record.symbol,
                        "name": record.name,
                        "price": record.price,
                    }
                )

        return path
