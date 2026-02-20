import os
import time
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, root_validator

from yahoo_crawler.application.crawl_service import (
    CrawlExecutionParams,
    CrawlExecutionResult,
    run_crawl_job,
)

DEFAULT_CACHE_TTL_MINUTES = 30
DEFAULT_REDIS_URL = "redis://localhost:6379/0"
DEFAULT_REDIS_KEY_PREFIX = "yahoo_crawler:quotes"


class CrawlRequest(BaseModel):
    region: str = Field(..., example="Argentina", description="Region filter value in Yahoo.")
    out: str = Field(
        "output/equities.csv",
        example="output/argentina.csv",
        description="Output CSV path.",
    )
    max_pages: Optional[int] = Field(
        None, example=3, description="Page limit for crawl (optional)."
    )
    timeout_seconds: int = Field(
        45, ge=10, le=180, description="Selenium wait timeout in seconds."
    )
    headless: bool = Field(
        True, description="Run browser in headless mode when True."
    )
    log_level: str = Field(
        "INFO", example="INFO", description="DEBUG, INFO, WARNING, or ERROR."
    )
    use_cache: bool = Field(
        False,
        description="Enable region cache to avoid recrawls in repeated runs.",
    )

    @root_validator(pre=True)
    def _reject_unknown_fields(cls, values):
        allowed_fields = {
            "region",
            "out",
            "max_pages",
            "timeout_seconds",
            "headless",
            "log_level",
            "use_cache",
        }
        unknown_fields = sorted(set(values.keys()) - allowed_fields)
        if unknown_fields:
            raise ValueError(
                "Unknown field(s): {0}".format(", ".join(unknown_fields))
            )
        return values


class CrawlResponse(BaseModel):
    success: bool
    source: str
    output_path: str
    total_records: int
    elapsed_seconds: float


app = FastAPI(
    title="Yahoo Screener Crawler API",
    description=(
        "API to run the Yahoo Finance equities crawler. "
        "Use /docs to test parameters with Swagger."
    ),
    version="0.1.0",
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/meta/options")
def options() -> dict:
    return {
        "endpoints": [
            "/health",
            "/meta/options",
            "/crawl",
        ],
        "notes": [
            "Use POST /crawl for synchronous execution (waits until done).",
            (
                "Redis cache settings come from environment variables: "
                "YAHOO_CRAWLER_CACHE_TTL_MINUTES, YAHOO_CRAWLER_REDIS_URL, "
                "and YAHOO_CRAWLER_REDIS_KEY_PREFIX."
            ),
            "Swagger: /docs",
            "ReDoc: /redoc",
        ],
        "defaults": {
            "region": "Argentina",
            "out": "output/equities.csv",
            "max_pages": None,
            "timeout_seconds": 45,
            "headless": True,
            "log_level": "INFO",
            "use_cache": False,
        },
    }


@app.post("/crawl", response_model=CrawlResponse)
def crawl(request: CrawlRequest) -> CrawlResponse:
    start = time.perf_counter()
    cache_ttl_minutes = _read_int_env(
        "YAHOO_CRAWLER_CACHE_TTL_MINUTES",
        DEFAULT_CACHE_TTL_MINUTES,
        minimum=0,
        maximum=1440,
    )
    redis_url = _read_str_env("YAHOO_CRAWLER_REDIS_URL", DEFAULT_REDIS_URL)
    redis_key_prefix = _read_str_env(
        "YAHOO_CRAWLER_REDIS_KEY_PREFIX", DEFAULT_REDIS_KEY_PREFIX
    )

    params = CrawlExecutionParams(
        region=request.region,
        out=request.out,
        max_pages=request.max_pages,
        timeout_seconds=request.timeout_seconds,
        headless=request.headless,
        log_level=request.log_level,
        use_cache=request.use_cache,
        cache_ttl_minutes=cache_ttl_minutes,
        redis_url=redis_url,
        redis_key_prefix=redis_key_prefix,
    )

    try:
        result: CrawlExecutionResult = run_crawl_job(params)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return CrawlResponse(
        success=True,
        source=result.source,
        output_path=result.output_path,
        total_records=result.total_records,
        elapsed_seconds=round(time.perf_counter() - start, 3),
    )

def _read_str_env(name: str, default: str) -> str:
    return os.getenv(name, default).strip() or default


def _read_int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default

    try:
        value = int(raw.strip())
    except ValueError:
        return default

    return max(minimum, min(maximum, value))


def run() -> None:
    host = os.getenv("YAHOO_CRAWLER_API_HOST", "127.0.0.1")
    port = int(os.getenv("YAHOO_CRAWLER_API_PORT", "8000"))
    uvicorn.run("yahoo_crawler.api:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    run()
