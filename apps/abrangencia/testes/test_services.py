"""Testes do servico do dominio Abrangencia."""

from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.abrangencia.constants import TipoAbrangencia
from apps.abrangencia.models import (
    AbrangenciaResolvida,
    Perfil,
    UsuarioPorPerfil,
)
from apps.abrangencia.services import AbrangenciaService
from apps.abrangencia.testes.helpers import criar_escopo, usar_rede_sme

_PERFIL_GUID = "2e89cf10-e42b-476f-8673-2dfbeeee3cd0"
_LOGIN = "9999001"
_ANO = 2026


def criar_perfil(
    tipo_abrangencia: int,
    grupo_codigo: int = 10,
    *,
    eh_perfil_manual: bool = False,
) -> None:
    """Cria o perfil consultado, com o tipo de abrangencia informado."""
    Perfil.objects.create(
        perfil_guid=_PERFIL_GUID,
        grupo_codigo=grupo_codigo,
        abrangencia_id=tipo_abrangencia,
        eh_perfil_manual=eh_perfil_manual,
    )


@override_settings(ABRANGENCIA_ANO_LETIVO=_ANO)
class TestNivelVazio(TestCase):
    """Testes de `AbrangenciaService._aplicar_nivel_vazio`."""

    def setUp(self) -> None:
        """Instancia o servico."""
        self.service = AbrangenciaService()

    def test_compacta_zera_niveis_por_tipo_abrangencia(self) -> None:
        """Trava quais niveis saem `[]` em cada tipo de abrangencia."""
        esperado = {
            TipoAbrangencia.PROFESSOR: {"idDres", "idUes", "idTurmas"},
            TipoAbrangencia.SME: {"idDres", "idUes", "idTurmas"},
            TipoAbrangencia.UE: {"idUes"},
            TipoAbrangencia.UE_TURMAS_DISCIPLINAS: {"idUes"},
            TipoAbrangencia.DRE: set(),
            TipoAbrangencia.DRE_ESCOLAS_ATRIBUIDAS: set(),
        }

        for tipo, niveis_vazios in esperado.items():
            with self.subTest(tipo_abrangencia=tipo.name):
                escopo = self.service._aplicar_nivel_vazio(
                    {"idDres": [], "idUes": [], "idTurmas": []},
                    int(tipo),
                    algoritmo_alternativo=False,
                    escopo_de_contrato_externo=True,
                    eh_perfil_manual=True,
                )

                for chave, valor in escopo.items():
                    if chave in niveis_vazios:
                        self.assertEqual(valor, [], f"{tipo.name}.{chave}")
                    else:
                        self.assertIsNone(valor, f"{tipo.name}.{chave}")

    def test_compacta_turma_do_poa_depende_da_origem_do_escopo(self) -> None:
        """Garante que `idTurmas` do POA distingue a origem do escopo."""
        por_lotacao = self.service._aplicar_nivel_vazio(
            {"idDres": [], "idUes": [], "idTurmas": []},
            int(TipoAbrangencia.UE_TURMAS_DISCIPLINAS),
            algoritmo_alternativo=False,
            escopo_de_contrato_externo=False,
        )
        por_contrato = self.service._aplicar_nivel_vazio(
            {"idDres": [], "idUes": [], "idTurmas": []},
            int(TipoAbrangencia.UE_TURMAS_DISCIPLINAS),
            algoritmo_alternativo=False,
            escopo_de_contrato_externo=True,
        )

        self.assertEqual(por_lotacao["idTurmas"], [])
        self.assertIsNone(por_contrato["idTurmas"])
        self.assertEqual(por_lotacao["idUes"], [])
        self.assertEqual(por_contrato["idUes"], [])

    def test_tipo_abrangencia_dre_decide_vazio_pelo_flag_manual(self) -> None:
        """Abrangencia Dre nao manual devolve `[]`."""
        manual = self.service._aplicar_nivel_vazio(
            {"idDres": [], "idUes": [], "idTurmas": []},
            int(TipoAbrangencia.DRE),
            algoritmo_alternativo=False,
            eh_perfil_manual=True,
        )
        nao_manual = self.service._aplicar_nivel_vazio(
            {"idDres": [], "idUes": [], "idTurmas": []},
            int(TipoAbrangencia.DRE),
            algoritmo_alternativo=False,
            eh_perfil_manual=False,
        )

        self.assertIsNone(manual["idDres"])
        self.assertEqual(nao_manual["idDres"], [])
        for escopo in (manual, nao_manual):
            self.assertIsNone(escopo["idUes"])
            self.assertIsNone(escopo["idTurmas"])

    def test_tipo_abrangencia_dre_nao_manual_em_detalhes(self) -> None:
        """Garante que o flag manual nao afeta o modo detalhado."""
        escopo = self.service._aplicar_nivel_vazio(
            {"idDres": [], "idUes": [], "idTurmas": []},
            int(TipoAbrangencia.DRE),
            algoritmo_alternativo=True,
            eh_perfil_manual=False,
        )

        self.assertEqual(escopo["idDres"], [])
        self.assertIsNone(escopo["idUes"])
        self.assertIsNone(escopo["idTurmas"])

    def test_nivel_com_codigo_nao_e_afetado_pela_regra(self) -> None:
        """Nivel com codigo sai como esta."""
        escopo = self.service._aplicar_nivel_vazio(
            {"idDres": [], "idUes": ["019331"], "idTurmas": []},
            int(TipoAbrangencia.UE),
            algoritmo_alternativo=False,
        )

        self.assertEqual(escopo["idUes"], ["019331"])
        self.assertIsNone(escopo["idDres"])
        self.assertIsNone(escopo["idTurmas"])

    def test_detalhes_zera_nivel_por_tipo_abrangencia(self) -> None:
        """Trava quais niveis saem `[]` em `DETALHES`."""
        esperado = {
            TipoAbrangencia.PROFESSOR: {"idTurmas"},
            TipoAbrangencia.SME: {"idDres"},
            TipoAbrangencia.UE: {"idUes"},
            TipoAbrangencia.UE_TURMAS_DISCIPLINAS: {"idTurmas"},
            TipoAbrangencia.DRE: {"idDres"},
            TipoAbrangencia.DRE_ESCOLAS_ATRIBUIDAS: {"idUes"},
        }

        for tipo, niveis_vazios in esperado.items():
            with self.subTest(tipo_abrangencia=tipo.name):
                escopo = self.service._aplicar_nivel_vazio(
                    {"idDres": [], "idUes": [], "idTurmas": []},
                    int(tipo),
                    algoritmo_alternativo=True,
                )

                for chave, valor in escopo.items():
                    if chave in niveis_vazios:
                        self.assertEqual(valor, [], f"{tipo.name}.{chave}")
                    else:
                        self.assertIsNone(valor, f"{tipo.name}.{chave}")

    def test_detalhes_descarta_nivel_nao_atribuido(self) -> None:
        """Garante `idUes: null` em `DETALHES`."""
        escopo = self.service._aplicar_nivel_vazio(
            {"idDres": [], "idUes": ["019274"], "idTurmas": ["9999101"]},
            int(TipoAbrangencia.UE_TURMAS_DISCIPLINAS),
            algoritmo_alternativo=True,
        )

        self.assertIsNone(escopo["idUes"])
        self.assertEqual(escopo["idTurmas"], ["9999101"])
        self.assertIsNone(escopo["idDres"])

    def test_compacta_mantem_nivel_atribuido(self) -> None:
        """Garante que o fluxo compacto preserva nivel com codigo."""
        escopo = self.service._aplicar_nivel_vazio(
            {"idDres": [], "idUes": ["019274"], "idTurmas": ["9999101"]},
            int(TipoAbrangencia.UE_TURMAS_DISCIPLINAS),
            algoritmo_alternativo=False,
        )

        self.assertEqual(escopo["idUes"], ["019274"])
        self.assertEqual(escopo["idTurmas"], ["9999101"])

    def test_perfil_inexistente_devolve_none(self) -> None:
        """Perfil inexistente nao zera nivel algum, nos dois algoritmos."""
        for algoritmo_alternativo in (False, True):
            with self.subTest(algoritmo_alternativo=algoritmo_alternativo):
                escopo = self.service._aplicar_nivel_vazio(
                    {"idDres": [], "idUes": [], "idTurmas": []},
                    None,
                    algoritmo_alternativo=algoritmo_alternativo,
                )

                self.assertIsNone(escopo["idDres"])
                self.assertIsNone(escopo["idUes"])
                self.assertIsNone(escopo["idTurmas"])


