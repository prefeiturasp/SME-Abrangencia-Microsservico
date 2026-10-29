"""Testes das views do dominio Abrangencia."""

import gzip
import json
from typing import Any, cast
from unittest.mock import MagicMock, patch

import httpx
from django.core.cache import caches
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import Resolver404, resolve
from rest_framework import status
from rest_framework.test import APIClient

from apps.abrangencia.api.views import (
    CicloEnsinoView,
    CodigosDresView,
    CompactaDreDetalhesView,
    CompactaSemRedisView,
    CompactaSondagemView,
    CompactaVigenteView,
    DresNomeAbreviacaoView,
    PerfilView,
)
from apps.abrangencia.integracao_eol import InstitucionalAPI, PedagogicoAPI
from apps.abrangencia.models import Perfil, UsuarioPorPerfil
from apps.abrangencia.rede_sme import RedeSmeIncompletaError
from apps.abrangencia.testes.helpers import criar_escopo, usar_rede_sme

_API_KEY = "chave-de-teste"
_PERFIL_GUID = "2e89cf10-e42b-476f-8673-2dfbeeee3cd0"
_LOGIN = "9999001"
_ANO = 2026

_BASE = "/api/abrangencia"

_CHAVES_COMPACTA = {
    "login",
    "abrangencia",
    "idDres",
    "dres",
    "idUes",
    "ues",
    "idTurmas",
    "turmas",
}


class TestFidelidadeDasRotas(TestCase):
    """Trava os caminhos das rotas contra o legado."""

    def test_rotas_reproduzem_os_caminhos_do_legado(self) -> None:
        """Garante que cada endpoint responde no caminho do legado."""
        esperado = {
            "perfil": (f"{_BASE}/{_PERFIL_GUID}", 32),
            "compacta-vigente": (
                f"{_BASE}/compacta-vigente/{_LOGIN}/perfil/{_PERFIL_GUID}",
                162,
            ),
            "compacta-vigente-dre-detalhes": (
                f"{_BASE}/compacta-vigente/{_LOGIN}/perfil/{_PERFIL_GUID}"
                "/DreDetalhes",
                174,
            ),
            "compacta-vigente-sondagem": (
                f"{_BASE}/compacta-vigente/{_LOGIN}/perfil/{_PERFIL_GUID}"
                "/Sondagem",
                186,
            ),
            "compacta-sem-redis": (
                f"{_BASE}/compacta-semRedis/{_LOGIN}/perfil/{_PERFIL_GUID}",
                198,
            ),
            "perfis-usuarios": (f"{_BASE}/perfis/usuarios", 255),
            "codigos-dres": (f"{_BASE}/codigos-dres", 54),
            "nome-abreviacao-dres": (f"{_BASE}/nome-abreviacao-dres", 74),
            "ciclo-ensino": (f"{_BASE}/ciclo-ensino", 242),
            "estrutura-vigente-por-dre": (
                f"{_BASE}/estrutura-vigente/000100",
                94,
            ),
            "estrutura-vigente": (f"{_BASE}/estrutura-vigente", 115),
        }

        for nome, (caminho, linha_legado) in esperado.items():
            with self.subTest(rota=nome, legado=linha_legado):
                self.assertEqual(resolve(caminho).url_name, nome)

    def test_rotas_de_um_segmento_nao_caem_na_rota_do_perfil(self) -> None:
        """Garante que a rota do perfil nao engole as rotas de um segmento.

        Registradas depois de `<str:id_perfil>/`, elas responderiam 400
        "O perfil é obrigatório.".
        """
        esperado = {
            f"{_BASE}/codigos-dres": CodigosDresView,
            f"{_BASE}/nome-abreviacao-dres": DresNomeAbreviacaoView,
            f"{_BASE}/ciclo-ensino": CicloEnsinoView,
            f"{_BASE}/{_PERFIL_GUID}": PerfilView,
        }

        for caminho, view in esperado.items():
            with self.subTest(caminho=caminho):
                funcao = cast(Any, resolve(caminho).func)
                self.assertIs(funcao.view_class, view)

    def test_rota_com_barra_final_nao_resolve(self) -> None:
        """Garante que a barra final nao e aceita, como no legado.

        Nenhuma rota do `AbrangenciaController` termina em barra.
        """
        caminhos = [
            f"{_BASE}/{_PERFIL_GUID}/",
            f"{_BASE}/compacta-vigente/{_LOGIN}/perfil/{_PERFIL_GUID}/",
            f"{_BASE}/compacta-vigente/{_LOGIN}/perfil/{_PERFIL_GUID}"
            "/DreDetalhes/",
            f"{_BASE}/compacta-vigente/{_LOGIN}/perfil/{_PERFIL_GUID}"
            "/Sondagem/",
            f"{_BASE}/compacta-semRedis/{_LOGIN}/perfil/{_PERFIL_GUID}/",
            f"{_BASE}/perfis/usuarios/",
            f"{_BASE}/codigos-dres/",
            f"{_BASE}/nome-abreviacao-dres/",
            f"{_BASE}/ciclo-ensino/",
        ]

        for caminho in caminhos:
            with (
                self.subTest(caminho=caminho),
                self.assertRaises(Resolver404),
            ):
                resolve(caminho)


class TestFlagsDeExpansaoPorEndpoint(TestCase):
    """Trava quais colecoes cada endpoint pede, contra o legado."""

    def test_flags_reproduzem_as_do_controller(self) -> None:
        """Garante as flags de cada endpoint, com a linha do legado."""
        esperado = {
            CompactaVigenteView: (False, False, False, False, 162),
            CompactaDreDetalhesView: (True, False, False, True, 183),
            CompactaSondagemView: (True, True, True, True, 195),
            CompactaSemRedisView: (False, False, False, True, 207),
        }

        for view, flags in esperado.items():
            dres, ues, turmas, alternativo, linha = flags
            with self.subTest(view=view.__name__, legado=linha):
                self.assertEqual(view.expandir_dres, dres)
                self.assertEqual(view.expandir_ues, ues)
                self.assertEqual(view.expandir_turmas, turmas)
                self.assertEqual(view.algoritmo_alternativo, alternativo)


