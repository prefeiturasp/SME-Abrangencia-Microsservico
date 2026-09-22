"""Testes das views do dominio Abrangencia."""

from django.test import TestCase, override_settings
from django.urls import Resolver404, resolve
from rest_framework import status
from rest_framework.test import APIClient

from apps.abrangencia.api.views import (
    CompactaDreDetalhesView,
    CompactaSemRedisView,
    CompactaSondagemView,
    CompactaVigenteView,
)
from apps.abrangencia.models import Perfil, UsuarioPorPerfil
from apps.abrangencia.testes.helpers import (
    criar_escopo,
    criar_unidade,
)

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
        }

        for nome, (caminho, linha_legado) in esperado.items():
            with self.subTest(rota=nome, legado=linha_legado):
                self.assertEqual(resolve(caminho).url_name, nome)

    def test_rota_com_barra_final_nao_resolve(self) -> None:
        """Garante que a barra final nao e aceita, como no legado."""
        with self.assertRaises(Resolver404):
            resolve(f"{_BASE}/perfis/usuarios/")


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
            tipo_abrangencia=1,
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
            tipo_abrangencia=1,
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
        criar_escopo(tipo_escopo="UE", ue_codigo="019331")

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
            tipo_abrangencia=1,
            eh_perfil_manual=False,
        )
        criar_escopo(
            tipo_resolucao="COMPACTA", tipo_escopo="UE", ue_codigo="019331"
        )
        criar_escopo(
            tipo_resolucao="DETALHES", tipo_escopo="UE", ue_codigo="094811"
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
            tipo_abrangencia=6
        )
        criar_escopo(
            tipo_resolucao="DETALHES", tipo_escopo="DRE", dre_codigo="108100"
        )
        criar_unidade(
            tipo_escopo="DRE",
            codigo="108100",
            nome="DRE Ipiranga",
            sigla="IP",
        )

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
        self.client = APIClient()
        self.client.credentials(HTTP_X_API_KEY=_API_KEY)
        Perfil.objects.create(
            perfil_guid=_PERFIL_GUID,
            grupo_codigo=6,
            tipo_abrangencia=2,
            eh_perfil_manual=False,
        )

    def test_tipo_professor_expande_so_turmas(self) -> None:
        """Tipo Professor expande somente turmas."""
        criar_escopo(
            tipo_resolucao="DETALHES", tipo_escopo="TURMA", turma_codigo="1234"
        )
        criar_unidade(
            tipo_escopo="TURMA",
            codigo="1234",
            nome="1o Ano A",
            ue_codigo_pai="019331",
            elegivel_sondagem=True,
        )

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
            tipo_resolucao="DETALHES", tipo_escopo="TURMA", turma_codigo="9999"
        )
        criar_unidade(
            tipo_escopo="TURMA", codigo="9999", elegivel_sondagem=False
        )

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
        self.client = APIClient()
        self.client.credentials(HTTP_X_API_KEY=_API_KEY)
        Perfil.objects.create(
            perfil_guid=_PERFIL_GUID,
            grupo_codigo=10,
            tipo_abrangencia=1,
            eh_perfil_manual=False,
        )

    def test_colecoes_expandidas_trazem_atributos_da_mv(self) -> None:
        """Garante nome, sigla e pai preenchidos, e `dres` vinda das UEs."""
        criar_escopo(
            tipo_resolucao="DETALHES", tipo_escopo="UE", ue_codigo="019331"
        )
        criar_unidade(
            codigo="019331",
            nome="EMEF Teste",
            sigla="EMEF T",
            dre_codigo_pai="108100",
        )
        criar_unidade(
            tipo_escopo="DRE",
            codigo="108100",
            nome="DRE Ipiranga",
            sigla="IP",
        )

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
        criar_unidade(codigo="019331", dre_codigo_pai="108100")
        criar_unidade(codigo="094811", dre_codigo_pai="108100")

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
            dre_codigo="108100",
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
                dre_codigo="108100" if ue else "",
            )
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