@override_settings(ABRANGENCIA_ANO_LETIVO=_ANO)
class TestEscopoPorAlgoritmo(TestCase):
    """Garante que cada endpoint le o `tipo_resolucao` que lhe cabe."""

    def setUp(self) -> None:
        """Cria escopos distintos para os dois algoritmos."""
        usar_rede_sme(self)
        self.service = AbrangenciaService()
        criar_perfil(int(TipoAbrangencia.UE))
        criar_escopo(tipo_resolucao="COMPACTA", ue_codigo="019331")
        criar_escopo(tipo_resolucao="DETALHES", ue_codigo="094811")

    def test_fluxo_compacto_le_somente_as_linhas_compactas(self) -> None:
        """Monta o escopo compacto."""
        payload = self.service.abrangencia_compacta(_LOGIN, _PERFIL_GUID)

        self.assertEqual(payload["idUes"], ["019331"])

    def test_fluxos_detalhados_leem_linhas_de_detalhes(self) -> None:
        """Monta o escopo detalhado."""
        payload = self.service.abrangencia_compacta(
            _LOGIN, _PERFIL_GUID, algoritmo_alternativo=True
        )

        self.assertEqual(payload["idUes"], ["094811"])


@override_settings(ABRANGENCIA_ANO_LETIVO=_ANO)
class TestNivelPeloCodigo(TestCase):
    """Testes do nivel de cada linha, sem `tipo_escopo`."""

    def setUp(self) -> None:
        """Instancia o servico."""
        usar_rede_sme(self)
        self.service = AbrangenciaService()

    def test_codigo_mais_fino_preenchido_decide_o_nivel(self) -> None:
        """Garante turma antes de UE, e UE antes de DRE."""
        criar_escopo(turma_codigo="9999101", ue_codigo="900101")
        criar_escopo(ue_codigo="900102", dre_codigo="900100")
        criar_escopo(dre_codigo="900200")

        escopo = self.service._escopo_resolvido(
            _LOGIN, _PERFIL_GUID, _ANO, "COMPACTA"
        )

        self.assertEqual(
            escopo,
            {
                "idDres": ["900200"],
                "idUes": ["900102"],
                "idTurmas": ["9999101"],
            },
        )

    def test_linha_sem_codigo_da_origem_de_exercicio_e_ue_nula(self) -> None:
        """Garante `idUes: [null]` so nas origens de exercicio."""
        for origem, esperado in (
            ("LOTACAO_EXERCICIO", [None]),
            ("LOTACAO_CARGO", []),
        ):
            with self.subTest(origem=origem):
                AbrangenciaResolvida.objects.all().delete()
                criar_escopo(origem=origem)

                escopo = self.service._escopo_resolvido(
                    _LOGIN, _PERFIL_GUID, _ANO, "COMPACTA"
                )

                self.assertEqual(escopo["idUes"], esperado)
                self.assertEqual(escopo["idDres"], [])
                self.assertEqual(escopo["idTurmas"], [])


