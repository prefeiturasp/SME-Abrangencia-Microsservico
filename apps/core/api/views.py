"""Views da API da aplicação core."""

import logging
from typing import cast

import httpx
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.api.responses import (
    resposta_erro_status_livre,
    resposta_indisponivel,
)
from apps.core.api.serializers import HealthStatusSerializer

logger = logging.getLogger(__name__)

_TAG = ["Core"]

_STATUS_DA_CHAVE = frozenset({401, 403})


@extend_schema(
    tags=_TAG,
    summary="Health Check",
    description="Verifica se a aplicação está disponível.",
    auth=[],
    responses={
        200: HealthStatusSerializer,
    },
)
class HealthCheckView(APIView):
    """Disponibiliza o endpoint de verificação de saúde da aplicação."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        serializer = HealthStatusSerializer(
            {"status": "healthy"},
        )

        return Response(serializer.data)


class APIExternaView(APIView):
    """Base das views que respondem com dados de uma API externa."""

    dominio: str = ""

    def handle_exception(self, exc: Exception) -> Response:
        if isinstance(exc, httpx.RequestError):
            return resposta_indisponivel(self.dominio)
        if isinstance(exc, httpx.HTTPStatusError):
            if exc.response.status_code in _STATUS_DA_CHAVE:
                logger.warning(
                    "API %s recusou a chave deste serviço (status %s)",
                    self.dominio,
                    exc.response.status_code,
                )
                return resposta_indisponivel(self.dominio)
            return resposta_erro_status_livre(exc)
        return cast(Response, super().handle_exception(exc))
