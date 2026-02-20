import argparse
import logging
import sys
from typing import Optional

from yahoo_crawler.application.crawl_service import CrawlExecutionParams, run_crawl_job
from yahoo_crawler.utils.logging_config import configure_logging


def _build_args(argv: Optional[list] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Crawler Yahoo Finance (equity screener) com Selenium + BeautifulSoup."
        )
    )
    parser.add_argument(
        "--region",
        required=True,
        help='Nome da regiao exatamente como aparece no filtro do Yahoo. Ex.: "Argentina"',
    )
    parser.add_argument(
        "--out",
        default="output/equities.csv",
        help="Caminho do CSV de saida. Padrao: output/equities.csv",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Limite de paginas para crawl (opcional).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=45,
        help="Timeout de espera do Selenium em segundos.",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Executa navegador com interface visual.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Nivel de log (DEBUG, INFO, WARNING, ERROR).",
    )
    parser.add_argument(
        "--use-cache",
        action="store_true",
        help="Ativa cache local por regiao para evitar recrawls em execucoes repetidas.",
    )
    parser.add_argument(
        "--cache-dir",
        default=".cache/yahoo_crawler",
        help="Diretorio do cache local. Padrao: .cache/yahoo_crawler",
    )
    parser.add_argument(
        "--cache-ttl-minutes",
        type=int,
        default=30,
        help="Tempo de vida do cache em minutos. Padrao: 30.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list] = None) -> int:
    args = _build_args(argv)
    configure_logging(args.log_level)
    logger = logging.getLogger(__name__)

    params = CrawlExecutionParams(
        region=args.region,
        out=args.out,
        max_pages=args.max_pages,
        timeout_seconds=args.timeout,
        headless=not args.no_headless,
        log_level=args.log_level,
        use_cache=args.use_cache,
        cache_dir=args.cache_dir,
        cache_ttl_minutes=args.cache_ttl_minutes,
    )

    try:
        result = run_crawl_job(params)
        logger.info("Fonte do resultado: %s", result.source)
        logger.info("CSV gerado em: %s", result.output_path)
        logger.info("Total de registros escritos: %s", result.total_records)
        return 0
    except Exception as exc:  # noqa: BLE001
        logger.exception("Falha na execucao do crawler: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