@override_settings(ABRANGENCIA_ANO_LETIVO=_ANO)
class TestAbrangenciaCompacta(TestCase):
    """Testes de `AbrangenciaService.abrangencia_compacta`."""

    def setUp(self) -> None:
        """Instancia o servico com uma rede vazia."""
        self.rede_sme = usar_rede_sme(self)
        self.service = AbrangenciaService()

    def test_perfil_sem_escopo_respeita_tipo_abrangencia(self) -> None:
        """Perfil existente sem linha de escopo nao e erro."""
        criar_perfil(int(TipoAbrangencia.SME))

        payload = self.service.abrangencia_compacta("999999", _PERFIL_GUID)

        self.assertEqual(payload["idDres"], [])
        self.assertEqual(payload["idUes"], [])
        self.assertEqual(payload["idTurmas"], [])
        self.assertIsNotNone(payload["abrangencia"])

    def test_tipo_abrangencia_sme_recebe_as_dres_da_rede(self) -> None:
        """Garante que o SME recebe as DREs de `codigos-dres`."""
        criar_perfil(int(TipoAbrangencia.SME))
        self.rede_sme.com_dre("900100").com_dre("900300")

        compacta = self.service.abrangencia_compacta(_LOGIN, _PERFIL_GUID)
        alternativo = self.service.abrangencia_compacta(
            _LOGIN, _PERFIL_GUID, algoritmo_alternativo=True
        )

        self.assertEqual(compacta["idDres"], ["900100", "900300"])
        self.assertEqual(alternativo["idDres"], ["900100", "900300"])

    def test_sme_le_so_os_codigos_dres_nos_dois_algoritmos(self) -> None:
        """Garante `idDres` do SME de `codigos-dres`, sem montar a rede.

        No legado, a rota de codigos das DREs e o `idDres` do SME usam o
        mesmo metodo; montar a rede so para isso custaria cerca de 200
        chamadas e responderia 503 por falha que nao afeta o SME.
        """
        criar_perfil(int(TipoAbrangencia.SME))

        for algoritmo_alternativo in (False, True):
            with (
                self.subTest(algoritmo_alternativo=algoritmo_alternativo),
                patch.object(
                    self.rede_sme, "codigos_dres", return_value=["900100"]
                ) as codigos,
                patch.object(self.rede_sme, "ues") as ues,
            ):
                payload = self.service.abrangencia_compacta(
                    _LOGIN,
                    _PERFIL_GUID,
                    algoritmo_alternativo=algoritmo_alternativo,
                )

                codigos.assert_called_once_with()
                ues.assert_not_called()
                self.assertEqual(payload["idDres"], ["900100"])

    def test_tipo_abrangencia_sme_com_linha_preserva_escopo(self) -> None:
        """MV tem precedencia sobre a rede no tipo SME."""
        criar_perfil(int(TipoAbrangencia.SME))
        self.rede_sme.com_dre("108100").com_dre("108200")
        criar_escopo(dre_codigo="108100")

        payload = self.service.abrangencia_compacta(_LOGIN, _PERFIL_GUID)

        self.assertEqual(payload["idDres"], ["108100"])

    def test_tipo_abrangencia_dre_expande_ues_por_id_dres(self) -> None:
        """Tipo de abrangencia DRE expande UEs pelo dre_codigo."""
        criar_perfil(int(TipoAbrangencia.DRE))
        criar_escopo(dre_codigo="108100")
        self.rede_sme.com_ue("019331", dre="108100")
        self.rede_sme.com_ue("094811", dre="108200")

        payload = self.service.abrangencia_compacta(
            _LOGIN, _PERFIL_GUID, expandir_ues=True
        )

        self.assertEqual([ue["codigo"] for ue in payload["ues"]], ["019331"])

    def test_perfil_inexistente_mantem_abrangencia_vazio(self) -> None:
        """Perfil inexistente monta payload sem tipo de abrangencia."""
        payload = self.service.abrangencia_compacta(_LOGIN, _PERFIL_GUID)

        self.assertIsNone(payload["abrangencia"])
        self.assertIsNone(payload["idDres"])
        self.assertIsNone(payload["idUes"])
        self.assertIsNone(payload["idTurmas"])

    def test_compacta_ue_sem_escopo_devolve_ues_vazia(self) -> None:
        """Garante `idUes: []` e outros niveis `null`."""
        criar_perfil(int(TipoAbrangencia.UE), grupo_codigo=12)

        payload = self.service.abrangencia_compacta(_LOGIN, _PERFIL_GUID)

        self.assertEqual(payload["idUes"], [])
        self.assertIsNone(payload["idDres"])
        self.assertIsNone(payload["idTurmas"])
        self.assertIsNotNone(payload["abrangencia"])

    def test_compacta_tipo_ue_manual_devolve_ues_nula(self) -> None:
        """Tipo UE manual devolve `idUes: null`."""
        criar_perfil(
            int(TipoAbrangencia.UE), grupo_codigo=8, eh_perfil_manual=True
        )

        payload = self.service.abrangencia_compacta(_LOGIN, _PERFIL_GUID)

        self.assertIsNone(payload["idUes"])

    def test_compacta_tipo_ue_grupo_43_devolve_ues_nula(self) -> None:
        """Garante que o grupo 43 segue o caminho manual mesmo nao o sendo."""
        criar_perfil(
            int(TipoAbrangencia.UE), grupo_codigo=43, eh_perfil_manual=False
        )

        payload = self.service.abrangencia_compacta(_LOGIN, _PERFIL_GUID)

        self.assertIsNone(payload["idUes"])

    def test_compacta_tipo_ue_nao_manual_segue_vazia(self) -> None:
        """Garante que o caminho de lotacao continua devolvendo `[]`."""
        criar_perfil(
            int(TipoAbrangencia.UE), grupo_codigo=12, eh_perfil_manual=False
        )

        payload = self.service.abrangencia_compacta(_LOGIN, _PERFIL_GUID)

        self.assertEqual(payload["idUes"], [])

    def test_compacta_preserva_ue_nula_da_origem_de_exercicio(self) -> None:
        """Garante `idUes: [null]` quando a MV traz UE sem codigo."""
        criar_perfil(int(TipoAbrangencia.UE), grupo_codigo=3)
        criar_escopo(origem="LOTACAO_EXERCICIO", ue_codigo=None)

        payload = self.service.abrangencia_compacta(_LOGIN, _PERFIL_GUID)

        self.assertEqual(payload["idUes"], [None])

    def test_compacta_descarta_ue_nula_sem_origem_de_exercicio(self) -> None:
        """Garante `idUes: []` quando a UE sem codigo nao e de exercicio."""
        criar_perfil(int(TipoAbrangencia.UE), grupo_codigo=12)
        criar_escopo(origem="LOTACAO_CARGO", ue_codigo=None)

        payload = self.service.abrangencia_compacta(_LOGIN, _PERFIL_GUID)

        self.assertEqual(payload["idUes"], [])

    def test_contrato_externo_nao_zera_turma_do_poa(self) -> None:
        """Contrato externo mantem `idTurmas` nulo no POA."""
        criar_perfil(int(TipoAbrangencia.UE_TURMAS_DISCIPLINAS))
        criar_escopo(origem="CONTRATO_EXTERNO")

        payload = self.service.abrangencia_compacta(_LOGIN, _PERFIL_GUID)

        self.assertIsNone(payload["idTurmas"])

    def test_compacta_ue_nula_nao_entra_na_lista_expandida(self) -> None:
        """Garante que o nulo fica no identificador e some de `ues`."""
        criar_perfil(int(TipoAbrangencia.UE), grupo_codigo=3)
        criar_escopo(origem="LOTACAO_EXERCICIO", ue_codigo=None)
        criar_escopo(origem="LOTACAO_EXERCICIO", ue_codigo="019331")
        self.rede_sme.com_ue("019331", dre="108100")

        payload = self.service.abrangencia_compacta(
            _LOGIN, _PERFIL_GUID, expandir_ues=True
        )

        self.assertEqual(payload["idUes"], [None, "019331"])
        self.assertEqual([ue["codigo"] for ue in payload["ues"]], ["019331"])

    def test_detalhes_tipo_dre_devolve_uma_unica_dre(self) -> None:
        """Garante uma so DRE no tipo de abrangencia Dre detalhado."""
        criar_perfil(int(TipoAbrangencia.DRE))
        criar_escopo(tipo_resolucao="DETALHES", dre_codigo="109000")
        criar_escopo(tipo_resolucao="DETALHES", dre_codigo="094530")

        payload = self.service.abrangencia_compacta(
            _LOGIN,
            _PERFIL_GUID,
            expandir_dres=True,
            algoritmo_alternativo=True,
        )

        self.assertEqual(payload["idDres"], ["094530"])
        self.assertEqual([dre["codigoDRE"] for dre in payload["dres"]], [])

    def test_detalhes_no_tipo_ue_nao_deriva_dres(self) -> None:
        """Garante `dres: []` no tipo de abrangencia UE sem UEs detalhadas."""
        criar_perfil(int(TipoAbrangencia.UE), grupo_codigo=12)
        self.rede_sme.com_ue("019331", dre="108100")
        self.rede_sme.com_dre("108100", nome="DRE Ipiranga")

        payload = self.service.abrangencia_compacta(
            _LOGIN,
            _PERFIL_GUID,
            expandir_dres=True,
            algoritmo_alternativo=True,
        )

        self.assertEqual(payload["dres"], [])
        self.assertIsNone(payload["ues"])
        self.assertIsNone(payload["idDres"])

    def test_sondagem_no_tipo_ue_deriva_dres(self) -> None:
        """Com `ues` pedida, `dres[]` volta a derivar do pai delas."""
        criar_perfil(int(TipoAbrangencia.UE), grupo_codigo=12)
        criar_escopo(
            tipo_resolucao="DETALHES", ue_codigo="019331", dre_codigo="108100"
        )
        self.rede_sme.com_ue("019331", dre="108100")
        self.rede_sme.com_dre("108100", nome="DRE Ipiranga")

        payload = self.service.abrangencia_compacta(
            _LOGIN,
            _PERFIL_GUID,
            expandir_dres=True,
            expandir_ues=True,
            algoritmo_alternativo=True,
        )

        self.assertEqual([d["codigoDRE"] for d in payload["dres"]], ["108100"])
        self.assertEqual([u["codigo"] for u in payload["ues"]], ["019331"])

    def test_colecao_nao_pedida_sai_none(self) -> None:
        """Colecao que o endpoint nao pede vem `null`, nunca `[]`."""
        criar_perfil(int(TipoAbrangencia.UE))
        criar_escopo(ue_codigo="019331")
        self.rede_sme.com_ue("019331")

        payload = self.service.abrangencia_compacta(_LOGIN, _PERFIL_GUID)

        self.assertIsNone(payload["dres"])
        self.assertIsNone(payload["ues"])
        self.assertIsNone(payload["turmas"])

    def test_nivel_com_linha_na_mv_nao_e_zerado_pelo_tipo(self) -> None:
        """Garante que o tipo de abrangencia nao recorta a MV de novo."""
        criar_perfil(int(TipoAbrangencia.DRE_ESCOLAS_ATRIBUIDAS))
        criar_escopo(dre_codigo="108100")

        payload = self.service.abrangencia_compacta(_LOGIN, _PERFIL_GUID)

        self.assertEqual(payload["idDres"], ["108100"])

    def test_codigo_sem_par_na_rede_fica_so_no_identificador(self) -> None:
        """Identificador e lista expandida sao recortes diferentes."""
        criar_perfil(int(TipoAbrangencia.DRE))
        criar_escopo(dre_codigo="108100")
        criar_escopo(dre_codigo="999999")
        self.rede_sme.com_dre("108100", nome="DRE Ipiranga", sigla="IP")

        payload = self.service.abrangencia_compacta(
            _LOGIN, _PERFIL_GUID, expandir_dres=True
        )

        self.assertEqual(payload["idDres"], ["108100", "999999"])
        self.assertEqual(
            payload["dres"],
            [
                {
                    "codigoDRE": "108100",
                    "nomeDRE": "DRE Ipiranga",
                    "siglaDRE": "IP",
                }
            ],
        )


