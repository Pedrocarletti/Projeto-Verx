from dataclasses import dataclass


@dataclass(frozen=True)
class EquityQuote:
    symbol: str
    name: str
    price: str