@override_settings(API_KEY=_API_KEY, API_KEY_HEADER="X-API-Key")
class TestPerfilView(TestCase):
    """Testes de `PerfilView`."""

    def setUp(self) -> None:
        """Prepara um client autenticado por API Key."""
        self.client = APIClient()
        self.client.credentials(HTTP_X_API_KEY=_API_KEY)

    def test_sem_api_key_retorna_401(self) -> None:
        """Requisicao sem API Key e recusada."""
        client_sem_chave = APIClient()

        resposta = client_sem_chave.get(f"{_BASE}/{_PERFIL_GUID}")

        self.assertEqual(resposta.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_guid_vazio_retorna_400(self) -> None:
        """GUID vazio/malformado e recusado antes de qualquer consulta."""
        resposta = self.client.get(
            f"{_BASE}/00000000-0000-0000-0000-000000000000"
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_perfil_inexistente_retorna_204(self) -> None:
        """Perfil sem registro nao e erro: responde sem corpo."""
        resposta = self.client.get(f"{_BASE}/{_PERFIL_GUID}")

        self.assertEqual(resposta.status_code, status.HTTP_204_NO_CONTENT)

    def test_perfil_existente_retorna_200_com_o_grupo_cargos(self) -> None:
        """Perfil existente devolve o `GrupoCargosDTO`."""
        Perfil.objects.create(
            perfil_guid=_PERFIL_GUID,
            grupo_codigo=10,
            abrangencia_id=1,
            eh_perfil_manual=False,
        )

        resposta = self.client.get(f"{_BASE}/{_PERFIL_GUID}")

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.json()["grupoID"], _PERFIL_GUID)


@override_settings(
    API_KEY=_API_KEY, API_KEY_HEADER="X-API-Key", ABRANGENCIA_ANO_LETIVO=_ANO
)
class TestCompactaVigenteView(TestCase):
    """Testes de `CompactaVigenteView`."""

    def setUp(self) -> None:
        """Prepara um client autenticado e o perfil consultado."""
        self.client = APIClient()
        self.client.credentials(HTTP_X_API_KEY=_API_KEY)
        Perfil.objects.create(
            perfil_guid=_PERFIL_GUID,
            grupo_codigo=10,
            abrangencia_id=1,
            eh_perfil_manual=False,
        )

    def test_guid_invalido_retorna_400(self) -> None:
        """GUID malformado e recusado antes de consultar o escopo."""
        resposta = self.client.get(
            f"{_BASE}/compacta-vigente/{_LOGIN}/perfil/nao-e-guid"
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_usuario_sem_escopo_retorna_200(self) -> None:
        """Usuario sem linha na MV nao e erro: responde 200."""
        resposta = self.client.get(
            f"{_BASE}/compacta-vigente/999999/perfil/{_PERFIL_GUID}"
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.json()["login"], "999999")

    def test_payload_traz_as_oito_chaves_do_contrato(self) -> None:
        """Garante as oito chaves do contrato, com as colecoes `null`."""
        criar_escopo(ue_codigo="019331")

        resposta = self.client.get(
            f"{_BASE}/compacta-vigente/{_LOGIN}/perfil/{_PERFIL_GUID}"
        )

        corpo = resposta.json()
        self.assertEqual(set(corpo), _CHAVES_COMPACTA)
        self.assertEqual(corpo["idUes"], ["019331"])
        self.assertIsNone(corpo["idDres"])
        self.assertIsNone(corpo["dres"])
        self.assertIsNone(corpo["ues"])
        self.assertIsNone(corpo["turmas"])


@override_settings(
    API_KEY=_API_KEY, API_KEY_HEADER="X-API-Key", ABRANGENCIA_ANO_LETIVO=_ANO
)
class TestRotasDoAlgoritmoAlternativo(TestCase):
    """Testes de `CompactaDreDetalhesView` e `CompactaSemRedisView`."""

    def setUp(self) -> None:
        """Cria o perfil e escopos distintos para os dois algoritmos."""
        self.client = APIClient()
        self.client.credentials(HTTP_X_API_KEY=_API_KEY)
        Perfil.objects.create(
            perfil_guid=_PERFIL_GUID,
            grupo_codigo=10,
            abrangencia_id=1,
            eh_perfil_manual=False,
        )
        criar_escopo(
            tipo_resolucao="COMPACTA", ue_codigo="019331"
        )
        criar_escopo(
            tipo_resolucao="DETALHES", ue_codigo="094811"
        )

    def test_rotas_detalhadas_devolvem_o_escopo_de_detalhes(self) -> None:
        """Garante que as rotas detalhadas leem `DETALHES`."""
        rotas = (
            f"{_BASE}/compacta-vigente/{_LOGIN}/perfil/{_PERFIL_GUID}"
            "/DreDetalhes",
            f"{_BASE}/compacta-semRedis/{_LOGIN}/perfil/{_PERFIL_GUID}",
        )

        for rota in rotas:
            with self.subTest(rota=rota):
                resposta = self.client.get(rota)

                self.assertEqual(resposta.status_code, status.HTTP_200_OK)
                self.assertEqual(resposta.json()["idUes"], ["094811"])

    def test_rota_de_dres_detalhadas_expande_dres(self) -> None:
        """Garante que so a rota de DREs detalhadas devolve `dres[]`."""
        Perfil.objects.filter(perfil_guid=_PERFIL_GUID).update(
            abrangencia_id=6
        )
        criar_escopo(
            tipo_resolucao="DETALHES", dre_codigo="108100"
        )
        usar_rede_sme(self).com_dre("108100", nome="DRE Ipiranga", sigla="IP")

        e08 = self.client.get(
            f"{_BASE}/compacta-vigente/{_LOGIN}/perfil/{_PERFIL_GUID}"
            "/DreDetalhes"
        ).json()
        e10 = self.client.get(
            f"{_BASE}/compacta-semRedis/{_LOGIN}/perfil/{_PERFIL_GUID}"
        ).json()

        self.assertEqual(e08["idDres"], ["108100"])
        self.assertEqual(e08["dres"][0]["nomeDRE"], "DRE Ipiranga")
        self.assertEqual(e10["idDres"], ["108100"])
        self.assertIsNone(e10["dres"])


@override_settings(
    API_KEY=_API_KEY, API_KEY_HEADER="X-API-Key", ABRANGENCIA_ANO_LETIVO=_ANO
)
class TestCompactaSondagemView(TestCase):
    """Testes de `CompactaSondagemView`."""

    def setUp(self) -> None:
        """Prepara client, perfil de Professor e escopo de turma."""
        self.rede_sme = usar_rede_sme(self)
        self.client = APIClient()
        self.client.credentials(HTTP_X_API_KEY=_API_KEY)
        Perfil.objects.create(
            perfil_guid=_PERFIL_GUID,
            grupo_codigo=6,
            abrangencia_id=2,
            eh_perfil_manual=False,
        )

    def test_tipo_professor_expande_so_turmas(self) -> None:
        """Tipo Professor expande somente turmas."""
        criar_escopo(
            tipo_resolucao="DETALHES", turma_codigo="1234"
        )
        self.rede_sme.com_turma("1234", nome="1o Ano A", ue="019331")

        resposta = self.client.get(
            f"{_BASE}/compacta-vigente/{_LOGIN}/perfil/{_PERFIL_GUID}"
            "/Sondagem"
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        corpo = resposta.json()
        self.assertEqual(corpo["turmas"][0]["codigoEscola"], "019331")
        self.assertEqual(corpo["turmas"][0]["nome"], "1o Ano A")
        self.assertIsNone(corpo["dres"])
        self.assertIsNone(corpo["ues"])

    def test_turma_fora_da_sondagem_some_da_colecao_mas_fica_no_id(
        self,
    ) -> None:
        """Garante que o recorte de sondagem vale so para `turmas[]`."""
        criar_escopo(
            tipo_resolucao="DETALHES", turma_codigo="9999"
        )
        self.rede_sme.com_turma("9999", sondagem=False)

        resposta = self.client.get(
            f"{_BASE}/compacta-vigente/{_LOGIN}/perfil/{_PERFIL_GUID}"
            "/Sondagem"
        )

        corpo = resposta.json()
        self.assertEqual(corpo["idTurmas"], ["9999"])
        self.assertEqual(corpo["turmas"], [])


@override_settings(
    API_KEY=_API_KEY, API_KEY_HEADER="X-API-Key", ABRANGENCIA_ANO_LETIVO=_ANO
)
class TestExpansaoNoTipoUe(TestCase):
    """Testes das colecoes expandidas no tipo de abrangencia UE (1)."""

    def setUp(self) -> None:
        """Prepara client e um perfil do tipo de abrangencia UE."""
        self.rede_sme = usar_rede_sme(self)
        self.client = APIClient()
        self.client.credentials(HTTP_X_API_KEY=_API_KEY)
        Perfil.objects.create(
            perfil_guid=_PERFIL_GUID,
            grupo_codigo=10,
            abrangencia_id=1,
            eh_perfil_manual=False,
        )

    def test_colecoes_expandidas_trazem_atributos_da_mv(self) -> None:
        """Garante nome, sigla e pai preenchidos, e `dres` vinda das UEs."""
        criar_escopo(
            tipo_resolucao="DETALHES", ue_codigo="019331"
        )
        self.rede_sme.com_ue(
            "019331", nome="EMEF Teste", sigla="EMEF T", dre="108100"
        )
        self.rede_sme.com_dre("108100", nome="DRE Ipiranga", sigla="IP")

        resposta = self.client.get(
            f"{_BASE}/compacta-vigente/{_LOGIN}/perfil/{_PERFIL_GUID}"
            "/Sondagem"
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        corpo = resposta.json()
        self.assertEqual(corpo["ues"][0]["sigla"], "EMEF T")
        self.assertEqual(corpo["ues"][0]["codigoDRE"], "108100")
        self.assertEqual(corpo["dres"][0]["nomeDRE"], "DRE Ipiranga")
        self.assertIsNone(corpo["idDres"])
        self.assertIsNone(corpo["turmas"])

    def test_escopo_de_ue_vazio_traz_a_rede_inteira(self) -> None:
        """Garante que escopo vazio traz a rede, nao uma lista vazia."""
        self.rede_sme.com_ue("019331", dre="108100")
        self.rede_sme.com_ue("094811", dre="108100")

        resposta = self.client.get(
            f"{_BASE}/compacta-vigente/{_LOGIN}/perfil/{_PERFIL_GUID}"
            "/Sondagem"
        )

        corpo = resposta.json()
        self.assertEqual(corpo["idUes"], [])
        self.assertEqual(
            [ue["codigo"] for ue in corpo["ues"]], ["019331", "094811"]
        )


@override_settings(API_KEY=_API_KEY, API_KEY_HEADER="X-API-Key")
class TestPerfisUsuariosView(TestCase):
    """Testes de `PerfisUsuariosView`."""

    def setUp(self) -> None:
        """Prepara um client autenticado por API Key."""
        self.client = APIClient()
        self.client.credentials(HTTP_X_API_KEY=_API_KEY)

    def test_corpo_invalido_retorna_400(self) -> None:
        """Corpo sem `ue`/`perfis` e recusado."""
        resposta = self.client.post(
            f"{_BASE}/perfis/usuarios", data={}, format="json"
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_corpo_valido_sem_usuarios_retorna_lista_vazia(self) -> None:
        """Corpo valido sem usuarios lotados devolve `[]`."""
        resposta = self.client.post(
            f"{_BASE}/perfis/usuarios",
            data={"ue": "019331", "perfis": [_PERFIL_GUID]},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.json(), [])

    def test_payload_preserva_a_grafia_perfils(self) -> None:
        """Garante a grafia `perfils` no payload."""
        UsuarioPorPerfil.objects.create(
            usuario_rf=_LOGIN,
            perfil_guid=_PERFIL_GUID,
            ano_letivo=_ANO,
            ue_codigo="019331",
        )

        resposta = self.client.post(
            f"{_BASE}/perfis/usuarios",
            data={"ue": "019331", "perfis": [_PERFIL_GUID]},
            format="json",
        )

        corpo = resposta.json()
        self.assertEqual(set(corpo[0]), {"usuarioRf", "perfils"})
        self.assertEqual(corpo[0]["usuarioRf"], _LOGIN)
        self.assertEqual(corpo[0]["perfils"][0]["ues"], ["019331"])

    @override_settings(ABRANGENCIA_ANO_LETIVO=_ANO)
    def test_post_devolve_posse_completa_do_usuario(self) -> None:
        """O POST seleciona por CP e preserva a posse completa."""
        cp = "40e1e074-37d6-e911-abd6-f81654fe895d"
        professor = "41e1e074-37d6-e911-abd6-f81654fe895d"
        infantil = "60e1e074-37d6-e911-abd6-f81654fe895d"
        cj = "61e1e074-37d6-e911-abd6-f81654fe895d"
        for guid, ue in [
            (cp, "019715"),
            (professor, "019715"),
            (infantil, "019519"),
            (cj, ""),
        ]:
            UsuarioPorPerfil.objects.create(
                usuario_rf="9999002",
                perfil_guid=guid,
                ano_letivo=_ANO,
                ue_codigo=ue,
            )
        usar_rede_sme(self).com_unidade("019715", "108100")
        resposta = self.client.post(
            f"{_BASE}/perfis/usuarios",
            data={"ue": "019715", "dre": "108100", "perfis": [cp]},
            format="json",
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(
            resposta.json(),
            [
                {
                    "usuarioRf": "9999002",
                    "perfils": [
                        {"perfil": cp, "ues": ["019715"]},
                        {"perfil": professor, "ues": ["019715"]},
                        {"perfil": infantil, "ues": ["019519"]},
                        {"perfil": cj, "ues": []},
                    ],
                }
            ],
        )

    def test_content_types_do_legado_produzem_a_mesma_resposta(
        self,
    ) -> None:
        """Garante o mesmo 200 para os três content-types do legado."""
        UsuarioPorPerfil.objects.create(
            usuario_rf=_LOGIN,
            perfil_guid=_PERFIL_GUID,
            ano_letivo=_ANO,
            ue_codigo="019331",
        )
        corpo = json.dumps({"ue": "019331", "perfis": [_PERFIL_GUID]})

        respostas = {}
        for content_type in [
            "application/json",
            "text/json",
            "application/json-patch+json",
        ]:
            with self.subTest(content_type=content_type):
                resposta = self.client.post(
                    f"{_BASE}/perfis/usuarios",
                    data=corpo,
                    content_type=content_type,
                )
                self.assertEqual(resposta.status_code, status.HTTP_200_OK)
                respostas[content_type] = resposta.json()

        self.assertEqual(len(respostas), 3)
        self.assertEqual(
            respostas["text/json"], respostas["application/json"]
        )
        self.assertEqual(
            respostas["application/json-patch+json"],
            respostas["application/json"],
        )
        self.assertEqual(
            respostas["application/json"][0]["usuarioRf"], _LOGIN
        )

    def test_content_type_text_plain_responde_415(self) -> None:
        """Garante que content-type fora de JSON continua recusado."""
        resposta = self.client.post(
            f"{_BASE}/perfis/usuarios",
            data=json.dumps({"ue": "019331", "perfis": [_PERFIL_GUID]}),
            content_type="text/plain",
        )

        self.assertEqual(
            resposta.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
        )


_CORPO_CODIGOS_DRES = b'["000100", "000200"]'
_CORPO_DRES = (
    b'[{"codigo": "000100", "nome": "DIRETORIA TESTE",'
    b' "abreviacao": "DRE - TT"}]'
)


def _lista_grande() -> bytes:
    ciclos = [
        {
            "codigoModalidadeEnsino": 1,
            "codigoEtapaEnsino": 2,
            "codigo": codigo,
            "descricao": "CICLO TESTE",
            "dtAtualizacao": "2011-01-21T19:10:37.937",
        }
        for codigo in range(500)
    ]
    return json.dumps(ciclos).encode()


_CORPO_CICLOS = (
    b'[{"codigoModalidadeEnsino": 1, "codigoEtapaEnsino": 2, "codigo": 3,'
    b' "descricao": "CICLO TESTE",'
    b' "dtAtualizacao": "2011-01-21T19:10:37.937"}]'
)
_INDISPONIVEL_INSTITUCIONAL = {
    "detail": "Serviço de institucional indisponível."
}


def _externa(status_code: int = 200, conteudo: bytes = b"") -> httpx.Response:
    return httpx.Response(status_code, content=conteudo)


@override_settings(API_KEY=_API_KEY, API_KEY_HEADER="X-API-Key")
class TestDresDaRedeViews(SimpleTestCase):
    """Testes de `CodigosDresView` e `DresNomeAbreviacaoView`."""

    def setUp(self) -> None:
        """Prepara um client autenticado por API Key."""
        self.client = APIClient()
        self.client.credentials(HTTP_X_API_KEY=_API_KEY)

    @patch.object(InstitucionalAPI, "codigos_dres")
    def test_codigos_dres_repassa_o_corpo_do_institucional(
        self, externa: MagicMock
    ) -> None:
        """Garante E-02 com os mesmos bytes do MS-Institucional."""
        externa.return_value = _externa(200, _CORPO_CODIGOS_DRES)

        resposta = self.client.get(f"{_BASE}/codigos-dres")

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.content, _CORPO_CODIGOS_DRES)
        self.assertEqual(resposta["Content-Type"], "application/json")

    @patch.object(InstitucionalAPI, "dres_nome_abreviacao")
    def test_nome_abreviacao_repassa_o_corpo_do_institucional(
        self, externa: MagicMock
    ) -> None:
        """Garante E-03 com os mesmos bytes do MS-Institucional."""
        externa.return_value = _externa(200, _CORPO_DRES)

        resposta = self.client.get(f"{_BASE}/nome-abreviacao-dres")

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.content, _CORPO_DRES)

    @patch.object(InstitucionalAPI, "dres_nome_abreviacao")
    @patch.object(InstitucionalAPI, "codigos_dres")
    def test_sem_dre_responde_204_sem_corpo(
        self, codigos: MagicMock, nomes: MagicMock
    ) -> None:
        """Garante 204, e nao 200 com lista vazia, nas duas rotas.

        O legado so responde 200 quando a lista tem ao menos uma DRE.
        """
        rotas = {"codigos-dres": codigos, "nome-abreviacao-dres": nomes}
        for status_externo, conteudo in ((200, b"[]"), (204, b""), (200, b"")):
            for rota, externa in rotas.items():
                externa.return_value = _externa(status_externo, conteudo)
                with self.subTest(rota=rota, conteudo=conteudo):
                    resposta = self.client.get(f"{_BASE}/{rota}")

                    self.assertEqual(
                        resposta.status_code, status.HTTP_204_NO_CONTENT
                    )
                    self.assertEqual(resposta.content, b"")

    @patch.object(InstitucionalAPI, "codigos_dres")
    def test_institucional_fora_do_ar_responde_503(
        self, externa: MagicMock
    ) -> None:
        """Garante 503 com o nome da API, e nunca 204, sem o upstream."""
        externa.side_effect = httpx.ConnectError("recusada")

        resposta = self.client.get(f"{_BASE}/codigos-dres")

        self.assertEqual(
            resposta.status_code, status.HTTP_503_SERVICE_UNAVAILABLE
        )
        self.assertEqual(resposta.json(), _INDISPONIVEL_INSTITUCIONAL)


@override_settings(API_KEY=_API_KEY, API_KEY_HEADER="X-API-Key")
@patch.object(PedagogicoAPI, "ciclos_ensino")
class TestCicloEnsinoView(SimpleTestCase):
    """Testes de `CicloEnsinoView`."""

    def setUp(self) -> None:
        """Prepara um client autenticado por API Key."""
        self.client = APIClient()
        self.client.credentials(HTTP_X_API_KEY=_API_KEY)

    def test_repassa_o_corpo_sem_transformacao(
        self, externa: MagicMock
    ) -> None:
        """Garante os mesmos bytes, com `dtAtualizacao` sem fuso."""
        externa.return_value = _externa(200, _CORPO_CICLOS)

        resposta = self.client.get(f"{_BASE}/ciclo-ensino")

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.content, _CORPO_CICLOS)
        self.assertEqual(resposta["Content-Type"], "application/json")

    def test_sem_accept_encoding_nao_comprime(
        self, externa: MagicMock
    ) -> None:
        """Garante o corpo cru para consumidor que nao pede gzip."""
        externa.return_value = _externa(200, _lista_grande())

        resposta = self.client.get(f"{_BASE}/ciclo-ensino")

        self.assertFalse(resposta.has_header("Content-Encoding"))
        self.assertEqual(resposta.content, _lista_grande())

    def test_com_accept_encoding_gzip_comprime(
        self, externa: MagicMock
    ) -> None:
        """Garante o response em gzip."""
        externa.return_value = _externa(200, _lista_grande())

        resposta = self.client.get(
            f"{_BASE}/ciclo-ensino", HTTP_ACCEPT_ENCODING="gzip"
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta["Content-Encoding"], "gzip")
        self.assertLess(len(resposta.content), len(_lista_grande()))
        self.assertEqual(
            gzip.decompress(resposta.content), _lista_grande()
        )

    def test_lista_vazio_responde_200_e_nunca_204(
        self, externa: MagicMock
    ) -> None:
        """Garante 200 com `[]` quando nenhum registro e encontrado."""
        for status_externo, conteudo in ((200, b"[]"), (204, b""), (200, b"")):
            externa.return_value = _externa(status_externo, conteudo)
            with self.subTest(status=status_externo, conteudo=conteudo):
                resposta = self.client.get(f"{_BASE}/ciclo-ensino")

                self.assertEqual(resposta.status_code, status.HTTP_200_OK)
                self.assertEqual(resposta.json(), [])

    def test_api_fora_do_ar_responde_503(self, externa: MagicMock) -> None:
        """Garante 503 com o nome da API no `detail`."""
        externa.side_effect = httpx.ReadTimeout("expirou")

        resposta = self.client.get(f"{_BASE}/ciclo-ensino")

        self.assertEqual(
            resposta.status_code, status.HTTP_503_SERVICE_UNAVAILABLE
        )
        self.assertEqual(
            resposta.json(), {"detail": "Serviço de pedagogico indisponível."}
        )


_ESTRUTURA = {
    "dres": [
        {
            "abreviacao": "DRE - TT",
            "codigo": "000100",
            "nome": "DIRETORIA TESTE",
            "ues": [
                {
                    "codigo": "000191",
                    "nome": "EMEF TESTE",
                    "codTipoEscola": 1,
                    "turmas": [
                        {
                            "anoLetivo": 2026,
                            "codigo": 9000001,
                            "dataFim": None,
                            "ueCodigo": "000191",
                        }
                    ],
                }
            ],
        }
    ]
}

_MSG_DRE = {"detail": "O codigo da Dre é obrigatório"}
_MSG_TURMA = {"detail": "É necessário informar ao menos uma turma"}


def _erro_http(status_code: int, corpo: bytes = b"") -> httpx.HTTPStatusError:
    requisicao = httpx.Request("GET", "https://pedagogico.teste")
    return httpx.HTTPStatusError(
        "erro",
        request=requisicao,
        response=httpx.Response(
            status_code, content=corpo, request=requisicao
        ),
    )


@override_settings(API_KEY=_API_KEY, API_KEY_HEADER="X-API-Key")
@patch.object(PedagogicoAPI, "estrutura_vigente_por_turmas")
@patch.object(PedagogicoAPI, "estrutura_vigente_por_dre")
class TestEstruturaVigenteViews(SimpleTestCase):
    """Testes de `EstruturaVigentePorDreView` e `EstruturaVigenteView`."""

    def setUp(self) -> None:
        """Prepara um client autenticado por API Key."""
        self.client = APIClient()
        self.client.credentials(HTTP_X_API_KEY=_API_KEY)

    def _post(self, corpo: Any) -> Any:
        return self.client.post(
            f"{_BASE}/estrutura-vigente", data=corpo, format="json"
        )

    def test_por_dre_devolve_a_estrutura_do_cliente(
        self, por_dre: MagicMock, _por_turmas: MagicMock
    ) -> None:
        """Garante o 200 com o `dict`, sem reescrita de tipos."""
        por_dre.return_value = _ESTRUTURA

        resposta = self.client.get(f"{_BASE}/estrutura-vigente/%20000100%20")

        por_dre.assert_called_once_with("000100")
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.json(), _ESTRUTURA)

    def test_por_turmas_envia_so_os_codigos_numericos(
        self, _por_dre: MagicMock, por_turmas: MagicMock
    ) -> None:
        """Garante `list[int]` descartando item não numérico."""
        por_turmas.return_value = _ESTRUTURA

        resposta = self._post(["123", 456, "x", " 789 ", "²"])

        por_turmas.assert_called_once_with([123, 456, 789])
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.json(), _ESTRUTURA)

    def test_sem_dre_responde_204_sem_corpo(
        self, por_dre: MagicMock, por_turmas: MagicMock
    ) -> None:
        """Garante 204, e não 200 com `dres: []`."""
        por_dre.return_value = {"dres": []}
        por_turmas.return_value = {"dres": []}

        respostas = {
            "estrutura_vigente_por_dre": self.client.get(
                f"{_BASE}/estrutura-vigente/000100"
            ),
            "estrutura_vigente_por_turmas": self._post(["123"]),
        }

        for endpoint, resposta in respostas.items():
            with self.subTest(endpoint=endpoint):
                self.assertEqual(
                    resposta.status_code, status.HTTP_204_NO_CONTENT
                )
                self.assertEqual(resposta.content, b"")

    def test_codigo_dre_em_branco_responde_400_sem_chamar(
        self, por_dre: MagicMock, _por_turmas: MagicMock
    ) -> None:
        """Garante a mensagem do legado."""
        resposta = self.client.get(f"{_BASE}/estrutura-vigente/%20")

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resposta.json(), _MSG_DRE)
        por_dre.assert_not_called()

    def test_codigo_dre_nao_numerico_responde_204_sem_chamar(
        self, por_dre: MagicMock, _por_turmas: MagicMock
    ) -> None:
        """Garante o 204 do legado sem arriscar 4xx no breaker do SDK."""
        for codigo in ["abc", "10%2E5", "-1"]:
            with self.subTest(codigo=codigo):
                resposta = self.client.get(
                    f"{_BASE}/estrutura-vigente/{codigo}"
                )

                self.assertEqual(
                    resposta.status_code, status.HTTP_204_NO_CONTENT
                )
        por_dre.assert_not_called()

    def test_corpo_sem_turma_numerica_responde_400_sem_chamar(
        self, _por_dre: MagicMock, por_turmas: MagicMock
    ) -> None:
        """Garante a mensagem do legado para corpo sem código de turma."""
        for corpo in [{}, [], ["x"], {"filtroTurmas": ["123"]}, "123"]:
            with self.subTest(corpo=corpo):
                resposta = self._post(corpo)

                self.assertEqual(
                    resposta.status_code, status.HTTP_400_BAD_REQUEST
                )
                self.assertEqual(resposta.json(), _MSG_TURMA)
        por_turmas.assert_not_called()

    def test_get_sem_codigo_responde_405(
        self, por_dre: MagicMock, por_turmas: MagicMock
    ) -> None:
        """Garante que `estrutura-vigente` só aceita POST."""
        resposta = self.client.get(f"{_BASE}/estrutura-vigente")

        self.assertEqual(
            resposta.status_code, status.HTTP_405_METHOD_NOT_ALLOWED
        )
        por_dre.assert_not_called()
        por_turmas.assert_not_called()

    def test_falha_do_upstream_responde_503(
        self, por_dre: MagicMock, por_turmas: MagicMock
    ) -> None:
        """Garante 503, circuito aberto e chave recusada."""
        falhas = [
            httpx.ConnectError("recusada"),
            _erro_http(401),
            _erro_http(403),
        ]

        for falha in falhas:
            por_dre.side_effect = falha
            por_turmas.side_effect = falha
            respostas = {
                "estrutura_vigente_por_dre": self.client.get(
                f"{_BASE}/estrutura-vigente/000100"
            ),
                "estrutura_vigente_por_turmas": self._post(["123"]),
            }
            for endpoint, resposta in respostas.items():
                with self.subTest(endpoint=endpoint, falha=repr(falha)):
                    self.assertEqual(
                        resposta.status_code,
                        status.HTTP_503_SERVICE_UNAVAILABLE,
                    )
                    self.assertEqual(
                        resposta.json(),
                        {"detail": "Serviço de pedagogico indisponível."},
                    )

    def test_erro_400_do_upstream_e_repassado(
        self, por_dre: MagicMock, por_turmas: MagicMock
    ) -> None:
        """Garante o mesmo status e retorno nas duas rotas."""
        por_dre.side_effect = _erro_http(400, b'{"detail": "invalido"}')
        por_turmas.side_effect = _erro_http(400, b'{"detail": "invalido"}')

        respostas = {
            "estrutura_vigente_por_dre": self.client.get(
                f"{_BASE}/estrutura-vigente/000100"
            ),
            "estrutura_vigente_por_turmas": self._post(["123"]),
        }

        for endpoint, resposta in respostas.items():
            with self.subTest(endpoint=endpoint):
                self.assertEqual(
                    resposta.status_code, status.HTTP_400_BAD_REQUEST
                )
                self.assertEqual(resposta.json(), {"detail": "invalido"})


