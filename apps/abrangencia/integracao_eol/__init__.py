"""Clientes das APIs IntegracaoEOL."""

from apps.abrangencia.integracao_eol.institucional import InstitucionalAPI
from apps.abrangencia.integracao_eol.pedagogico import PedagogicoAPI

__all__ = ["InstitucionalAPI", "PedagogicoAPI"]