@override_settings(ABRANGENCIA_ANO_LETIVO=_ANO)
class TestExpansaoDeUes(TestCase):
    """Testes de `AbrangenciaService._expandir_ues`."""

    def setUp(self) -> None:
        """Instancia o servico."""
        self.rede_sme = usar_rede_sme(self)
        self.service = AbrangenciaService()

    def test_traz_nome_sigla_e_dre_pai_da_rede(self) -> None:
        """Garante que `ues[]` sai com os atributos reais, nao `null`."""
        self.rede_sme.com_ue(
            "019331", nome="EMEF Teste", sigla="EMEF T", dre="108100"
        )

        resultado = self.service._expandir_ues(["019331"])

        self.assertEqual(
            resultado,
            [
                {
                    "codigo": "019331",
                    "codigoDRE": "108100",
                    "nome": "EMEF Teste",
                    "sigla": "EMEF T",
                }
            ],
        )

    def test_ue_fora_da_rede_nao_entra_na_colecao(self) -> None:
        """Garante que UE fora da rede nao entra em `ues`, mas fica no id."""
        criar_perfil(int(TipoAbrangencia.UE), grupo_codigo=12)
        criar_escopo(ue_codigo="900101")
        criar_escopo(ue_codigo="900199")
        self.rede_sme.com_ue("900101")

        payload = self.service.abrangencia_compacta(
            _LOGIN, _PERFIL_GUID, expandir_ues=True
        )

        self.assertEqual(payload["idUes"], ["900101", "900199"])
        self.assertEqual([ue["codigo"] for ue in payload["ues"]], ["900101"])

    def test_colecao_sai_ordenada_por_codigo(self) -> None:
        """As UEs saem ordenadas, independentemente da ordem do escopo."""
        self.rede_sme.com_ue("094811").com_ue("019331")

        resultado = self.service._expandir_ues(["094811", "019331"])

        self.assertEqual(
            [item["codigo"] for item in resultado], ["019331", "094811"]
        )

    def test_escopo_vazio_traz_as_ues_da_rede(self) -> None:
        """Garante que escopo vazio traz a rede, nao uma lista vazia."""
        self.rede_sme.com_ue("900102").com_ue("900101")

        resultado = self.service._expandir_ues([])

        self.assertEqual(
            [item["codigo"] for item in resultado], ["900101", "900102"]
        )

    def test_tipo_dre_expande_ues_da_dre_e_nao_do_escopo(self) -> None:
        """Tipo Dre monta `ues[]` a partir da DRE."""
        self.rede_sme.com_ue("019331", dre="108100")
        self.rede_sme.com_ue("094811", dre="108100")
        self.rede_sme.com_ue("400305", dre="109000")

        resultado = self.service._expandir_ues_da_dre(
            ["108100"], int(TipoAbrangencia.DRE)
        )

        self.assertEqual(
            [item["codigo"] for item in resultado], ["019331", "094811"]
        )

    def test_tipo_sme_expande_a_rede_inteira(self) -> None:
        """Garante que o tipo de abrangencia SME nao filtra `ues[]` por DRE."""
        self.rede_sme.com_ue("019331", dre="108100")
        self.rede_sme.com_ue("400305", dre="109000")

        resultado = self.service._expandir_ues_da_dre(
            [], int(TipoAbrangencia.SME)
        )

        self.assertEqual(
            [item["codigo"] for item in resultado], ["019331", "400305"]
        )