@override_settings(API_KEY=_API_KEY, API_KEY_HEADER="X-API-Key")
class TestRotasNovasExigemApiKey(SimpleTestCase):
    """Garante 401 sem API Key nas rotas de API externa."""

    @patch("apps.abrangencia.api.views.PedagogicoAPI")
    @patch("apps.abrangencia.api.views.InstitucionalAPI")
    @patch("apps.abrangencia.api.views.AbrangenciaService")
    def test_sem_api_key_responde_401_sem_consultar_nada(
        self,
        service: MagicMock,
        institucional: MagicMock,
        pedagogico: MagicMock,
    ) -> None:
        """Garante que nenhuma fonte e consultada sem autenticacao."""
        client = APIClient()
        chamadas = [
            ("get", "codigos-dres"),
            ("get", "nome-abreviacao-dres"),
            ("get", "ciclo-ensino"),
            ("get", "estrutura-vigente/000100"),
            ("post", "estrutura-vigente"),
        ]

        for metodo, rota in chamadas:
            with self.subTest(rota=rota):
                resposta = getattr(client, metodo)(f"{_BASE}/{rota}")

                self.assertEqual(
                    resposta.status_code, status.HTTP_401_UNAUTHORIZED
                )
        service.assert_not_called()
        institucional.assert_not_called()
        pedagogico.assert_not_called()


