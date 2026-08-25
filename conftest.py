"""Configuração da suíte pytest.

Os models do domínio Abrangência são `managed=False` — o schema pertence
ao pipeline `sme-airflow`, versionado por Flyway. O banco de teste do
pytest-django não tem esse schema por padrão, então esta fixture cria as
tabelas a partir dos próprios models antes da suíte rodar.
"""

import pytest
from django.apps import apps
from django.db import connections


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    """Cria as tabelas dos models não gerenciados no banco de teste."""
    with (
        django_db_blocker.unblock(),
        connections["default"].schema_editor() as editor,
    ):
        criadas = set()
        for model in apps.get_models():
            if not model._meta.managed:
                tabela = model._meta.db_table
                if tabela not in criadas:
                    editor.create_model(model)
                    criadas.add(tabela)