@override_settings(ABRANGENCIA_ANO_LETIVO=_ANO)
class TestExpansaoDeDres(TestCase):
    """Testes de `AbrangenciaService._expandir_dres`."""

    def setUp(self) -> None:
        """Instancia o servico e uma DRE na rede."""
        self.rede_sme = usar_rede_sme(self)
        self.rede_sme.com_dre("108100", nome="DRE Ipiranga", sigla="IP")
        self.service = AbrangenciaService()

    def test_traz_nome_e_sigla_do_institucional(self) -> None:
        """Garante que `dres[]` sai com `nomeDRE` e `siglaDRE` reais."""
        resultado = self.service._expandir_dres(
            ["108100"], [], int(TipoAbrangencia.DRE)
        )

        self.assertEqual(
            resultado,
            [
                {
                    "codigoDRE": "108100",
                    "nomeDRE": "DRE Ipiranga",
                    "siglaDRE": "IP",
                }
            ],
        )

    def test_tipo_ue_deriva_a_lista_do_pai_das_ues(self) -> None:
        """Garante que a lista deriva das UEs."""
        ues = [
            {
                "codigo": "019331",
                "codigoDRE": "108100",
                "nome": "EMEF",
                "sigla": "E",
            }
        ]

        for tipo in (
            TipoAbrangencia.UE,
            TipoAbrangencia.DRE_ESCOLAS_ATRIBUIDAS,
        ):
            with self.subTest(tipo_abrangencia=tipo):
                resultado = self.service._expandir_dres([], ues, int(tipo))

                self.assertEqual(
                    [item["codigoDRE"] for item in resultado], ["108100"]
                )

    def test_tipo_ue_sem_ue_detalhavel_sai_vazia(self) -> None:
        """Sem UE detalhavel, `dres[]` sai vazia mesmo havendo `idDres`."""
        for tipo in (
            TipoAbrangencia.UE,
            TipoAbrangencia.DRE_ESCOLAS_ATRIBUIDAS,
        ):
            with self.subTest(tipo_abrangencia=tipo):
                resultado = self.service._expandir_dres(
                    ["108100"], [], int(tipo)
                )

                self.assertEqual(resultado, [])

    def test_dre_derivada_fora_do_institucional_nao_entra(self) -> None:
        """DRE pai que o Institucional nao conhece nao entra na lista."""
        ues = [
            {
                "codigo": "019331",
                "codigoDRE": "999999",
                "nome": "EMEF",
                "sigla": "E",
            }
        ]

        resultado = self.service._expandir_dres(
            [], ues, int(TipoAbrangencia.UE)
        )

        self.assertEqual(resultado, [])


