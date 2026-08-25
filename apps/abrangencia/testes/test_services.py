"""Testes do serviço do domínio Abrangência."""

from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.abrangencia.constants import PERFIS_POA, TipoAbrangencia
from apps.abrangencia.services import AbrangenciaService

_PERFIL_GUID = "108d0f8a-0000-0000-0000-000000000001"
_PERFIL_POA = next(iter(PERFIS_POA))


@override_settings(ABRANGENCIA_ANO_LETIVO=2026)
class TestProjetarEscopo(TestCase):
    """Testes de `AbrangenciaService.projetar_escopo`."""

    def setUp(self) -> None:
        """Instancia o serviço e um conjunto de escopo bruto de exemplo."""
        self.service = AbrangenciaService()
        self.id_dres = ["108100"]
        self.id_ues = ["019331"]
        self.id_turmas = ["1234"]

    def test_ramo_ue_preenche_apenas_ues(self) -> None:
        """`TipoAbrangencia.UE` preenche só `idUes`."""
        escopo = self.service.projetar_escopo(
            TipoAbrangencia.UE,
            _PERFIL_GUID,
            self.id_dres,
            self.id_ues,
            self.id_turmas,
        )

        self.assertIsNone(escopo["idDres"])
        self.assertEqual(escopo["idUes"], self.id_ues)
        self.assertIsNone(escopo["idTurmas"])

    def test_ramo_professor_preenche_turmas_com_lista_vazia_default(
        self,
    ) -> None:
        """`PROFESSOR` monta `AbrangenciaCompactaVigente`: default é `[]`."""
        escopo = self.service.projetar_escopo(
            TipoAbrangencia.PROFESSOR,
            _PERFIL_GUID,
            self.id_dres,
            self.id_ues,
            self.id_turmas,
        )

        self.assertEqual(escopo["idDres"], [])
        self.assertEqual(escopo["idUes"], [])
        self.assertEqual(escopo["idTurmas"], self.id_turmas)

    def test_ramo_dre_preenche_apenas_dres(self) -> None:
        """`DRE` preenche só `idDres`."""
        escopo = self.service.projetar_escopo(
            TipoAbrangencia.DRE,
            _PERFIL_GUID,
            self.id_dres,
            self.id_ues,
            self.id_turmas,
        )

        self.assertEqual(escopo["idDres"], self.id_dres)
        self.assertIsNone(escopo["idUes"])
        self.assertIsNone(escopo["idTurmas"])

    def test_ramo_sme_preenche_os_tres_niveis(self) -> None:
        """`SME` é o único ramo que preenche os três níveis."""
        escopo = self.service.projetar_escopo(
            TipoAbrangencia.SME,
            _PERFIL_GUID,
            self.id_dres,
            self.id_ues,
            self.id_turmas,
        )

        self.assertEqual(escopo["idDres"], self.id_dres)
        self.assertEqual(escopo["idUes"], self.id_ues)
        self.assertEqual(escopo["idTurmas"], self.id_turmas)

    def test_ramo_sem_case_cai_no_default(self) -> None:
        """`DRE_ESCOLAS_ATRIBUIDAS` não tem `case`: zera tudo com `None`."""
        escopo = self.service.projetar_escopo(
            TipoAbrangencia.DRE_ESCOLAS_ATRIBUIDAS,
            _PERFIL_GUID,
            self.id_dres,
            self.id_ues,
            self.id_turmas,
        )

        self.assertIsNone(escopo["idDres"])
        self.assertIsNone(escopo["idUes"])
        self.assertIsNone(escopo["idTurmas"])

    def test_tipo_abrangencia_none_cai_no_default(self) -> None:
        """Perfil inexistente (`None`) também cai no default."""
        escopo = self.service.projetar_escopo(
            None,
            _PERFIL_GUID,
            self.id_dres,
            self.id_ues,
            self.id_turmas,
        )

        self.assertIsNone(escopo["idDres"])
        self.assertIsNone(escopo["idUes"])
        self.assertIsNone(escopo["idTurmas"])

    def test_algoritmo_alternativo_ue_turmas_disciplinas_resolve_turma(
        self,
    ) -> None:
        """No algoritmo alternativo, `UE_TURMAS_DISCIPLINAS` resolve turma."""
        escopo = self.service.projetar_escopo(
            TipoAbrangencia.UE_TURMAS_DISCIPLINAS,
            _PERFIL_GUID,
            self.id_dres,
            self.id_ues,
            self.id_turmas,
            algoritmo_alternativo=True,
        )

        self.assertIsNone(escopo["idUes"])
        self.assertEqual(escopo["idTurmas"], self.id_turmas)

    def test_perfil_poa_no_ramo_ue_usa_turmas_poa(self) -> None:
        """Perfil POA no ramo UE preenche `idTurmas` pela origem POA."""
        escopo = self.service.projetar_escopo(
            TipoAbrangencia.UE,
            _PERFIL_POA,
            self.id_dres,
            self.id_ues,
            self.id_turmas,
            id_turmas_poa=["5555"],
        )

        self.assertEqual(escopo["idTurmas"], ["5555"])

    def test_perfil_poa_no_algoritmo_alternativo_nao_usa_turmas_poa(
        self,
    ) -> None:
        """A exceção POA só vale para o algoritmo padrão."""
        escopo = self.service.projetar_escopo(
            TipoAbrangencia.UE,
            _PERFIL_POA,
            self.id_dres,
            self.id_ues,
            self.id_turmas,
            id_turmas_poa=["5555"],
            algoritmo_alternativo=True,
        )

        self.assertIsNone(escopo["idTurmas"])


