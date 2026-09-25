"""Catálogo de ciclos de ensino, servido pelo SME-IntegracaoEOL-Pedagogico-Microsservico."""

import httpx

from apps.core.cliente_http import ClienteServico, obter_cliente


class PedagogicoAPI:
    """Chamadas ao SME-IntegracaoEOL-Pedagogico-Microsservico."""

    nome = "pedagogico"

    _PATH_CICLO_ENSINO = "/abrangencia/ciclo-ensino/"

    def __init__(self, cliente: ClienteServico | None = None) -> None:
        self._cliente = cliente or obter_cliente(self.nome)

    def ciclos_ensino(self) -> httpx.Response:
        """Busca o catálogo de ciclos de ensino."""
        return self._cliente.get(self._PATH_CICLO_ENSINO)