@override_settings(ABRANGENCIA_ANO_LETIVO=_ANO)
class TestExpansaoDeTurmas(TestCase):
    """Testes de `AbrangenciaService._expandir_turmas`."""

    def setUp(self) -> None:
        """Instancia o servico."""
        self.rede_sme = usar_rede_sme(self)
        self.service = AbrangenciaService()

    def test_inclui_somente_turma_elegivel_a_sondagem(self) -> None:
        """Garante que o recorte de sondagem vale so para a lista."""
        criar_perfil(int(TipoAbrangencia.PROFESSOR))
        criar_escopo(tipo_resolucao="DETALHES", turma_codigo="1234")
        criar_escopo(tipo_resolucao="DETALHES", turma_codigo="9999")
        self.rede_sme.com_turma("1234", sondagem=True)
        self.rede_sme.com_turma("9999", sondagem=False)

        payload = self.service.abrangencia_compacta(
            _LOGIN,
            _PERFIL_GUID,
            expandir_turmas=True,
            algoritmo_alternativo=True,
        )

        self.assertEqual(payload["idTurmas"], ["1234", "9999"])
        assert payload["turmas"] is not None
        self.assertEqual(
            [turma["codigo"] for turma in payload["turmas"]], ["1234"]
        )

    def test_projeta_nome_e_escola_da_turma(self) -> None:
        """`turmas[]` projeta `nome` e `codigoEscola` do MS Pedagogico."""
        self.rede_sme.com_turma("1234", nome="1o Ano A", ue="019331")

        resultado = self.service._expandir_turmas(["1234"], _ANO)

        self.assertEqual(
            resultado,
            [
                {
                    "codigo": "1234",
                    "nome": "1o Ano A",
                    "codigoEscola": "019331",
                }
            ],
        )

    def test_sem_turma_elegivel_sai_lista_vazia(self) -> None:
        """Garante que `turmas` sai `[]`, nao `None`, sem turma elegivel."""
        self.rede_sme.com_turma("1234", sondagem=False)

        self.assertEqual(self.service._expandir_turmas(["1234"], _ANO), [])

    def test_escopo_vazio_traz_a_rede_inteira(self) -> None:
        """Garante que escopo vazio traz a rede, nao uma lista vazia."""
        self.rede_sme.com_turma("1234").com_turma("5678")
        self.rede_sme.com_turma("9999", sondagem=False)

        resultado = self.service._expandir_turmas([], _ANO)

        assert resultado is not None
        self.assertEqual(
            [turma["codigo"] for turma in resultado], ["1234", "5678"]
        )

    def test_rede_sem_turma_elegivel_sai_lista_vazia(self) -> None:
        """Rede sem nenhuma turma elegivel devolve `[]`, nao `None`."""
        self.assertEqual(self.service._expandir_turmas([], _ANO), [])


