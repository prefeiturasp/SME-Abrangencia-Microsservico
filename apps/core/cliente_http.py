"""Cliente HTTP para APIs externas."""

from typing import Any, cast

import httpx
from django.conf import settings
from sme_sidecar_sdk import CircuitOpenError, build_http_client
from sme_sidecar_sdk.http import SyncHTTPClient

HEADER_API_KEY = "X-API-Key"


class ClienteServico:
    """Chama uma API externa enviando a chave deste serviço.

    Timeout, retry e circuit breaker vêm do cliente do SDK. Resposta 4xx
    ou 5xx chega como `httpx.HTTPStatusError`.

    Args:
        base_url: URL base da API externa.
        dominio: Nome lógico da API, usado no breaker e nos logs.
        api_key: Chave enviada em `X-API-Key`; vazia não envia o header.
    """

    def __init__(self, base_url: str, dominio: str, api_key: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.dominio = dominio
        self._api_key = api_key
        self._cliente: SyncHTTPClient | None = None

    def get(self, path: str) -> httpx.Response:
        """Executa um GET no caminho relativo à URL base."""
        try:
            return cast(
                httpx.Response,
                self._http().get(path, headers=self._headers()),
            )
        except CircuitOpenError as exc:
            raise self._indisponivel("GET", path) from exc

    def post(self, path: str, payload: Any = None) -> httpx.Response:
        """Executa um POST com `payload` como corpo JSON."""
        try:
            return cast(
                httpx.Response,
                self._http().post(path, headers=self._headers(), json=payload),
            )
        except CircuitOpenError as exc:
            raise self._indisponivel("POST", path) from exc

    def fechar(self) -> None:
        """Fecha as conexões mantidas pelo cliente."""
        if self._cliente is not None:
            self._cliente.close()
            self._cliente = None

    def _http(self) -> SyncHTTPClient:
        if self._cliente is None:
            self._cliente = build_http_client(
                self.dominio,
                base_url=self.base_url,
                follow_redirects=True,
            )
        return self._cliente

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._api_key:
            headers[HEADER_API_KEY] = self._api_key
        return headers

    def _indisponivel(self, metodo: str, path: str) -> httpx.ConnectError:
        return httpx.ConnectError(
            f"Circuit breaker aberto para {self.dominio}",
            request=httpx.Request(metodo, f"{self.base_url}{path}"),
        )


_clientes: dict[str, ClienteServico] = {}


def obter_cliente(nome: str) -> ClienteServico:
    """Devolve o cliente da API `nome`, configurada em `APIS_EXTERNAS`.

    O cliente nasce na primeira chamada, com os settings daquele momento,
    e é reaproveitado nas seguintes.
    """
    if nome not in _clientes:
        config = settings.APIS_EXTERNAS[nome]
        _clientes[nome] = ClienteServico(
            base_url=config["URL"],
            dominio=nome,
            api_key=config["API_KEY"],
        )
    return _clientes[nome]


def fechar_clientes() -> None:
    """Fecha e descarta os clientes criados até aqui."""
    for cliente in _clientes.values():
        cliente.fechar()
    _clientes.clear()
