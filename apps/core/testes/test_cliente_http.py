"""Testes do cliente HTTP de APIs externas."""

from unittest.mock import MagicMock, patch

import httpx
from django.test import SimpleTestCase, override_settings
from sme_sidecar_sdk import CircuitOpenError

from apps.core.cliente_http import (
    ClienteServico,
    fechar_clientes,
    obter_cliente,
)

_BASE_URL = "https://api-externa.teste"


def _cliente(api_key: str = "") -> ClienteServico:
    return ClienteServico(
        base_url=f"{_BASE_URL}/",
        dominio="externa",
        api_key=api_key,
    )


@patch("apps.core.cliente_http.build_http_client")
class TestClienteServico(SimpleTestCase):
    """Testes de `ClienteServico`."""

    def test_get_usa_path_relativo_e_envia_a_chave(
        self, build: MagicMock
    ) -> None:
        """Garante o path relativo à URL base e a chave em `X-API-Key`."""
        _cliente(api_key="segredo").get("/recurso/")

        build.assert_called_once_with(
            "externa", base_url=_BASE_URL, follow_redirects=True
        )
        build.return_value.get.assert_called_once_with(
            "/recurso/",
            headers={"Accept": "application/json", "X-API-Key": "segredo"},
        )

    def test_post_envia_payload_como_json(self, build: MagicMock) -> None:
        """Garante que o payload vai como corpo JSON, sem transformação."""
        _cliente(api_key="segredo").post("/recurso/", payload=["1", "abc"])

        build.return_value.post.assert_called_once_with(
            "/recurso/",
            headers={"Accept": "application/json", "X-API-Key": "segredo"},
            json=["1", "abc"],
        )

    def test_sem_chave_nao_envia_o_header(self, build: MagicMock) -> None:
        """Garante que chave vazia não vira header vazio."""
        _cliente().get("/recurso/")

        build.return_value.get.assert_called_once_with(
            "/recurso/", headers={"Accept": "application/json"}
        )

    def test_reaproveita_o_cliente_do_sdk(self, build: MagicMock) -> None:
        """Garante um único cliente do SDK por `ClienteServico`."""
        cliente = _cliente()

        cliente.get("/a/")
        cliente.post("/b/")

        build.assert_called_once()

    def test_circuito_aberto_vira_erro_de_conexao(
        self, build: MagicMock
    ) -> None:
        """Garante que circuito aberto chega à view como falha de rede.

        A view base trata `httpx.RequestError` como indisponibilidade.
        """
        for metodo in ["get", "post"]:
            with self.subTest(metodo=metodo):
                chamada = getattr(build.return_value, metodo)
                chamada.side_effect = CircuitOpenError()

                with self.assertRaises(httpx.ConnectError) as erro:
                    getattr(_cliente(), metodo)("/recurso/")

                self.assertEqual(
                    erro.exception.request.url, f"{_BASE_URL}/recurso/"
                )

    def test_fechar_descarta_o_cliente_do_sdk(self, build: MagicMock) -> None:
        """Garante que o próximo uso após `fechar` cria outro cliente."""
        cliente = _cliente()
        cliente.get("/a/")

        cliente.fechar()
        cliente.get("/a/")

        build.return_value.close.assert_called_once_with()
        self.assertEqual(build.call_count, 2)

    def test_fechar_sem_uso_nao_falha(self, build: MagicMock) -> None:
        """Garante que fechar um cliente nunca usado não cria conexão."""
        _cliente().fechar()

        build.assert_not_called()


_APIS = {
    "externa": {
        "URL": "https://externa.teste",
        "API_KEY": "chave-externa",
    },
    "outra": {
        "URL": "https://outra.teste",
        "API_KEY": "",
    },
}


class TestRegistroDeClientes(SimpleTestCase):
    """Testes de `obter_cliente` e `fechar_clientes`."""

    def setUp(self) -> None:
        fechar_clientes()
        self.addCleanup(fechar_clientes)

    @override_settings(APIS_EXTERNAS=_APIS)
    def test_cada_api_usa_a_propria_configuracao(self) -> None:
        """Garante URL e chave de cada entrada de APIS_EXTERNAS."""
        externa = obter_cliente("externa")
        outra = obter_cliente("outra")

        self.assertEqual(
            (externa.base_url, externa.dominio),
            ("https://externa.teste", "externa"),
        )
        self.assertEqual(externa._headers()["X-API-Key"], "chave-externa")
        self.assertEqual(
            (outra.base_url, outra.dominio),
            ("https://outra.teste", "outra"),
        )
        self.assertEqual(outra._headers(), {"Accept": "application/json"})

    @override_settings(APIS_EXTERNAS=_APIS)
    def test_reaproveita_o_cliente_por_nome(self) -> None:
        """Garante um cliente por API, e não um por requisição."""
        self.assertIs(obter_cliente("externa"), obter_cliente("externa"))

    def test_fechar_clientes_rele_os_settings(self) -> None:
        """Garante que, depois de fechar, o cliente nasce com a URL nova."""
        antiga = {"externa": {**_APIS["externa"], "URL": "https://antiga"}}
        nova = {"externa": {**_APIS["externa"], "URL": "https://nova"}}
        with override_settings(APIS_EXTERNAS=antiga):
            antigo = obter_cliente("externa")

        fechar_clientes()
        with override_settings(APIS_EXTERNAS=nova):
            novo = obter_cliente("externa")

        self.assertEqual(antigo.base_url, "https://antiga")
        self.assertEqual(novo.base_url, "https://nova")

    @override_settings(APIS_EXTERNAS=_APIS)
    def test_api_nao_configurada_falha_na_hora(self) -> None:
        """Garante erro explícito para nome fora de APIS_EXTERNAS."""
        with self.assertRaises(KeyError):
            obter_cliente("desconhecida")
