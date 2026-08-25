"""Testes dos modelos de leitura do domínio Abrangência."""

from django.db import models
from django.test import TestCase

from apps.abrangencia.models import (
    AbrangenciaCompacta,
    ArrayDeTexto,
    Perfil,
    PerfilVinculoFuncional,
    UsuarioAbrangencia,
)


class TestModelosNaoGerenciados(TestCase):
    """Garante que os models refletem o schema, sem gerar migration."""

    def test_perfil_nao_e_gerenciado(self) -> None:
        """`Perfil` não pertence a este serviço (schema do sme-airflow)."""
        self.assertFalse(Perfil._meta.managed)
        self.assertEqual(Perfil._meta.db_table, "perfil")

    def test_perfil_vinculo_funcional_nao_e_gerenciado(self) -> None:
        """`PerfilVinculoFuncional` também é somente leitura."""
        self.assertFalse(PerfilVinculoFuncional._meta.managed)
        self.assertEqual(
            PerfilVinculoFuncional._meta.db_table,
            "perfil_vinculo_funcional",
        )

    def test_usuario_abrangencia_nao_e_gerenciado(self) -> None:
        """`UsuarioAbrangencia` também é somente leitura."""
        self.assertFalse(UsuarioAbrangencia._meta.managed)
        self.assertEqual(
            UsuarioAbrangencia._meta.db_table, "usuario_abrangencia"
        )

    def test_abrangencia_compacta_nao_e_gerenciada(self) -> None:
        """`AbrangenciaCompacta` lê a materialized view, não uma tabela."""
        self.assertFalse(AbrangenciaCompacta._meta.managed)
        self.assertEqual(
            AbrangenciaCompacta._meta.db_table, "mv_abrangencia_compacta"
        )


class TestArrayDeTexto(TestCase):
    """Testes de `ArrayDeTexto` fora do PostgreSQL (suíte roda em SQLite)."""

    def setUp(self) -> None:
        """Cria o campo isolado do model, para testar a conversão."""
        self.campo = ArrayDeTexto(models.TextField())

    def test_db_type_fora_do_postgres_e_text(self) -> None:
        """Sem tipo array nativo, a coluna vira `text`."""
        self.assertEqual(self.campo.db_type(connection=None), "text")

    def test_from_db_value_decodifica_json(self) -> None:
        """Lista serializada em JSON volta como lista de strings."""
        resultado = self.campo.from_db_value(
            '["019331", "094811"]', connection=None
        )

        self.assertEqual(resultado, ["019331", "094811"])

    def test_from_db_value_none_permanece_none(self) -> None:
        """Valor nulo permanece `None`, não vira lista vazia."""
        self.assertIsNone(self.campo.from_db_value(None, connection=None))

    def test_from_db_value_lista_ja_pronta_e_preservada(self) -> None:
        """Uma lista já materializada não é reprocessada."""
        entrada = ["019331"]

        self.assertIs(
            self.campo.from_db_value(entrada, connection=None), entrada
        )

    def test_get_db_prep_value_serializa_lista_em_json(self) -> None:
        """Lista vira texto JSON antes de ser gravada fora do Postgres."""
        resultado = self.campo.get_db_prep_value(
            ["019331", "094811"], connection=None
        )

        self.assertEqual(resultado, '["019331", "094811"]')

    def test_get_db_prep_value_none_permanece_none(self) -> None:
        """Valor nulo não é serializado."""
        self.assertIsNone(self.campo.get_db_prep_value(None, connection=None))