_URL_MS = "http://ms.teste/dres/900100/unidades/"
_INDISPONIVEL_REDE = {"detail": "Serviço de DREs, UEs e turmas indisponível."}


def _falhas_do_ms() -> dict[str, Exception]:
    requisicao = httpx.Request("GET", _URL_MS)
    return {
        "fora do ar": httpx.ConnectError("recusada", request=requisicao),
        "erro do MS": httpx.HTTPStatusError(
            "erro",
            request=requisicao,
            response=httpx.Response(500, request=requisicao),
        ),
        "nao encontrado": httpx.HTTPStatusError(
            "erro",
            request=requisicao,
            response=httpx.Response(404, request=requisicao),
        ),
        "rede incompleta": RedeSmeIncompletaError("codigos-dres sem DRE"),
    }


@override_settings(
    API_KEY=_API_KEY, API_KEY_HEADER="X-API-Key", ABRANGENCIA_ANO_LETIVO=_ANO
)
class TestFalhaDosMsNasRotasDeEscopo(TestCase):
    """Garante 503, e nunca colecao vazia, quando um MS falha."""

    def setUp(self) -> None:
        """Prepara client e uma rede que falha em toda consulta."""
        self.client = APIClient()
        self.client.credentials(HTTP_X_API_KEY=_API_KEY)
        self.rede_sme = usar_rede_sme(self)

    def _falhar(self, erro: Exception) -> None:
        metodos = (
            "dres",
            "codigos_dres",
            "ues",
            "unidades_da_dre",
            "turmas_de_sondagem",
        )
        for metodo in metodos:
            troca = patch.object(self.rede_sme, metodo, side_effect=erro)
            troca.start()
            self.addCleanup(troca.stop)

    def test_compactas_respondem_503(self) -> None:
        """Garante 503 em E-07 a E-10 com o MS fora ou com erro.

        Lista vazia e resposta valida do contrato: o consumidor nao
        distinguiria a falha.
        """
        Perfil.objects.create(
            perfil_guid=_PERFIL_GUID,
            grupo_codigo=10,
            abrangencia_id=6,
            eh_perfil_manual=False,
        )
        rotas = [
            f"compacta-vigente/{_LOGIN}/perfil/{_PERFIL_GUID}",
            f"compacta-vigente/{_LOGIN}/perfil/{_PERFIL_GUID}/DreDetalhes",
            f"compacta-vigente/{_LOGIN}/perfil/{_PERFIL_GUID}/Sondagem",
            f"compacta-semRedis/{_LOGIN}/perfil/{_PERFIL_GUID}",
        ]

        for caso, erro in _falhas_do_ms().items():
            self._falhar(erro)
            for rota in rotas:
                with self.subTest(caso=caso, rota=rota):
                    resposta = self.client.get(f"{_BASE}/{rota}")

                    self.assertEqual(
                        resposta.status_code,
                        status.HTTP_503_SERVICE_UNAVAILABLE,
                    )
                    self.assertEqual(resposta.json(), _INDISPONIVEL_REDE)

    def test_usuarios_por_perfil_com_dre_responde_503(self) -> None:
        """Garante 503 em E-13 quando o filtro de DRE nao chega ao MS."""
        for caso, erro in _falhas_do_ms().items():
            self._falhar(erro)
            with self.subTest(caso=caso):
                resposta = self.client.post(
                    f"{_BASE}/perfis/usuarios",
                    data={
                        "ue": "900101",
                        "dre": "900100",
                        "perfis": [_PERFIL_GUID],
                    },
                    format="json",
                )

                self.assertEqual(
                    resposta.status_code, status.HTTP_503_SERVICE_UNAVAILABLE
                )

    def test_usuarios_por_perfil_sem_dre_nao_chama_o_ms(self) -> None:
        """Garante que E-13 sem DRE nao depende do MS."""
        self._falhar(httpx.ConnectError("recusada"))

        resposta = self.client.post(
            f"{_BASE}/perfis/usuarios",
            data={"ue": "900101", "perfis": [_PERFIL_GUID]},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)


