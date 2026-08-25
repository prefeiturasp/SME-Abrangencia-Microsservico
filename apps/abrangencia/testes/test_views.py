"""Testes das views do domínio Abrangência."""

from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.abrangencia.models import AbrangenciaCompacta, Perfil

_API_KEY = "chave-de-teste"
_PERFIL_GUID = "2e89cf10-e42b-476f-8673-2dfbeeee3cd0"


@override_settings(API_KEY=_API_KEY, API_KEY_HEADER="X-API-Key")
class TestPerfilView(TestCase):
    """Testes de `PerfilView`."""

    def setUp(self) -> None:
        """Prepara um client autenticado por API Key."""
        self.client = APIClient()
        self.client.credentials(HTTP_X_API_KEY=_API_KEY)

    def test_sem_api_key_retorna_401(self) -> None:
        """Requisição sem API Key é recusada."""
        client_sem_chave = APIClient()

        resposta = client_sem_chave.get(f"/abrangencia/api/v1/{_PERFIL_GUID}")

        self.assertEqual(resposta.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_guid_vazio_retorna_400(self) -> None:
        """GUID vazio/malformado é recusado antes de qualquer consulta."""
        resposta = self.client.get(
            "/abrangencia/api/v1/00000000-0000-0000-0000-000000000000"
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_perfil_inexistente_retorna_204(self) -> None:
        """Perfil sem registro não é erro: responde sem corpo."""
        resposta = self.client.get(f"/abrangencia/api/v1/{_PERFIL_GUID}")

        self.assertEqual(resposta.status_code, status.HTTP_204_NO_CONTENT)

    def test_perfil_existente_retorna_200_com_o_grupo_cargos(self) -> None:
        """Perfil existente devolve o `GrupoCargosDTO`."""
        Perfil.objects.create(
            perfil_guid=_PERFIL_GUID,
            grupo_codigo=10,
            tipo_abrangencia=1,
            eh_perfil_manual=False,
        )

        resposta = self.client.get(f"/abrangencia/api/v1/{_PERFIL_GUID}")

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.json()["grupoID"], _PERFIL_GUID)


@override_settings(
    API_KEY=_API_KEY, API_KEY_HEADER="X-API-Key", ABRANGENCIA_ANO_LETIVO=2026
)
class TestCompactaVigenteView(TestCase):
    """Testes de `CompactaVigenteView`."""

    def setUp(self) -> None:
        """Prepara um client autenticado por API Key."""
        self.client = APIClient()
        self.client.credentials(HTTP_X_API_KEY=_API_KEY)

    def test_guid_invalido_retorna_400(self) -> None:
        """GUID malformado é recusado antes de consultar o escopo."""
        resposta = self.client.get(
            "/abrangencia/api/v1/compacta-vigente/5059151/perfil/nao-e-guid"
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_usuario_sem_escopo_retorna_200_com_forma_do_ramo(self) -> None:
        """Usuário sem linha na MV não é erro."""
        Perfil.objects.create(
            perfil_guid=_PERFIL_GUID,
            grupo_codigo=10,
            tipo_abrangencia=1,
            eh_perfil_manual=False,
        )

        resposta = self.client.get(
            f"/abrangencia/api/v1/compacta-vigente/999999/perfil/{_PERFIL_GUID}"
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.json()["login"], "999999")

    def test_usuario_com_escopo_retorna_ues_do_ramo(self) -> None:
        """Usuário com escopo na MV devolve `idUes` no ramo UE."""
        Perfil.objects.create(
            perfil_guid=_PERFIL_GUID,
            grupo_codigo=10,
            tipo_abrangencia=1,
            eh_perfil_manual=False,
        )
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
            id_ues_detalhaveis=[],
        )

        resposta = self.client.get(
            f"/abrangencia/api/v1/compacta-vigente/5059151/perfil/{_PERFIL_GUID}"
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        corpo = resposta.json()
        self.assertEqual(corpo["idUes"], ["019331"])
        self.assertIsNone(corpo["idDres"])


@override_settings(API_KEY=_API_KEY, API_KEY_HEADER="X-API-Key")
class TestPerfisUsuariosView(TestCase):
    """Testes de `PerfisUsuariosView`."""

    def setUp(self) -> None:
        """Prepara um client autenticado por API Key."""
        self.client = APIClient()
        self.client.credentials(HTTP_X_API_KEY=_API_KEY)

    def test_corpo_invalido_retorna_400(self) -> None:
        """Corpo sem `ue`/`perfis` é recusado."""
        resposta = self.client.post(
            "/abrangencia/api/v1/perfis/usuarios", data={}, format="json"
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_corpo_valido_sem_usuarios_retorna_lista_vazia(self) -> None:
        """Corpo válido sem usuários lotados devolve `[]`."""
        resposta = self.client.post(
            "/abrangencia/api/v1/perfis/usuarios",
            data={"ue": "019331", "perfis": [_PERFIL_GUID]},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.json(), [])
