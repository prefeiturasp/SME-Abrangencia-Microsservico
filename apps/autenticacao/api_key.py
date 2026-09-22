"""Autenticação por API Key para os endpoints do domínio Abrangência.

Mesmo padrão usado nos demais microsserviços da plataforma
SME-Identidade, para manter um único mecanismo de autenticação de
serviço a serviço.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import IsAuthenticated

if TYPE_CHECKING:
    from rest_framework.request import Request


class _UsuarioApiKey:
    """Representação mínima de usuário autenticado por API Key."""

    is_authenticated = True
    is_active = True
    is_staff = False
    is_anonymous = False

    def __str__(self) -> str:
        return "api-user"


class AutenticacaoApiKey(BaseAuthentication):
    """Autentica requisições via API Key no header configurado.

    A chave é comparada com ``settings.API_KEY``.
    O header utilizado é definido por ``settings.API_KEY_HEADER``.
    """

    def authenticate(
        self, request: Request
    ) -> tuple[_UsuarioApiKey, None] | None:
        """Retorna `None` sem header outro backend pode tentar depois.

        Raises:
            AuthenticationFailed: Header presente com chave inválida.
        """
        header = settings.API_KEY_HEADER.upper().replace("-", "_")
        chave = request.META.get(f"HTTP_{header}", "")
        if not chave:
            return None
        if chave != settings.API_KEY:
            raise AuthenticationFailed("API Key inválida.")
        return (_UsuarioApiKey(), None)

    def authenticate_header(self, request: Request) -> str:
        """Retorna o nome do header de autenticação esperado."""
        return settings.API_KEY_HEADER  # type: ignore[no-any-return]


PermissaoApiKey = IsAuthenticated