_CACHE_LOCAL = {
    "default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"},
    "keydb": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "views-teste",
    },
}
_ESTRUTURA_FICTICIA = {
    "dres": [{"codigo": "900100", "nome": "DRE TESTE", "ues": []}]
}


@override_settings(
    API_KEY=_API_KEY, API_KEY_HEADER="X-API-Key", CACHES=_CACHE_LOCAL
)
class TestCacheDosRepasses(SimpleTestCase):
    """Garante o cache de E-03 e E-04, com o TTL do legado, e E-02 sem."""

    def setUp(self) -> None:
        """Prepara um client autenticado e o cache limpo."""
        self.client = APIClient()
        self.client.credentials(HTTP_X_API_KEY=_API_KEY)
        caches["keydb"].clear()
        self.addCleanup(caches["keydb"].clear)

    def test_resposta_do_cache_tem_os_bytes_do_ms(self) -> None:
        """Garante o corpo do MS byte a byte, mesmo saindo do cache.

        O cache guarda a lista JSON; a resposta dele sai compacta e sem
        escape de acento, como o corpo que o MS entrega.
        """
        corpos = {
            "dres_nome_abreviacao": (
                "nome-abreviacao-dres",
                '[{"codigo":"900100","nome":"DIRETORIA REGIONAL DE '
                'EDUCAÇÃO TESTE","abreviacao":"DRE - TÉ"}]'.encode(),
            ),
        }

        for metodo, (rota, corpo) in corpos.items():
            with (
                self.subTest(rota=rota),
                patch.object(InstitucionalAPI, metodo) as externa,
            ):
                externa.return_value = _externa(200, corpo)

                do_ms = self.client.get(f"{_BASE}/{rota}")
                do_cache = self.client.get(f"{_BASE}/{rota}")

                externa.assert_called_once()
                self.assertEqual(do_ms.content, corpo)
                self.assertEqual(do_cache.content, corpo)
                self.assertEqual(do_cache["Content-Type"], "application/json")

    def test_corpo_que_nao_e_lista_nao_entra_no_cache(self) -> None:
        """Garante que so lista JSON vai para o cache."""
        with patch.object(
            InstitucionalAPI, "dres_nome_abreviacao"
        ) as externa:
            externa.return_value = _externa(200, b'{"codigo": "1"}')

            self.client.get(f"{_BASE}/nome-abreviacao-dres")
            self.client.get(f"{_BASE}/nome-abreviacao-dres")

        self.assertEqual(externa.call_count, 2)

    def test_nome_abreviacao_vem_do_cache_na_segunda_chamada(self) -> None:
        """Garante uma so chamada ao Institucional para E-03."""
        with patch.object(
            InstitucionalAPI, "dres_nome_abreviacao"
        ) as externa:
            externa.return_value = _externa(200, _CORPO_DRES)

            primeira = self.client.get(f"{_BASE}/nome-abreviacao-dres")
            segunda = self.client.get(f"{_BASE}/nome-abreviacao-dres")

        externa.assert_called_once()
        self.assertEqual(segunda.status_code, status.HTTP_200_OK)
        self.assertEqual(segunda.json(), primeira.json())

    def test_codigos_dres_nao_tem_cache_aqui(self) -> None:
        """Garante E-02 sempre no Institucional, que ja guarda a lista.

        O MS-Institucional mantem `codigos-dres` no cache dele; uma copia
        aqui so somaria um segundo prazo de validade.
        """
        with patch.object(InstitucionalAPI, "codigos_dres") as externa:
            externa.return_value = _externa(200, _CORPO_CODIGOS_DRES)

            self.client.get(f"{_BASE}/codigos-dres")
            resposta = self.client.get(f"{_BASE}/codigos-dres")

        self.assertEqual(externa.call_count, 2)
        self.assertEqual(resposta.content, _CORPO_CODIGOS_DRES)
        self.assertIsNone(caches["keydb"].get("abrangencia:codigos-dres"))

    def test_sem_conteudo_ou_erro_nao_entra_no_cache(self) -> None:
        """Garante que 204, lista vazia e erro voltam ao MS, como no legado."""
        casos = ((204, b""), (200, b"[]"), (500, b"{}"))
        for status_externo, conteudo in casos:
            with (
                self.subTest(status=status_externo, conteudo=conteudo),
                patch.object(
                    InstitucionalAPI, "dres_nome_abreviacao"
                ) as externa,
            ):
                externa.return_value = _externa(status_externo, conteudo)

                self.client.get(f"{_BASE}/nome-abreviacao-dres")
                self.client.get(f"{_BASE}/nome-abreviacao-dres")

                self.assertEqual(externa.call_count, 2)

    @patch.object(PedagogicoAPI, "estrutura_vigente_por_dre")
    def test_estrutura_por_dre_vem_do_cache_na_segunda_chamada(
        self, externa: MagicMock
    ) -> None:
        """Garante uma so chamada ao MS-Pedagogico para a mesma DRE."""
        externa.return_value = _ESTRUTURA_FICTICIA

        primeira = self.client.get(f"{_BASE}/estrutura-vigente/900100")
        segunda = self.client.get(f"{_BASE}/estrutura-vigente/900100")

        externa.assert_called_once_with("900100")
        self.assertEqual(segunda.status_code, status.HTTP_200_OK)
        self.assertEqual(segunda.json(), primeira.json())

    @patch.object(PedagogicoAPI, "estrutura_vigente_por_dre")
    def test_estrutura_sem_dre_nao_entra_no_cache(
        self, externa: MagicMock
    ) -> None:
        """Garante que o 204 de E-04 nao fica guardado."""
        externa.return_value = {"dres": []}

        for _ in range(2):
            resposta = self.client.get(f"{_BASE}/estrutura-vigente/900100")
            self.assertEqual(resposta.status_code, status.HTTP_204_NO_CONTENT)

        self.assertEqual(externa.call_count, 2)


