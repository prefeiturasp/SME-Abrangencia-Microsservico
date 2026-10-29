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
        """Busca os códigos das DREs da rede.

        Returns:
            A resposta do Institucional, sem tratamento do corpo.

        Raises:
            httpx.HTTPStatusError: O Institucional respondeu 4xx ou 5xx.
            httpx.ConnectError: O Institucional está fora do ar ou com o
                circuit breaker aberto.
        """
        return self._cliente.get(self._PATH_CODIGOS_DRES)

    def dres_nome_abreviacao(self) -> httpx.Response:
        """Busca as DREs da rede com nome e abreviação.

        Returns:
            A resposta do Institucional, sem tratamento do corpo.

        Raises:
            httpx.HTTPStatusError: O Institucional respondeu 4xx ou 5xx.
            httpx.ConnectError: O Institucional está fora do ar ou com o
                circuit breaker aberto.
        """
        return self._cliente.get(self._PATH_NOME_ABREVIACAO_DRES)

    def dres(self, codigos: list[str]) -> list[dict[str, Any]]:
        """Busca nome e sigla das DREs informadas.

        Args:
            codigos: Códigos EOL das DREs.

        Returns:
            DRE encontrada, com `codigoDRE`, `nomeDRE` e
            `siglaDRE`; `[]` quando o Institucional responde sem conteúdo.

        Raises:
            httpx.HTTPStatusError: O Institucional respondeu 4xx ou 5xx.
            httpx.ConnectError: O Institucional está fora do ar ou com o
                circuit breaker aberto.
            httpx.DecodingError: O corpo não é uma lista JSON.
        """
        return lista(self._cliente.post(self._PATH_DRES, payload=codigos))

    def escolas(self, codigos: list[str]) -> list[dict[str, Any]]:
        """Busca nome, DRE e tipo de escola das UEs informadas.

        Args:
            codigos: Códigos EOL das UEs.

        Returns:
            UE encontrada; `[]` quando o Institucional
            responde sem conteúdo.

        Raises:
            httpx.HTTPStatusError: O Institucional respondeu 4xx ou 5xx.
            httpx.ConnectError: O Institucional está fora do ar ou com o
                circuit breaker aberto.
            httpx.DecodingError: O corpo não é uma lista JSON.
        """
        return lista(self._cliente.post(self._PATH_ESCOLAS, payload=codigos))

    def unidades_da_dre(self, dre: str) -> list[dict[str, Any]]:
        """Busca as unidades de uma DRE.

        Args:
            dre: Código EOL da DRE.

        Returns:
            Unidade, com `codigoEol` e `nomeNaoOficial`;
            `[]` quando o Institucional responde sem conteúdo.

        Raises:
            httpx.HTTPStatusError: O Institucional respondeu 4xx ou 5xx.
            httpx.ConnectError: O Institucional está fora do ar ou com o
                circuit breaker aberto.
            httpx.DecodingError: O corpo não é uma lista JSON.
        """
        path = self._PATH_UNIDADES_DA_DRE.format(dre=dre)
        return lista(self._cliente.get(path))
