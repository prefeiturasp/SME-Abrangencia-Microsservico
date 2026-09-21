"""Testes dos modelos de leitura do domínio Abrangência."""

from django.test import TestCase

from apps.abrangencia.models import (
    AbrangenciaResolvida,
    Perfil,
    PerfilVinculoFuncional,
    Unidade,
    UsuarioPorPerfil,
)

_PERFIL_GUID = "2e89cf10-e42b-476f-8673-2dfbeeee3cd0"


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

    def test_abrangencia_resolvida_le_a_mv_de_escopo(self) -> None:
        """`AbrangenciaResolvida` lê a MV."""
        self.assertFalse(AbrangenciaResolvida._meta.managed)
        self.assertEqual(
            AbrangenciaResolvida._meta.db_table, "mv_abrangencia_resolvida"
        )

    def test_unidade_le_a_mv_de_unidade(self) -> None:
        """`Unidade` lê `mv_abrangencia_unidade`, não a tabela de origem."""
        self.assertFalse(Unidade._meta.managed)
        self.assertEqual(Unidade._meta.db_table, "mv_abrangencia_unidade")

    def test_usuario_por_perfil_le_a_mv_de_usuarios(self) -> None:
        """`UsuarioPorPerfil` lê a MV."""
        self.assertFalse(UsuarioPorPerfil._meta.managed)
        self.assertEqual(
            UsuarioPorPerfil._meta.db_table, "mv_abrangencia_usuarios_perfil"
        )


class TestRepresentacaoDosModelos(TestCase):
    """Testes de `__str__` dos models."""

    def test_perfil(self) -> None:
        """Perfil exibe GUID e nome."""
        perfil = Perfil(perfil_guid=_PERFIL_GUID, nome="CP")

        self.assertEqual(str(perfil), f"{_PERFIL_GUID} - CP")

    def test_perfil_vinculo_funcional(self) -> None:
        """Vínculo exibe perfil, tipo e código."""
        vinculo = PerfilVinculoFuncional(
            perfil_guid=_PERFIL_GUID, tipo="CARGO", codigo=1
        )

        self.assertEqual(str(vinculo), f"{_PERFIL_GUID} - CARGO - 1")

    def test_abrangencia_resolvida(self) -> None:
        """Escopo exibe login, perfil e resolução."""
        escopo = AbrangenciaResolvida(
            login="5059151",
            perfil_guid=_PERFIL_GUID,
            tipo_resolucao="COMPACTA",
            tipo_escopo="UE",
        )

        self.assertEqual(
            str(escopo), f"5059151 - {_PERFIL_GUID} - COMPACTA/UE"
        )

    def test_unidade(self) -> None:
        """Unidade exibe ano, tipo e código."""
        unidade = Unidade(ano_letivo=2026, tipo_escopo="UE", codigo="019331")

        self.assertEqual(str(unidade), "2026 - UE - 019331")

    def test_usuario_por_perfil(self) -> None:
        """Usuário por perfil exibe usuário, perfil e UE."""
        usuario = UsuarioPorPerfil(
            usuario_rf="5059151",
            perfil_guid=_PERFIL_GUID,
            ue_codigo="019331",
        )

        self.assertEqual(str(usuario), f"5059151 - {_PERFIL_GUID} - 019331")
