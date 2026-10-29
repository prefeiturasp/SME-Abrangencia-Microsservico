"""DREs e UEs, servidas pelo SME-IntegracaoEOL-Institucional-Microsservico."""

from typing import Any

import httpx

from apps.core.api.responses import lista
from apps.core.cliente_http import ClienteServico, obter_cliente


class InstitucionalAPI:
    """Chamadas ao SME-IntegracaoEOL-Institucional-Microsservico."""

    nome = "institucional"

    _PATH_CODIGOS_DRES = "/abrangencia/codigos-dres/"
    _PATH_NOME_ABREVIACAO_DRES = "/abrangencia/nome-abreviacao-dres/"
    _PATH_DRES = "/dres/"
    _PATH_ESCOLAS = "/escolas/"
    _PATH_UNIDADES_DA_DRE = "/dres/{dre}/unidades/"

    def __init__(self, cliente: ClienteServico | None = None) -> None:
        self._cliente = cliente or obter_cliente(self.nome)

    def codigos_dres(self) -> httpx.Response:
        """Busca os códigos das DREs da rede."""
        return self._cliente.get(self._PATH_CODIGOS_DRES)

    def dres_nome_abreviacao(self) -> httpx.Response:
        """Busca as DREs da rede com nome e abreviação."""
        return self._cliente.get(self._PATH_NOME_ABREVIACAO_DRES)

    def dres(self, codigos: list[str]) -> list[dict[str, Any]]:
        """Busca `codigoDRE`, `nomeDRE` e `siglaDRE` das DREs informadas."""
        return lista(self._cliente.post(self._PATH_DRES, payload=codigos))

    def escolas(self, codigos: list[str]) -> list[dict[str, Any]]:
        """Busca nome, DRE e tipo de escola das UEs informadas."""
        return lista(self._cliente.post(self._PATH_ESCOLAS, payload=codigos))

    def unidades_da_dre(self, dre: str) -> list[dict[str, Any]]:
        """Busca as unidades de uma DRE, com `codigoEol` e `nomeNaoOficial`."""
        path = self._PATH_UNIDADES_DA_DRE.format(dre=dre)
        return lista(self._cliente.get(path))