@override_settings(
    API_KEY=_API_KEY, API_KEY_HEADER="X-API-Key", CACHES=_CACHE_LOCAL
)
class TestCacheDoPerfil(TestCase):
    """Garante o cache de E-01, com o TTL do legado."""

    def setUp(self) -> None:
        """Prepara um client autenticado e o cache limpo."""
        self.client = APIClient()
        self.client.credentials(HTTP_X_API_KEY=_API_KEY)
        caches["keydb"].clear()
        self.addCleanup(caches["keydb"].clear)

    def test_perfil_vem_do_cache_na_segunda_chamada(self) -> None:
        """Garante uma so consulta ao banco para o mesmo perfil. """
        with patch(
            "apps.abrangencia.api.views.AbrangenciaService.grupo_cargos",
            autospec=True,
            side_effect=lambda servico, guid: {"grupoID": guid},
        ) as consulta:
            primeira = self.client.get(f"{_BASE}/{_PERFIL_GUID}")
            segunda = self.client.get(f"{_BASE}/{_PERFIL_GUID.upper()}")

        consulta.assert_called_once()
        self.assertEqual(segunda.status_code, status.HTTP_200_OK)
        self.assertEqual(segunda.json(), primeira.json())

    def test_perfil_inexistente_nao_entra_no_cache(self) -> None:
        """Garante que o 204 volta ao banco na proxima chamada."""
        with patch(
            "apps.abrangencia.api.views.AbrangenciaService.grupo_cargos",
            return_value=None,
        ) as consulta:
            for _ in range(2):
                resposta = self.client.get(f"{_BASE}/{_PERFIL_GUID}")
                self.assertEqual(
                    resposta.status_code, status.HTTP_204_NO_CONTENT
                )

        self.assertEqual(consulta.call_count, 2)

    def test_guid_invalido_nao_consulta_o_cache(self) -> None:
        """Garante o 400 antes de qualquer leitura de cache ou banco."""
        with patch(
            "apps.abrangencia.api.views.PerfilCacheRepository"
        ) as repositorio:
            resposta = self.client.get(
                f"{_BASE}/00000000-0000-0000-0000-000000000000"
            )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        repositorio.assert_not_called()