@override_settings(ABRANGENCIA_ANO_LETIVO=2026)
class TestAbrangenciaCompacta(TestCase):
    """Testes de `AbrangenciaService.abrangencia_compacta`."""

    def test_usuario_sem_escopo_usa_tipo_do_perfil(self) -> None:
        """Sem linha na MV, a forma da resposta vem do ramo do perfil."""
        service = AbrangenciaService()
        with (
            patch.object(service, "_escopo_compacto", return_value=None),
            patch.object(
                service,
                "_tipo_abrangencia_do_perfil",
                return_value=int(TipoAbrangencia.SME),
            ),
            patch.object(service, "_perfil_com_vinculos", return_value=None),
        ):
            payload = service.abrangencia_compacta("999999", _PERFIL_GUID)

        self.assertEqual(payload["idDres"], [])
        self.assertEqual(payload["idUes"], [])
        self.assertEqual(payload["idTurmas"], [])
        self.assertIsNone(payload["dres"])
        self.assertIsNone(payload["ues"])
        self.assertIsNone(payload["turmas"])

    def test_expandir_ues_usa_ues_detalhaveis(self) -> None:
        """`ues` expandida vem de `id_ues_detalhaveis`, não do projetado."""
        service = AbrangenciaService()
        linha = {
            "id_dres": ["108100"],
            "id_ues": ["019331"],
            "id_turmas": [],
            "tipo_abrangencia": int(TipoAbrangencia.UE),
            "id_ues_exercicio": [],
            "id_turmas_poa": [],
            "id_ues_alternativo": [],
            "id_turmas_alternativo": [],
            "grupo_codigo": 10,
            "id_ues_readaptado": [],
            "id_ues_detalhaveis": ["019331", "094811"],
        }
        with (
            patch.object(service, "_escopo_compacto", return_value=linha),
            patch.object(service, "_perfil_com_vinculos", return_value=None),
        ):
            payload = service.abrangencia_compacta(
                "5059151", _PERFIL_GUID, expandir_ues=True
            )

        assert payload["ues"] is not None
        codigos = [item["codigo"] for item in payload["ues"]]
        self.assertEqual(codigos, ["019331", "094811"])
        # Ramo UE zera idDres, mas a expansão de ues não depende do ramo.
        self.assertIsNone(payload["idDres"])

    def test_expandir_turmas_sem_turma_elegivel_retorna_none(self) -> None:
        """Sem turma de sondagem, `turmas` sai `None`, não `[]`."""
        service = AbrangenciaService()
        with (
            patch.object(service, "_escopo_compacto", return_value=None),
            patch.object(
                service,
                "_tipo_abrangencia_do_perfil",
                return_value=int(TipoAbrangencia.PROFESSOR),
            ),
            patch.object(service, "_turmas_sondagem", return_value=[]),
            patch.object(service, "_perfil_com_vinculos", return_value=None),
        ):
            payload = service.abrangencia_compacta(
                "5059151", _PERFIL_GUID, expandir_turmas=True
            )

        self.assertIsNone(payload["turmas"])


class TestUsuariosPorPerfilService(TestCase):
    """Testes de `AbrangenciaService.usuarios_por_perfil`."""

    def test_agrupa_por_usuario_preservando_a_grafia_perfils(self) -> None:
        """A chave de saída é `perfils`, agrupando por usuário."""
        service = AbrangenciaService()
        registros = [
            {
                "usuario_rf": "5059151",
                "perfil_guid": _PERFIL_GUID,
                "ues": ["019331"],
            }
        ]
        with patch.object(
            service, "_usuarios_por_perfil", return_value=registros
        ):
            resultado = service.usuarios_por_perfil(
                "019331", None, [_PERFIL_GUID]
            )

        self.assertEqual(
            resultado,
            [
                {
                    "usuarioRf": "5059151",
                    "perfils": [{"perfil": _PERFIL_GUID, "ues": ["019331"]}],
                }
            ],
        )
