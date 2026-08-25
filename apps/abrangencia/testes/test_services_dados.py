"""Testes dos métodos de acesso a dado de `AbrangenciaService`."""

from django.test import TestCase

from apps.abrangencia.models import (
    AbrangenciaCompacta,
    Perfil,
    PerfilVinculoFuncional,
    UsuarioAbrangencia,
)
from apps.abrangencia.services import AbrangenciaService

_PERFIL_GUID = "2e89cf10-e42b-476f-8673-2dfbeeee3cd0"
_OUTRO_PERFIL_GUID = "57a7b9ab-8e61-4093-b692-a0bb1f9f46bd"


class TestPerfilComVinculos(TestCase):
    """Testes de `AbrangenciaService._perfil_com_vinculos`."""

    def setUp(self) -> None:
        """Cria um perfil com um cargo e uma função-atividade."""
        self.service = AbrangenciaService()
        Perfil.objects.create(
            perfil_guid=_PERFIL_GUID,
            grupo_codigo=10,
            tipo_abrangencia=1,
            eh_perfil_manual=False,
        )
        PerfilVinculoFuncional.objects.create(
            perfil_guid=_PERFIL_GUID, tipo="CARGO", codigo=100
        )
        PerfilVinculoFuncional.objects.create(
            perfil_guid=_PERFIL_GUID, tipo="FUNCAO_ATIVIDADE", codigo=200
        )

    def test_retorna_perfil_com_cargos_e_funcoes_ordenados(self) -> None:
        """Cargos e funções voltam ordenados, agrupados por tipo."""
        resultado = self.service._perfil_com_vinculos(_PERFIL_GUID)

        assert resultado is not None
        self.assertEqual(resultado["cargos"], [100])
        self.assertEqual(resultado["funcoes"], [200])
        self.assertEqual(resultado["grupo_codigo"], 10)

    def test_perfil_sem_vinculo_retorna_listas_vazias(self) -> None:
        """Perfil existente sem vínculo funcional não é erro."""
        Perfil.objects.create(
            perfil_guid=_OUTRO_PERFIL_GUID,
            grupo_codigo=20,
            tipo_abrangencia=4,
            eh_perfil_manual=True,
        )

        resultado = self.service._perfil_com_vinculos(_OUTRO_PERFIL_GUID)

        assert resultado is not None
        self.assertEqual(resultado["cargos"], [])
        self.assertEqual(resultado["funcoes"], [])

    def test_perfil_inexistente_retorna_none(self) -> None:
        """GUID sem registro na tabela `perfil` retorna `None`."""
        self.assertIsNone(
            self.service._perfil_com_vinculos(
                "00000000-0000-0000-0000-000000000001"
            )
        )


class TestEscopoCompacto(TestCase):
    """Testes de `AbrangenciaService._escopo_compacto`."""

    def setUp(self) -> None:
        """Cria uma linha na MV de escopo compacto."""
        self.service = AbrangenciaService()
        AbrangenciaCompacta.objects.create(
            login="5059151",
            perfil_guid=_PERFIL_GUID,
            ano_letivo=2026,
            grupo_codigo=10,
            tipo_abrangencia=1,
            eh_perfil_manual=False,
            id_dres=["108100"],
            id_ues=["019331"],
            id_turmas=[],
            id_ues_exercicio=[],
            id_turmas_poa=[],
            id_ues_alternativo=[],
            id_turmas_alternativo=[],
            id_ues_readaptado=[],
            id_ues_detalhaveis=["019331"],
        )

    def test_retorna_escopo_normalizado(self) -> None:
        """Colunas `id_*` nulas viram lista vazia, nunca `None`."""
        resultado = self.service._escopo_compacto(
            "5059151", _PERFIL_GUID, 2026
        )

        assert resultado is not None
        self.assertEqual(resultado["id_dres"], ["108100"])
        self.assertEqual(resultado["id_ues"], ["019331"])
        self.assertEqual(resultado["id_turmas"], [])

    def test_usuario_sem_linha_retorna_none(self) -> None:
        """Trio `(login, perfil, ano)` sem linha na MV retorna `None`."""
        self.assertIsNone(
            self.service._escopo_compacto("999999", _PERFIL_GUID, 2026)
        )

    def test_ano_letivo_diferente_nao_encontra_linha(self) -> None:
        """O filtro usa as três colunas do índice único da MV."""
        self.assertIsNone(
            self.service._escopo_compacto("5059151", _PERFIL_GUID, 2020)
        )


