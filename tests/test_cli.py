from yahoo_crawler import cli
from yahoo_crawler.application.crawl_service import CrawlExecutionResult


def test_build_args_parses_supported_flags() -> None:
    args = cli._build_args(
        [
            "--region",
            "Argentina",
            "--out",
            "output/custom.csv",
            "--max-pages",
            "5",
            "--timeout",
            "60",
            "--no-headless",
            "--log-level",
            "DEBUG",
            "--use-cache",
            "--cache-ttl-minutes",
            "90",
            "--redis-url",
            "redis://localhost:6379/1",
            "--redis-key-prefix",
            "verx:test",
        ]
    )

    assert args.region == "Argentina"
    assert args.out == "output/custom.csv"
    assert args.max_pages == 5
    assert args.timeout == 60
    assert args.no_headless is True
    assert args.log_level == "DEBUG"
    assert args.use_cache is True
    assert args.cache_ttl_minutes == 90
    assert args.redis_url == "redis://localhost:6379/1"
    assert args.redis_key_prefix == "verx:test"


def test_main_returns_zero_and_maps_cli_args(monkeypatch) -> None:
    captured = {}

    def _fake_run(params):
        captured["params"] = params
        return CrawlExecutionResult(
            output_path=params.out,
            total_records=3,
            source="live",
        )

    monkeypatch.setattr(cli, "configure_logging", lambda _level: None)
    monkeypatch.setattr(cli, "run_crawl_job", _fake_run)

    exit_code = cli.main(
        [
            "--region",
            "Argentina",
            "--out",
            "output/result.csv",
            "--max-pages",
            "2",
            "--timeout",
            "30",
            "--no-headless",
            "--log-level",
            "WARNING",
            "--use-cache",
            "--cache-ttl-minutes",
            "15",
            "--redis-url",
            "redis://localhost:6379/2",
            "--redis-key-prefix",
            "verx:prod",
        ]
    )

    params = captured["params"]
    assert exit_code == 0
    assert params.region == "Argentina"
    assert params.out == "output/result.csv"
    assert params.max_pages == 2
    assert params.timeout_seconds == 30
    assert params.headless is False
    assert params.log_level == "WARNING"
    assert params.use_cache is True
    assert params.cache_ttl_minutes == 15
    assert params.redis_url == "redis://localhost:6379/2"
    assert params.redis_key_prefix == "verx:prod"


def test_main_returns_one_when_crawl_job_fails(monkeypatch) -> None:
    def _failing_run(_params):
        raise RuntimeError("execution error")

    monkeypatch.setattr(cli, "configure_logging", lambda _level: None)
    monkeypatch.setattr(cli, "run_crawl_job", _failing_run)

    exit_code = cli.main(["--region", "Argentina"])

    assert exit_code == 1
