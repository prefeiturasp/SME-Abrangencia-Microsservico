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

## Executar Testes com Docker

```bash
docker compose -f docker-compose-dev.yml run --rm abrangencia \
  python -m coverage run --source=apps.abrangencia manage.py test apps.abrangencia --noinput --settings=config.settings

docker compose -f docker-compose-dev.yml run --rm abrangencia \
  python -m coverage report
```

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
| `/abrangencia/api/v1/docs/schema/` | Schema OpenAPI 3 |

---

## Endpoints Implementados

| Legado | Metodo | Path | Atende |
|--------|--------|------|--------|
| E-01 | GET | `/api/abrangencia/{id_perfil}` | Retorna cargos, funcoes e tipo de abrangencia do perfil consultado. |
| E-07 | GET | `/api/abrangencia/compacta-vigente/{login}/perfil/{id_perfil}` | Retorna o escopo compacto vigente do usuario no perfil, sem listas detalhadas. |
| E-08 | GET | `/api/abrangencia/compacta-vigente/{login}/perfil/{id_perfil}/DreDetalhes` | Retorna o escopo detalhado com DREs expandidas quando o tipo de abrangencia permite. |
| E-09 | GET | `/api/abrangencia/compacta-vigente/{login}/perfil/{id_perfil}/Sondagem` | Retorna o escopo detalhado com listas expandidas e turmas elegiveis para sondagem. |
| E-10 | GET | `/api/abrangencia/compacta-semRedis/{login}/perfil/{id_perfil}` | Retorna o escopo detalhado sem expandir DREs, UEs ou turmas. |
| E-13 | POST | `/api/abrangencia/perfis/usuarios` | Lista usuarios por UE, com seus perfis e UEs vinculadas. |

---

## Observacoes de Contrato

- As rotas do dominio nao usam barra final mantendo compatibilidade com o legado.
- Campos em camelCase preservam o contrato existente na API legado.