class TestTipoAbrangenciaDoPerfil(TestCase):
    """Testes de `AbrangenciaService._tipo_abrangencia_do_perfil`."""

    def test_retorna_o_ramo_do_perfil(self) -> None:
        """Retorna o `tipo_abrangencia` de um perfil existente."""
        Perfil.objects.create(
            perfil_guid=_PERFIL_GUID,
            grupo_codigo=10,
            tipo_abrangencia=6,
            eh_perfil_manual=False,
        )
        service = AbrangenciaService()

        self.assertEqual(service._tipo_abrangencia_do_perfil(_PERFIL_GUID), 6)

    def test_perfil_inexistente_retorna_none(self) -> None:
        """Perfil sem registro retorna `None`, não levanta erro."""
        service = AbrangenciaService()

        self.assertIsNone(
            service._tipo_abrangencia_do_perfil(
                "00000000-0000-0000-0000-000000000001"
            )
        )


class TestTurmasSondagem(TestCase):
    """Testes de `AbrangenciaService._turmas_sondagem`."""

    def _criar_usuario_abrangencia(self, **overrides: object) -> None:
        base = {
            "login": "5059151",
            "perfil_guid": _PERFIL_GUID,
            "ano_letivo": 2026,
            "origem": "ATRIBUICAO_AULA",
            "nivel_abrangencia": "TURMA",
            "turma_codigo": "1234",
            "ue_codigo": "019331",
            "vigente": True,
            "elegivel_sondagem": True,
        }
        base.update(overrides)
        UsuarioAbrangencia.objects.create(**base)

    def test_retorna_apenas_turmas_elegiveis_e_vigentes(self) -> None:
        """Turma não elegível a sondagem não aparece na lista."""
        self._criar_usuario_abrangencia()
        self._criar_usuario_abrangencia(
            turma_codigo="9999", elegivel_sondagem=False
        )
        self._criar_usuario_abrangencia(turma_codigo="8888", vigente=False)
        service = AbrangenciaService()

        resultado = service._turmas_sondagem("5059151", _PERFIL_GUID, 2026)

        self.assertEqual(
            resultado, [{"turma_codigo": "1234", "ue_codigo": "019331"}]
        )

    def test_sem_turma_elegivel_retorna_lista_vazia(self) -> None:
        """Usuário sem turma elegível não é erro, retorna `[]`."""
        service = AbrangenciaService()

        self.assertEqual(
            service._turmas_sondagem("5059151", _PERFIL_GUID, 2026), []
        )


class TestUsuariosPorPerfil(TestCase):
    """Testes de `AbrangenciaService._usuarios_por_perfil`."""

    def _criar_usuario_abrangencia(self, **overrides: object) -> None:
        base = {
            "login": "5059151",
            "perfil_guid": _PERFIL_GUID,
            "ano_letivo": 2026,
            "origem": "LOTACAO_CARGO",
            "nivel_abrangencia": "UE",
            "ue_codigo": "019331",
            "dre_codigo": "108100",
            "vigente": True,
        }
        base.update(overrides)
        UsuarioAbrangencia.objects.create(**base)

    def test_agrupa_ues_por_login_e_perfil(self) -> None:
        """Um único registro por par `(login, perfil)`, UEs ordenadas."""
        self._criar_usuario_abrangencia()
        self._criar_usuario_abrangencia(ue_codigo="094811")
        service = AbrangenciaService()

        resultado = service._usuarios_por_perfil(
            "019331", None, [_PERFIL_GUID]
        )

        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["usuario_rf"], "5059151")
        self.assertEqual(resultado[0]["ues"], ["019331"])

    def test_filtra_por_dre_quando_informada(self) -> None:
        """DRE diferente da informada exclui o registro."""
        self._criar_usuario_abrangencia(dre_codigo="999999")
        service = AbrangenciaService()

        resultado = service._usuarios_por_perfil(
            "019331", "108100", [_PERFIL_GUID]
        )

        self.assertEqual(resultado, [])

    def test_origem_fora_da_lista_de_lotacao_e_ignorada(self) -> None:
        """Só origens de lotação alimentam o índice."""
        self._criar_usuario_abrangencia(origem="ATRIBUICAO_AULA")
        service = AbrangenciaService()

        resultado = service._usuarios_por_perfil(
            "019331", None, [_PERFIL_GUID]
        )

        self.assertEqual(resultado, [])
