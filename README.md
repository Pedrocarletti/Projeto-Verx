# Yahoo Screener Crawler

Crawler em Python para extrair `symbol`, `name` e `price (intraday)` do Yahoo Finance Equity Screener:

- URL alvo: `https://finance.yahoo.com/research-hub/screener/equity/`
- Stack obrigatoria usada: `Selenium` + `BeautifulSoup` + `orientacao a objetos`
- Saida: arquivo CSV com colunas `"symbol","name","price"`

## Requisitos

- Python 3.7+
- Google Chrome instalado

## Instalar

```bash
python -m pip install -r requirements.txt
```

ou:

```bash
python -m pip install .
```

## Executar

```bash
python -m yahoo_crawler.cli --region "Argentina" --out output/argentina.csv
```

Opcoes uteis:

```bash
python -m yahoo_crawler.cli --region "Argentina" --out output/argentina.csv --max-pages 10 --timeout 60 --no-headless
```

Com cache local (melhor para execucoes repetidas):

```bash
python -m yahoo_crawler.cli --region "Argentina" --out output/argentina.csv --use-cache --cache-ttl-minutes 30
```

## API + Swagger

Suba a API:

```bash
python -m uvicorn yahoo_crawler.api:app --host 127.0.0.1 --port 8000
```

Abra no navegador:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

Endpoints:

- `GET /health`
- `GET /meta/options`
- `POST /crawl` (sincrono, espera terminar)
- `POST /crawl/submit` (assíncrono, retorna `job_id` imediato)
- `GET /crawl/jobs/{job_id}` (consulta status)

Exemplo de request no `POST /crawl`:

```json
{
  "region": "Argentina",
  "out": "output/argentina.csv",
  "max_pages": 2,
  "timeout_seconds": 60,
  "headless": true,
  "log_level": "INFO",
  "use_cache": true,
  "cache_dir": ".cache/yahoo_crawler",
  "cache_ttl_minutes": 30
}
```

Fluxo recomendado para nao bloquear no Swagger:

1. Chame `POST /crawl/submit` com o mesmo body do crawl.
2. Copie o `job_id` retornado.
3. Consulte `GET /crawl/jobs/{job_id}` ate `status = completed` ou `failed`.

## Formato do CSV

Exemplo:

```csv
"symbol","name","price"
"AMX.BA","America Movil, S.A.B. de C.V.","2089.00"
"NOKA.BA","Nokia Corporation","557.50"
```

## Arquitetura

```text
src/yahoo_crawler/
  application/
    screener_crawler.py      # orquestracao do caso de uso
    crawl_service.py         # servico compartilhado (CLI/API)
  cache/
    quote_cache.py           # cache persistente por regiao (TTL)
  domain/
    models.py                # EquityQuote
  infrastructure/
    webdriver_factory.py     # criacao/config Selenium
    yahoo_client.py          # navegacao, filtro region, paginacao
  output/
    csv_writer.py            # escrita CSV
  parsing/
    screener_parser.py       # parsing com BeautifulSoup
  cli.py                     # interface de linha de comando
  api.py                     # API HTTP com Swagger
```

## Testes unitarios

```bash
pytest -q
```

Limpeza de artefatos locais:

```powershell
.\scripts\cleanup.ps1
```

Para limpar tambem arquivos em `output/`:

```powershell
.\scripts\cleanup.ps1 -RemoveOutputFiles
```

Cobertura de testes:

- parser (`BeautifulSoup`) com fixture HTML
- escrita de CSV
- orquestracao (paginas + deduplicacao + parametro `region`)

## Observacoes de robustez

- Esperas explicitas (`WebDriverWait`) no Selenium
- Seletor por `data-testid` para tabela/paginacao
- Deduplicacao por `symbol` no nivel da aplicacao
- `--max-pages` para execucao controlada em cenarios muito grandes

## Performance

- Cache persistente por regiao (`--use-cache`) com TTL configuravel (`--cache-ttl-minutes`)
- Parse com BeautifulSoup apenas do HTML da tabela (evita parse da pagina inteira)
- Cache em memoria de parsing por hash da pagina (evita retrabalho se pagina repetir)
- Uma chamada por iteracao para verificar `next page` (menos ida ao Selenium)

## CI/CD no GitHub Actions

Workflows adicionados:

- `./.github/workflows/ci.yml`: roda `ruff`, `mypy` e `pytest` em `push`/`pull_request` para `main` e `master` (com disparo manual).
- `./.github/workflows/cd.yml`: roda quality gates, build de imagem Docker, scan de seguranca com Trivy e deploy automatico no ECS por ambiente.

Fluxo de deploy:

- `push` na `main` ou `master`: deploy em `dev`
- `push` de tag `v*`: deploy em `hml` e depois `prod`
- `workflow_dispatch`: deploy manual escolhendo `dev`, `hml` ou `prod` e opcionalmente `image_tag`

Configuracao no GitHub:

1. Crie os environments: `dev`, `hml`, `prod`.
2. No environment `prod`, habilite `Required reviewers` para aprovacao antes do deploy.
3. Configure as variaveis (`Settings > Secrets and variables > Actions > Variables`):
   - Repo-level: `AWS_REGION`, `ECR_REPOSITORY`
   - Environment-level (`dev`/`hml`/`prod`): `ECS_CLUSTER`, `ECS_SERVICE`, `ECS_CONTAINER_NAME`
4. Configure o segredo (`Settings > Secrets and variables > Actions > Secrets`):
   - Repo-level: `AWS_ROLE_TO_ASSUME` (role AWS com OIDC para GitHub Actions, permissao em ECR + ECS)

Release para subir `hml` e `prod`:

```bash
git tag v0.1.0
git push origin v0.1.0
```

## Entrega no GitHub

Depois de validar localmente, publique no seu repositório e compartilhe o link:

```bash
git init
git add .
git commit -m "feat: yahoo equity screener crawler with selenium + bs4 + tests"
git branch -M main
git remote add origin <SEU_REPO_URL>
git push -u origin main
```
