"""Ciclos de ensino, estrutura vigente e turmas, do MS-Pedagogico."""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from apps.core.api.responses import lista
from apps.core.cliente_http import ClienteServico, obter_cliente

_FUSO_LEGADO = ZoneInfo("America/Sao_Paulo")
_DATAS_TURMA = ("dataFim", "dataInicioTurma")


class PedagogicoAPI:
    """Chamadas ao SME-IntegracaoEOL-Pedagogico-Microsservico."""

    nome = "pedagogico"

    _PATH_CICLO_ENSINO = "/abrangencia/ciclo-ensino/"
    _PATH_TURMAS_POR_DRE = "/turmas/turmas-atribuidas-dre-ue/todas/"
    _PATH_TURMAS_POR_CODIGO = "/turmas/turmas-atribuidas-dre-ue/por-turmas/"
    _PATH_LISTAR_TURMAS = "/turmas/listar-turmas/"
    _PATH_TURMAS_DA_UE = (
        "/turmas/ue/{ue}/sincronizacoes-institucionais/anos-letivos/"
    )

    def __init__(self, cliente: ClienteServico | None = None) -> None:
        self._cliente = cliente or obter_cliente(self.nome)

    def ciclos_ensino(self) -> httpx.Response:
        """Busca o catálogo de ciclos de ensino."""
        return self._cliente.get(self._PATH_CICLO_ENSINO)

    def estrutura_vigente_por_dre(self, codigo_dre: str) -> dict[str, Any]:
        """Busca DRE, UE e turma vigente de uma DRE."""
        resposta = self._cliente.get(
            self._PATH_TURMAS_POR_DRE, params={"codigo_dre": codigo_dre}
        )
        return _estrutura_legado(resposta)

    def estrutura_vigente_por_turmas(
        self, codigos_turma: list[int]
    ) -> dict[str, Any]:
        """Busca DRE, UE e das turmas informadas."""
        resposta = self._cliente.post(
            self._PATH_TURMAS_POR_CODIGO, payload=codigos_turma
        )
        return _estrutura_legado(resposta)

    def listar_turmas(self, codigos_turma: list[int]) -> list[dict[str, Any]]:
        """Busca ano letivo, série, etapa, nome e UE das turmas informadas."""
        return lista(
            self._cliente.post(self._PATH_LISTAR_TURMAS, payload=codigos_turma)
        )

    def codigos_turma_da_ue(self, ue: str, anos: list[int]) -> list[str]:
        """Busca os códigos das turmas de uma UE nos anos letivos."""
        resposta = self._cliente.get(
            self._PATH_TURMAS_DA_UE.format(ue=ue),
            params={"anos_letivos_vigente": anos},
        )
        return [str(codigo) for codigo in lista(resposta)]


def _estrutura_legado(resposta: httpx.Response) -> dict[str, Any]:
    """Retorna estrutura com a lista de DREs."""
    if resposta.status_code == 204 or not resposta.content:
        return {"dres": []}
    corpo = resposta.json()
    dres = corpo.get("dres") if isinstance(corpo, dict) else None
    return {"dres": [_dre_legado(dre) for dre in dres or []]}


def _dre_legado(dre: dict[str, Any]) -> dict[str, Any]:
    """Retorna as UEs de uma DRE."""
    ues = dre.get("ues")
    if not isinstance(ues, list):
        return dre
    return {**dre, "ues": [_ue_legado(ue) for ue in ues]}


def _ue_legado(ue: dict[str, Any]) -> dict[str, Any]:
    """Retorna as turmas de uma UE."""
    turmas = ue.get("turmas")
    if not isinstance(turmas, list):
        return ue
    return {**ue, "turmas": [_turma_legado(turma) for turma in turmas]}


def _turma_legado(turma: dict[str, Any]) -> dict[str, Any]:
    """Formata os campos de data e hora da turma para o padrão do legado."""
    return {
        chave: _formatar_data_hora_legado(valor)
        if chave in _DATAS_TURMA
        else valor
        for chave, valor in turma.items()
    }


def _formatar_data_hora_legado(valor: Any) -> Any:
    """Formata datas UTC (com 'Z') para o horário local sem fuso."""
    if not isinstance(valor, str) or not valor.endswith("Z"):
        return valor
    try:
        data_hora = datetime.fromisoformat(valor)
    except ValueError:
        return valor
    texto = (
        data_hora.astimezone(_FUSO_LEGADO).replace(tzinfo=None).isoformat()
    )
    base, _, fracao = texto.partition(".")
    fracao = fracao.rstrip("0")
    return f"{base}.{fracao}" if fracao else base
