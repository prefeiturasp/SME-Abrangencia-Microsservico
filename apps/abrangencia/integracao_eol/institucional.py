"""DREs da rede, servidas pelo SME-IntegracaoEOL-Institucional-Microsservico."""

import httpx

from apps.core.cliente_http import ClienteServico, obter_cliente


class InstitucionalAPI:
    """Chamadas ao SME-IntegracaoEOL-Institucional-Microsservico."""

    nome = "institucional"

    _PATH_CODIGOS_DRES = "/abrangencia/codigos-dres/"
    _PATH_NOME_ABREVIACAO_DRES = "/abrangencia/nome-abreviacao-dres/"

    def __init__(self, cliente: ClienteServico | None = None) -> None:
        self._cliente = cliente or obter_cliente(self.nome)

    def codigos_dres(self) -> httpx.Response:
        """Busca os códigos das DREs da rede."""
        return self._cliente.get(self._PATH_CODIGOS_DRES)

    def dres_nome_abreviacao(self) -> httpx.Response:
        """Busca as DREs da rede com nome e abreviação."""
        return self._cliente.get(self._PATH_NOME_ABREVIACAO_DRES)