@override_settings(ABRANGENCIA_ANO_LETIVO=_ANO)
class TestUsuariosPorPerfilDaDre(TestCase):
    """Testes do filtro por DRE de `usuarios_por_perfil`."""

    def setUp(self) -> None:
        """Lota um usuario em duas UEs, de DREs diferentes."""
        self.rede_sme = usar_rede_sme(self)
        self.rede_sme.com_unidade("900101", "900100")
        self.rede_sme.com_unidade("900102", "900200")
        for ue in ("900101", "900102"):
            UsuarioPorPerfil.objects.create(
                usuario_rf=_LOGIN,
                perfil_guid=_PERFIL_GUID,
                ano_letivo=_ANO,
                ue_codigo=ue,
            )
        self.service = AbrangenciaService()

    def test_filtra_dre_pelo_mapa_do_institucional(self) -> None:
        """Garante o usuario com alguma UE da DRE pedida."""
        casos = {"900100": 1, "900200": 1, "900300": 0}

        for dre, quantidade in casos.items():
            with self.subTest(dre=dre):
                resultado = self.service.usuarios_por_perfil(
                    "900101", dre, [_PERFIL_GUID]
                )

                self.assertEqual(len(resultado), quantidade)

    def test_ues_devolvidas_nao_dependem_do_filtro(self) -> None:
        """Garante as UEs da posse inteira, com ou sem DRE."""
        resultado = self.service.usuarios_por_perfil(
            "900101", "900100", [_PERFIL_GUID]
        )

        self.assertEqual(
            resultado[0]["perfils"][0]["ues"], ["900101", "900102"]
        )


