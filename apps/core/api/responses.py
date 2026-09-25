"""Fábricas de respostas HTTP reutilizáveis."""

from typing import Any

import httpx
from django.http import HttpResponse
from rest_framework.response import Response

__all__ = [
    "resposta_detalhe",
    "resposta_erro_status_livre",
    "resposta_externa",
    "resposta_indisponivel",
    "sem_conteudo",
]


def resposta_externa(resposta: httpx.Response) -> HttpResponse:
    """Devolve o retorno da API externa com o mesmo status."""
    return HttpResponse(
        resposta.content,
        status=resposta.status_code,
        content_type="application/json",
    )


def sem_conteudo(resposta: httpx.Response) -> bool:
    """Informa se a API externa respondeu 204, sem retorno ou com JSON vazio.

    Retorno que não é JSON conta como conteúdo.
    """
    if resposta.status_code == 204 or not resposta.content:
        return True
    try:
        return not resposta.json()
    except ValueError:
        return False


def resposta_indisponivel(dominio: str, status_code: int = 503) -> Response:
    """Retorna resposta padronizada para API temporariamente indisponível."""
    return resposta_detalhe(f"Serviço de {dominio} indisponível.", status_code)


def resposta_detalhe(detalhe: str, status_code: int = 400) -> Response:
    """Retorna uma resposta padronizada com campo `detail`."""
    return Response({"detail": detalhe}, status=status_code)


def resposta_erro_status_livre(exc: httpx.HTTPStatusError) -> Response:
    """Monta resposta de erro preservando status fora do intervalo padrão.
    
    Args:
        exc: Exceção HTTP lançada pelo cliente externo.

    Returns:
        Resposta com o corpo e o status originais da API.
    """
    try:
        corpo: Any = exc.response.json()
    except ValueError:
        detalhe = exc.response.text.strip() or exc.response.reason_phrase
        corpo = {"detail": detalhe}
    resposta = Response(corpo, status=400)
    resposta.status_code = exc.response.status_code
    return resposta
