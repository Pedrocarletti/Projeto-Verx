from dataclasses import dataclass


@dataclass
class CrawlerConfig:
    base_url: str = "https://finance.yahoo.com/research-hub/screener/equity/"
    timeout_seconds: int = 45
    headless: bool = True
    page_load_timeout_seconds: int = 60
    cache_enabled: bool = False
    cache_dir: str = ".cache/yahoo_crawler"
    cache_ttl_minutes: int = 30
