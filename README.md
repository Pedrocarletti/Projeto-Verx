# Yahoo Screener Crawler

Python crawler to extract `symbol`, `name`, and `price (intraday)` from the Yahoo Finance Equity Screener:

- Target URL: `https://finance.yahoo.com/research-hub/screener/equity/`
- Required stack: `Selenium` + `BeautifulSoup` + `object-oriented design`
- Output: CSV file with columns `"symbol","name","price"`

## Requirements

- Python 3.7+
- Google Chrome installed
- Redis server (only if you want cache hits with `--use-cache` or `use_cache=true`)

## Install

```bash
python -m pip install -r requirements.txt
```

or:

```bash
python -m pip install .
```

## Run

```bash
python -m yahoo_crawler.cli --region "Argentina" --out output/argentina.csv
```

Useful options:

```bash
python -m yahoo_crawler.cli --region "Argentina" --out output/argentina.csv --max-pages 10 --timeout 60 --no-headless
```

With cache enabled (Redis-only):

```bash
python -m yahoo_crawler.cli --region "Argentina" --out output/argentina.csv --use-cache --redis-url "redis://localhost:6379/0" --redis-key-prefix "yahoo_crawler:quotes" --cache-ttl-minutes 30
```

Note: cache options (`--cache-ttl-minutes`, `--redis-url`, `--redis-key-prefix`) are relevant only when `--use-cache` is enabled.

## API + Swagger

Start the API:

```bash
python -m yahoo_crawler.api
```

Alternative (explicit host/port):

```bash
python -m uvicorn yahoo_crawler.api:app --host 127.0.0.1 --port 8000
```

Open in browser:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

Endpoints:

- `GET /health`
- `GET /meta/options`
- `POST /crawl` (synchronous, waits to finish)

Current API model:

- Only synchronous crawl is supported (`/crawl`).
- `POST /crawl` request body uses only `use_cache` for cache toggle.
- Redis settings come from environment variables.
- Local filesystem cache backend is not available anymore.

Example request body for `POST /crawl`:

```json
{
  "region": "Argentina",
  "out": "output/argentina.csv",
  "max_pages": 2,
  "timeout_seconds": 60,
  "headless": true,
  "log_level": "INFO",
  "use_cache": true
}
```

Recommended flow in Swagger:

1. Call `POST /crawl` directly with your request body.
2. Wait for the crawl execution response.

Cache behavior for API runs comes from environment variables:

- `YAHOO_CRAWLER_API_HOST` (default: `127.0.0.1`)
- `YAHOO_CRAWLER_API_PORT` (default: `8000`)
- `YAHOO_CRAWLER_CACHE_TTL_MINUTES` (default: `30`)
- `YAHOO_CRAWLER_REDIS_URL` (default: `redis://localhost:6379/0`)
- `YAHOO_CRAWLER_REDIS_KEY_PREFIX` (default: `yahoo_crawler:quotes`)

Note: API does not auto-load a `.env` file by itself. Export env vars in your shell or use your process manager/container setup.

If `use_cache` is `false`, Redis is not used during the crawl execution.

## CSV Format

Example:

```csv
"symbol","name","price"
"AMX.BA","America Movil, S.A.B. de C.V.","2089.00"
"NOKA.BA","Nokia Corporation","557.50"
```

## Architecture

```text
src/yahoo_crawler/
  application/
    screener_crawler.py      # use-case orchestration
    crawl_service.py         # shared service for CLI/API
  cache/
    redis_quote_cache.py     # per-region Redis cache (TTL via created_at)
  domain/
    models.py                # EquityQuote
  infrastructure/
    webdriver_factory.py     # Selenium driver creation/config
    yahoo_client.py          # navigation, region filter, pagination
  output/
    csv_writer.py            # CSV writing
  parsing/
    screener_parser.py       # BeautifulSoup parsing
  cli.py                     # command-line interface
  api.py                     # HTTP API with Swagger
```

## Unit Tests

```bash
pytest -q
```

Clean local artifacts:

```powershell
.\scripts\cleanup.ps1
```

Also remove files inside `output/`:

```powershell
.\scripts\cleanup.ps1 -RemoveOutputFiles
```

Test coverage includes:

- parser (`BeautifulSoup`) using HTML fixtures
- CSV writer
- orchestration (pagination + deduplication + `region` parameter)
- API validation for `/crawl` payload and defaults

## Robustness Notes

- Explicit waits (`WebDriverWait`) in Selenium
- `data-testid` selectors for table/pagination
- Deduplication by `symbol` at application level
- `--max-pages` for controlled execution in very large datasets

## Performance

- Per-region persistent cache (`--use-cache`) with configurable TTL (`--cache-ttl-minutes`)
- Redis-only cache backend
- BeautifulSoup parses table HTML only (avoids parsing full page)
- In-memory parse cache by page hash (avoids repeated parsing)
- One call per iteration for `next page` check (fewer Selenium trips)

## CI/CD on GitHub Actions

Workflows:

- `./.github/workflows/ci.yml`: runs `ruff`, `mypy`, and `pytest` on `push`/`pull_request` to `main` and `master` (plus manual trigger).
- `./.github/workflows/cd.yml`: only builds the Docker image (no AWS, no ECR, no ECS).

Current flow:

- `push`/`pull_request`: `ci.yml` validates code quality (`ruff`, `mypy`, `pytest`).
- `push` to `main`/`master` or tag `v*`: `cd.yml` validates that `Dockerfile` builds.
- `workflow_dispatch`: runs `cd.yml` manually with optional `image_tag`.

GitHub setup for current scenario:

- No AWS variables or secrets are required by the active workflows.
