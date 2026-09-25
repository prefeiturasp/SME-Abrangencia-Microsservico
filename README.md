# SME-Abrangencia-Microsservico

Expoe, em contrato compativel com o legado, os perfis, vinculos funcionais e escopos de DRE, UE e turma usados pelos sistemas integrados.

---

## Estrutura dos Apps

| App | Responsabilidade | Prefixo API |
|-----|------------------|-------------|
| `apps.abrangencia` | Perfis, escopo compacto e usuarios por perfil | `/api/abrangencia/` |
| `apps.autenticacao` | Autenticacao por API key | - |
| `apps.core` | Health check e infraestrutura comum | `/api/abrangencia/` |

### Modelos ETL Cobertos

- `Perfil`
- `PerfilVinculoFuncional`
- `AbrangenciaResolvida`
- `Unidade`
- `UsuarioPorPerfil`

Todos sao modelos de leitura (`managed=False`). O schema e as materialized views
sao mantidos pelo pipeline `sme-airflow`.

---

## Pre-requisitos

- Python 3.12+
- Docker e Docker Compose para rodar via container

---

## Rodar Localmente

```bash
cp .env.example .env
pip install -r requirements/local.txt
python manage.py runserver 0.0.0.0:8003
```

Acesse em: http://localhost:8003/abrangencia/api/v1/docs/

---

## Rodar com Docker

```bash
cp .env.example .env
docker compose -f docker-compose-dev.yml up --build
```

Acesse em: http://localhost:8003/abrangencia/api/v1/docs/

---

## Testes

```bash
# Local
python manage.py test

# Via docker (espelha pipeline)
./executar_testes_docker.sh

---

## Gerar Documentacao Sphinx com Docker

```bash
docker compose -f docker-compose-dev.yml run --rm abrangencia \
  sphinx-build -b html docs docs/_build/html
```

A documentacao HTML sera gerada em `docs/_build/html/index.html`.

---

## Autenticacao

Todos os endpoints do dominio exigem o header configurado em `API_KEY_HEADER`
com o valor de `API_KEY`.

Exemplo:

```bash
curl -H "X-API-Key: dev-key-default" \
  http://localhost:8003/api/abrangencia/2e89cf10-e42b-476f-8673-2dfbeeee3cd0
```

---

## Documentacao da API

| URL | Descricao |
|-----|-----------|
| `/abrangencia/api/v1/docs/` | Swagger UI |
| `/abrangencia/api/v1/docs/schema/` | Schema OpenAPI |

---

## Endpoints Implementados

| Metodo | Path | Atende 
|--------|------|--------|
| GET | `/api/abrangencia/{id_perfil}/` | Retorna cargos, funcoes e tipo de abrangencia do perfil consultado. |
| GET | `/api/abrangencia/compacta-vigente/{login}/perfil/{id_perfil}` | Retorna o escopo compacto vigente do usuario no perfil, sem listas detalhadas. |
| GET | `/api/abrangencia/compacta-vigente/{login}/perfil/{id_perfil}/DreDetalhes/` | Retorna o escopo detalhado com DREs expandidas quando o tipo de abrangencia permite. |
| GET | `/api/abrangencia/compacta-vigente/{login}/perfil/{id_perfil}/Sondagem/` | Retorna o escopo detalhado com listas expandidas e turmas elegiveis para sondagem. |
| GET | `/api/abrangencia/compacta-semRedis/{login}/perfil/{id_perfil}/` | Retorna o escopo detalhado sem expandir DREs, UEs ou turmas. |
| POST | `/api/abrangencia/perfis/usuarios` | Lista usuarios por UE, com seus perfis e UEs vinculadas. |
| GET | `/api/abrangencia/codigos-dres/` | SME-IntegracaoEOL-Institucional-Microsservico os codigos das DREs da rede. |
| GET | `/api/abrangencia/nome-abreviacao-dres/` | SME-IntegracaoEOL-Institucional-Microsservico as DREs da rede com nome e abreviacao. |
| GET | `/api/abrangencia/ciclo-ensino/` | Consulta SME-IntegracaoEOL-Pedagogico-Microsservico o catalogo de ciclos de ensino. |

---

**APIs externas**

| Variável                            | Padrão      | Descrição                                   |
| ----------------------------------- | ----------- | ------------------------------------------- |
| `INSTITUCIONAL_API_URL`             | —           | URL base do SME-IntegracaoEOL-Institucional-Microsservico, com o prefixo: `https://<host>/api/v1/institucional` |
| `INSTITUCIONAL_API_KEY`             | —           | Chave deste servico no SME-IntegracaoEOL-Institucional-Microsservico     |
| `PEDAGOGICO_API_URL`                | —           | URL base do MS-Pedagogico, com o prefixo: `https://<host>/api/v1/pedagogico` |
| `PEDAGOGICO_API_KEY`                | —           | Chave deste servico no MS-Pedagogico        |

A chave vai sempre no header `X-API-Key`. Sem URL, o servico sobe normalmente e as rotas que dependem da API respondem 503.

---

**SME Sidecar SDK**

| Variável                          | Padrão                  | Descrição                                       |
| --------------------------------- | ----------------------- | ----------------------------------------------- |
| `SME_SERVICE_NAME`                | `abrangencia-ms`        | Nome do serviço nos logs e traces               |
| `SME_SERVICE_VERSION`             | `unknown`               | Versão publicada na telemetria                  |
| `SME_ENVIRONMENT`                 | `dev`                   | Ambiente de execução                            |
| `SME_TIMEOUT_SECONDS`             | `10`                    | Timeout das chamadas às APIs externas           |
| `SME_LOG_LEVEL`                   | `ERROR`                 | Nível mínimo dos logs                           |
| `SME_LOG_FORMAT`                  | `json`                  | Formato `json` ou `console`                     |
| `SME_OTEL_ENABLED`                | `false`                 | Ativa tracing OpenTelemetry                     |
| `SME_OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4317` | URL OTLP gRPC configurada diretamente no `.env` |
| `SME_OTEL_EXPORTER_OTLP_HEADERS`  | —                       | Headers do exporter em `chave=valor`            |
| `SME_OTEL_EXPORTER_OTLP_INSECURE` | `true`                  | Desabilita TLS no transporte OTLP               |
| `SME_BROKER_URL`                  | —                       | URL AMQP para transporte opcional de logs       |
| `SME_LOG_QUEUE`                   | —                       | Fila de logs                           |
