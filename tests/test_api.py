import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from yahoo_crawler import api
from yahoo_crawler.application.crawl_service import CrawlExecutionResult


class _ImmediateExecutor:
    def submit(self, fn, *args, **kwargs):
        fn(*args, **kwargs)
        return None


@pytest.fixture(autouse=True)
def _reset_jobs() -> None:
    with api._jobs_lock:
        api._jobs.clear()
    yield
    with api._jobs_lock:
        api._jobs.clear()


def test_health_endpoint_returns_ok() -> None:
    assert api.health() == {"status": "ok"}


def test_options_endpoint_exposes_defaults_and_endpoints() -> None:
    payload = api.options()

    assert "/crawl" in payload["endpoints"]
    assert payload["defaults"]["region"] == "Argentina"
    assert payload["defaults"]["timeout_seconds"] == 45


def test_crawl_endpoint_returns_result_payload(monkeypatch) -> None:
    def _fake_run(_params):
        return CrawlExecutionResult(
            output_path="output/test.csv",
            total_records=2,
            source="live",
        )

    monkeypatch.setattr(api, "run_crawl_job", _fake_run)

    response = api.crawl(api.CrawlRequest(region="Argentina"))

    assert response.success is True
    assert response.source == "live"
    assert response.total_records == 2
    assert response.output_path == "output/test.csv"


def test_crawl_endpoint_raises_http_500_when_execution_fails(monkeypatch) -> None:
    def _failing_run(_params):
        raise RuntimeError("erro no crawler")

    monkeypatch.setattr(api, "run_crawl_job", _failing_run)

    with pytest.raises(HTTPException) as excinfo:
        api.crawl(api.CrawlRequest(region="Argentina"))

    assert excinfo.value.status_code == 500
    assert excinfo.value.detail == "erro no crawler"


def test_crawl_submit_and_status_completed(monkeypatch) -> None:
    def _fake_run(_params):
        return CrawlExecutionResult(
            output_path="output/async.csv",
            total_records=1,
            source="cache",
        )

    monkeypatch.setattr(api, "run_crawl_job", _fake_run)
    monkeypatch.setattr(api, "_executor", _ImmediateExecutor())

    submit_response = api.crawl_submit(api.CrawlRequest(region="Argentina"))
    status_response = api.crawl_job_status(submit_response.job_id)

    assert submit_response.accepted is True
    assert submit_response.status == "queued"
    assert status_response.status == "completed"
    assert status_response.result is not None
    assert status_response.result.source == "cache"
    assert status_response.result.total_records == 1
    assert status_response.error is None


def test_crawl_submit_and_status_failed(monkeypatch) -> None:
    def _failing_run(_params):
        raise RuntimeError("falha assincrona")

    monkeypatch.setattr(api, "run_crawl_job", _failing_run)
    monkeypatch.setattr(api, "_executor", _ImmediateExecutor())

    submit_response = api.crawl_submit(api.CrawlRequest(region="Argentina"))
    status_response = api.crawl_job_status(submit_response.job_id)

    assert status_response.status == "failed"
    assert status_response.result is None
    assert "falha assincrona" in str(status_response.error)


def test_crawl_job_status_raises_404_for_unknown_job() -> None:
    with pytest.raises(HTTPException) as excinfo:
        api.crawl_job_status("inexistente")

    assert excinfo.value.status_code == 404


def test_crawl_request_validates_required_region() -> None:
    with pytest.raises(ValidationError):
        api.CrawlRequest()
