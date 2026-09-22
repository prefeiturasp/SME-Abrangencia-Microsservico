COMPOSE      = docker compose -f docker-compose-dev.yml
EXEC         = $(COMPOSE) exec abrangencia
RUN          = $(COMPOSE) run --rm abrangencia
PYTEST_ARGS ?= --cov=apps --cov-report=term-missing --cov-fail-under=80

.PHONY: run build stop \
        test \
        lint coverage schema docs docs-clean help

help:
	@echo "Targets disponíveis:"
	@echo ""
	@echo "  Ambiente:"
	@echo "    make run              — sobe o projeto em modo dev"
	@echo "    make build            — rebuild da imagem dev"
	@echo "    make stop             — para e remove containers"
	@echo ""
	@echo "  Testes:"
	@echo "    make test             — todos os apps com cobertura ≥80%"
	@echo ""
	@echo "  Qualidade:"
	@echo "    make lint             — ruff + black + isort + mypy"
	@echo "    make coverage         — relatório HTML em docs/_cov/"
	@echo "    make schema           — gera schema OpenAPI em schema.yml"
	@echo "    make docs             — gera documentação Sphinx em docs/_build/html/"

# ---------------------------------------------------------------------------
# Ambiente — este projeto sobe sempre via docker-compose-dev.yml, nunca
# `python manage.py` direto no host.
# ---------------------------------------------------------------------------

run:
	$(COMPOSE) up

build:
	$(COMPOSE) up --build

stop:
	$(COMPOSE) down

# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------

test:
	$(RUN) python -m pytest $(PYTEST_ARGS) -v

# ---------------------------------------------------------------------------
# Qualidade
# ---------------------------------------------------------------------------

lint:
	$(EXEC) bash -c "\
		ruff check . && \
		mypy apps config"

coverage:
	$(RUN) python -m pytest $(PYTEST_ARGS) \
		--cov-report=html:docs/_cov
	@echo "Relatório gerado em docs/_cov/index.html"

schema:
	$(EXEC) python manage.py spectacular --file schema.yml
	@echo "Schema gerado em schema.yml"

docs:
	$(RUN) sphinx-build -b html docs docs/_build/html
	@echo "Documentação gerada em docs/_build/html/index.html"

docs-clean:
	rm -rf docs/_build
