"""Testes da views do módulo core."""

import ast
from pathlib import Path

import httpx
from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.test import APIClient, APIRequestFactory

from apps.core.api import views
from apps.core.api.views import APIExternaView


class TestHealthCheckView(SimpleTestCase):
    """Testes da view HealthCheckView."""

    def test_deve_retornar_aplicacao_saudavel(self) -> None:
        """Deve retornar o status de saúde da aplicação, sem autenticação."""
        client = APIClient()

        response = client.get(reverse("health-check"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"status": "healthy"})

    def test_responde_em_health_sob_o_prefixo_do_dominio(self) -> None:
        """Garante o caminho `/api/abrangencia/health/`."""
        client = APIClient()

        response = client.get("/api/abrangencia/health/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"status": "healthy"})


def _erro_http(status_code: int, **kwargs: object) -> httpx.HTTPStatusError:
    requisicao = httpx.Request("GET", "https://api-externa.teste/recurso/")
    resposta = httpx.Response(status_code, request=requisicao, **kwargs)
    return httpx.HTTPStatusError("erro", request=requisicao, response=resposta)


class _ViewQueFalha(APIExternaView):
    authentication_classes = []
    permission_classes = []
    dominio = "externa"
    erro: Exception = Exception()

    def get(self, _request: Request) -> Response:
        raise self.erro


def _chamar(erro: Exception) -> Response:
    view = _ViewQueFalha.as_view(erro=erro)
    return view(APIRequestFactory().get("/"))


class TestAPIExternaView(SimpleTestCase):
    """Testes de `APIExternaView.handle_exception`."""

    def test_falha_de_rede_responde_503(self) -> None:
        """Garante 503 com `detail` para API fora do ar ou lenta."""
        erros = [httpx.ConnectError("recusada"), httpx.ReadTimeout("expirou")]
        for erro in erros:
            with self.subTest(erro=erro):
                resposta = _chamar(erro)

                self.assertEqual(
                    resposta.status_code, status.HTTP_503_SERVICE_UNAVAILABLE
                )
                self.assertEqual(
                    resposta.data,
                    {"detail": "Serviço de externa indisponível."},
                )

    def test_chave_recusada_responde_503(self) -> None:
        """Garante que 401/403 da API externa não chegam ao consumidor."""
        for status_code in [401, 403]:
            with self.subTest(status_code=status_code):
                resposta = _chamar(_erro_http(status_code))

                self.assertEqual(
                    resposta.status_code, status.HTTP_503_SERVICE_UNAVAILABLE
                )
                self.assertEqual(
                    resposta.data,
                    {"detail": "Serviço de externa indisponível."},
                )

    def test_demais_erros_repetem_status_e_corpo(self) -> None:
        """Garante que outro 4xx ou 5xx sai com o status da API externa."""
        for status_code in [400, 404, 500]:
            with self.subTest(status_code=status_code):
                resposta = _chamar(
                    _erro_http(status_code, json={"detail": "erro"})
                )

                self.assertEqual(resposta.status_code, status_code)
                self.assertEqual(resposta.data, {"detail": "erro"})

    def test_outra_excecao_segue_o_tratamento_do_drf(self) -> None:
        """Garante que erro de validação continua 400 do DRF."""
        resposta = _chamar(ValidationError({"campo": ["invalido"]}))

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resposta.data, {"campo": ["invalido"]})


class TestFronteiraDoNucleo(SimpleTestCase):
    """Testes da fronteira entre núcleo e domínio."""

    def test_nucleo_nao_importa_o_dominio(self) -> None:
        """Garante que as peças do núcleo não conhecem o domínio."""
        modulos = ["api/responses.py", "api/views.py", "cliente_http.py"]
        for modulo in modulos:
            with self.subTest(modulo=modulo):
                caminho = Path(views.__file__).resolve().parents[1] / modulo
                arvore = ast.parse(caminho.read_text(encoding="utf-8"))

                importados = {
                    no.module or ""
                    for no in ast.walk(arvore)
                    if isinstance(no, ast.ImportFrom)
                } | {
                    alias.name
                    for no in ast.walk(arvore)
                    if isinstance(no, ast.Import)
                    for alias in no.names
                }

                self.assertFalse(
                    any(
                        nome.startswith("apps.abrangencia")
                        for nome in importados
                    )
                )