class TestUsuariosPorPerfilService(TestCase):
    """Testes de `AbrangenciaService.usuarios_por_perfil`."""

    def test_agrupa_por_usuario_preservando_a_grafia_perfils(self) -> None:
        """Garante a grafia `perfils`, sem o "i", no agrupamento."""
        service = AbrangenciaService()
        registros = [
            {
                "usuario_rf": _LOGIN,
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
                    "usuarioRf": _LOGIN,
                    "perfils": [{"perfil": _PERFIL_GUID, "ues": ["019331"]}],
                }
            ],
        )

    def test_usuario_com_dois_perfis_vira_uma_entrada(self) -> None:
        """Um usuario em dois perfis sai uma vez."""
        service = AbrangenciaService()
        outro_perfil = "57a7b9ab-8e61-4093-b692-a0bb1f9f46bd"
        registros = [
            {
                "usuario_rf": _LOGIN,
                "perfil_guid": _PERFIL_GUID,
                "ues": ["019331"],
            },
            {
                "usuario_rf": _LOGIN,
                "perfil_guid": outro_perfil,
                "ues": ["019331"],
            },
        ]

        with patch.object(
            service, "_usuarios_por_perfil", return_value=registros
        ):
            resultado = service.usuarios_por_perfil(
                "019331", None, [_PERFIL_GUID, outro_perfil]
            )

        self.assertEqual(len(resultado), 1)
        self.assertEqual(len(resultado[0]["perfils"]), 2)
