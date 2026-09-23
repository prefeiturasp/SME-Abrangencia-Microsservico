"""Test runner para criação de tabelas não gerenciadas."""

from typing import Any

from django.apps import apps
from django.db import connections
from django.test.runner import DiscoverRunner


class AbrangenciaTestRunner(DiscoverRunner):
    """Cria tabelas não gerenciadas antes de executar os testes."""

    def setup_databases(self, **kwargs: Any) -> Any:
        """Cria as tabelas dos models não gerenciados e prepara o banco."""
        result = super().setup_databases(**kwargs)
        with connections["default"].schema_editor() as editor:
            created_tables = set()
            for model in apps.get_models():
                if not model._meta.managed:
                    table_name = model._meta.db_table
                    if table_name not in created_tables:
                        editor.create_model(model)
                        created_tables.add(table_name)
        return result
