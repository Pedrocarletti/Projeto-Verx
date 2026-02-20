import os
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import Dict, Optional
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from yahoo_crawler.application.crawl_service import (
    CrawlExecutionParams,
    CrawlExecutionResult,
    run_crawl_job,
)


class CrawlRequest(BaseModel):
    region: str = Field(..., example="Argentina", description="Regiao do filtro no Yahoo.")
    out: str = Field(
        "output/equities.csv",
        example="output/argentina.csv",
        description="Caminho do CSV de saida.",
    )
    max_pages: Optional[int] = Field(
        None, example=3, description="Limite de paginas para crawl (opcional)."
    )
    timeout_seconds: int = Field(
        45, ge=10, le=180, description="Timeout de espera do Selenium em segundos."
    )
    headless: bool = Field(
        True, description="Executa navegador sem interface visual quando True."
    )
    log_level: str = Field(
        "INFO", example="INFO", description="DEBUG, INFO, WARNING ou ERROR."
    )
    use_cache: bool = Field(
        False,
        description="Ativa cache local por regiao para evitar recrawls em execucoes repetidas.",
    )
    cache_dir: str = Field(
        ".cache/yahoo_crawler", description="Diretorio para arquivos de cache."
    )
    cache_ttl_minutes: int = Field(
        30, ge=0, le=1440, description="TTL do cache em minutos."
    )


class CrawlResponse(BaseModel):
    success: bool
    source: str
    output_path: str
    total_records: int
    elapsed_seconds: float


class CrawlSubmitResponse(BaseModel):
    accepted: bool
    job_id: str
    status: str


class CrawlJobStatusResponse(BaseModel):
    job_id: str
    status: str
    submitted_at: float
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    elapsed_seconds: Optional[float] = None
    result: Optional[CrawlResponse] = None
    error: Optional[str] = None


app = FastAPI(
    title="Yahoo Screener Crawler API",
    description=(
        "API para executar o crawler de equities do Yahoo Finance. "
        "Use /docs para testar os parametros via Swagger."
    ),
    version="0.1.0",
)

_executor = ThreadPoolExecutor(max_workers=2)
_jobs_lock = Lock()
_jobs: Dict[str, dict] = {}


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
            "/crawl/submit",
            "/crawl/jobs/{job_id}",
        ],
        "notes": [
            "Use POST /crawl para execucao sincrona (espera terminar).",
            "Use POST /crawl/submit para iniciar sem bloquear e depois consultar status.",
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
            "cache_dir": ".cache/yahoo_crawler",
            "cache_ttl_minutes": 30,
        },
    }


@app.post("/crawl", response_model=CrawlResponse)
def crawl(request: CrawlRequest) -> CrawlResponse:
    start = time.perf_counter()
    params = CrawlExecutionParams(
        region=request.region,
        out=request.out,
        max_pages=request.max_pages,
        timeout_seconds=request.timeout_seconds,
        headless=request.headless,
        log_level=request.log_level,
        use_cache=request.use_cache,
        cache_dir=request.cache_dir,
        cache_ttl_minutes=request.cache_ttl_minutes,
    )

    try:
        result: CrawlExecutionResult = run_crawl_job(params)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc))

    return CrawlResponse(
        success=True,
        source=result.source,
        output_path=result.output_path,
        total_records=result.total_records,
        elapsed_seconds=round(time.perf_counter() - start, 3),
    )


@app.post("/crawl/submit", response_model=CrawlSubmitResponse)
def crawl_submit(request: CrawlRequest) -> CrawlSubmitResponse:
    job_id = str(uuid4())
    submitted_at = time.time()

    with _jobs_lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "submitted_at": submitted_at,
            "started_at": None,
            "finished_at": None,
            "elapsed_seconds": None,
            "result": None,
            "error": None,
        }

    _executor.submit(_run_crawl_job_async, job_id, request)
    return CrawlSubmitResponse(accepted=True, job_id=job_id, status="queued")


@app.get("/crawl/jobs/{job_id}", response_model=CrawlJobStatusResponse)
def crawl_job_status(job_id: str) -> CrawlJobStatusResponse:
    with _jobs_lock:
        job = _jobs.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="job_id nao encontrado.")

    return CrawlJobStatusResponse(**job)


def _run_crawl_job_async(job_id: str, request: CrawlRequest) -> None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return
        job["status"] = "running"
        job["started_at"] = time.time()

    start = time.perf_counter()
    params = CrawlExecutionParams(
        region=request.region,
        out=request.out,
        max_pages=request.max_pages,
        timeout_seconds=request.timeout_seconds,
        headless=request.headless,
        log_level=request.log_level,
        use_cache=request.use_cache,
        cache_dir=request.cache_dir,
        cache_ttl_minutes=request.cache_ttl_minutes,
    )

    try:
        result: CrawlExecutionResult = run_crawl_job(params)
        response = CrawlResponse(
            success=True,
            source=result.source,
            output_path=result.output_path,
            total_records=result.total_records,
            elapsed_seconds=round(time.perf_counter() - start, 3),
        )
        finished_at = time.time()
        with _jobs_lock:
            job = _jobs.get(job_id)
            if not job:
                return
            job["status"] = "completed"
            job["finished_at"] = finished_at
            job["elapsed_seconds"] = response.elapsed_seconds
            job["result"] = response
            job["error"] = None
    except Exception as exc:  # noqa: BLE001
        finished_at = time.time()
        with _jobs_lock:
            job = _jobs.get(job_id)
            if not job:
                return
            job["status"] = "failed"
            job["finished_at"] = finished_at
            job["elapsed_seconds"] = round(time.perf_counter() - start, 3)
            job["error"] = str(exc)
            job["result"] = None


def run() -> None:
    host = os.getenv("YAHOO_CRAWLER_API_HOST", "127.0.0.1")
    port = int(os.getenv("YAHOO_CRAWLER_API_PORT", "8000"))
    uvicorn.run("yahoo_crawler.api:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    run()
