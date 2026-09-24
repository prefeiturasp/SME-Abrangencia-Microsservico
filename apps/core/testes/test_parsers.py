"""Testes dos parsers de JSON do core."""

import pytest
from rest_framework import status
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from apps.core.api.parsers import ParserJsonPatch, ParserTextJson

_CORPO = '{"chave": "valor", "itens": [1, 2]}'


class _EcoView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        return Response(request.data)


def _post(corpo: str, content_type: str) -> Response:
    requisicao = APIRequestFactory().post(
        "/eco", data=corpo, content_type=content_type
    )
    return _EcoView.as_view()(requisicao)


class TestParsers:
    """Testes de `ParserTextJson` e `ParserJsonPatch`."""

    def test_cada_parser_declara_o_seu_media_type(self) -> None:
        """Garante os content-types aceitos pela API legada."""
        assert ParserTextJson.media_type == "text/json"
        assert ParserJsonPatch.media_type == "application/json-patch+json"

    def test_parsers_herdam_de_json_parser(self) -> None:
        """Garante a herança de `JSONParser`.

        O `Request` do DRF só relê o corpo a partir de `request.body` para
        parsers que sejam `JSONParser` ou `FormParser`.
        """
        assert issubclass(ParserTextJson, JSONParser)
        assert issubclass(ParserJsonPatch, JSONParser)

    @pytest.mark.parametrize(
        "content_type",
        [
            "application/json",
            "text/json",
            "application/json-patch+json",
            "text/json; charset=utf-8",
        ],
    )
    def test_content_type_aceito_e_lido_como_json(
        self, content_type: str
    ) -> None:
        """Garante que os três content-types produzem o mesmo corpo."""
        resposta = _post(_CORPO, content_type)

        assert resposta.status_code == status.HTTP_200_OK
        assert resposta.data == {"chave": "valor", "itens": [1, 2]}

    @pytest.mark.parametrize(
        "content_type",
        [
            "text/plain",
            "application/xml",
            "application/x-www-form-urlencoded",
            "application/vnd.qualquer+json",
        ],
    )
    def test_content_type_fora_da_lista_responde_415(
        self, content_type: str
    ) -> None:
        """Garante que a lista é ampliada, não aberta.

        `application/vnd.qualquer+json` também recusa: o coringa
        `application/*+json` do legado não é reproduzido.
        """
        resposta = _post(_CORPO, content_type)

        assert (
            resposta.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
        )

    @pytest.mark.parametrize(
        "content_type", ["text/json", "application/json-patch+json"]
    )
    def test_corpo_mal_formado_responde_400(self, content_type: str) -> None:
        """Garante 400, e não 500, para JSON inválido."""
        resposta = _post('{"chave": ', content_type)

        assert resposta.status_code == status.HTTP_400_BAD_REQUEST
