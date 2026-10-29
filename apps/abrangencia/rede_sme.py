"""DREs, UEs e turmas da rede, lidas dos MS Institucional e Pedagogico."""

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, fields
from typing import Any

from django.core.exceptions import ImproperlyConfigured

from apps.abrangencia.cache_repository import (
    IntegracaoEolCacheRepository,
    RedeSmeCacheRepository,
    agora,
)
from apps.abrangencia.constants import (
    ANO_INICIO_GRADE,
    ETAPAS_LISTAGEM,
    ETAPAS_SONDAGEM,
    PARAMETRO_TIPOS_ESCOLA_EXIBIDOS,
    SERIE_SONDAGEM_FIM,
    SERIE_SONDAGEM_INICIO,
)
from apps.abrangencia.integracao_eol import InstitucionalAPI, PedagogicoAPI
from apps.abrangencia.models import ParametroSistema, Sistema
from apps.core.api.responses import lista

_LOTE = 500
_SISTEMA_GLOBAL = 0
_AUSENTE: dict[str, Any] = {}

Atributos = dict[str, dict[str, Any]]


class RedeSmeIncompletaError(Exception):
    """A rede inválida: resposta vazia onde nao podia."""


@dataclass(frozen=True)
class _RedeSme:
    """Rede vigente: igual para todo request."""

    tipos_escolas_exibidos: frozenset[int]
    dres: tuple[str, ...]
    siglas: dict[str, str | None]
    ues: frozenset[str]
    turmas_vigentes: dict[int, tuple[str, ...]]


def tipos_escola_exibidos(ano: int) -> frozenset[int]:
    """Le `tipos_escola_exibidos` do sistema ativo, ou o global.

    Raises:
        ImproperlyConfigured: Parametro ausente ou vazio no ano.
    """
    ativos = list(
        Sistema.objects.filter(ativo=True)
        .exclude(sistema_id=_SISTEMA_GLOBAL)
        .values_list("sistema_id", flat=True)
    )
    linhas = ParametroSistema.objects.filter(
        nome=PARAMETRO_TIPOS_ESCOLA_EXIBIDOS,
        ativo=True,
        ano_letivo=ano,
        sistema_id__in=[*ativos, _SISTEMA_GLOBAL] if ativos else [],
    ).values_list("sistema_id", "valor")
    valores = [
        valor
        for _, valor in sorted(
            linhas, key=lambda linha: linha[0] == _SISTEMA_GLOBAL
        )
    ]
    tipos = frozenset(
        int(item)
        for item in (valores[0] if valores else "").split(",")
        if item.strip()
    )
    if not tipos:
        raise ImproperlyConfigured(
            f"{PARAMETRO_TIPOS_ESCOLA_EXIBIDOS} ausente em "
            f"parametro_sistema para {ano}."
        )
    return tipos


def estrutura_vigente_por_dre(
    codigo_dre: str,
    pedagogico: PedagogicoAPI | None = None,
    cache: IntegracaoEolCacheRepository | None = None,
) -> dict[str, Any]:
    """Devolve a estrutura vigente da DRE, do cache."""
    cache = cache or IntegracaoEolCacheRepository()
    estrutura = cache.obter_estrutura_vigente(codigo_dre)
    if estrutura is None:
        estrutura = (pedagogico or PedagogicoAPI()).estrutura_vigente_por_dre(
            codigo_dre
        )
        if estrutura["dres"]:
            cache.armazenar_estrutura_vigente(codigo_dre, estrutura)
    return estrutura


def turma_listavel(turma: Mapping[str, Any]) -> bool:
    """Informa se a turma e de etapa listada e tem grade curricular."""
    return (
        turma.get("codigo_etapa_ensino") in ETAPAS_LISTAGEM
        and (turma.get("ano_letivo") or 0) >= ANO_INICIO_GRADE
    )


def turma_de_sondagem(turma: Mapping[str, Any]) -> bool:
    """Informa se a turma e de serie 1 a 6, como texto, e etapa 5 ou 13."""
    serie = str(turma.get("ano") or "")
    return (
        SERIE_SONDAGEM_INICIO <= serie <= SERIE_SONDAGEM_FIM
        and turma.get("codigo_etapa_ensino") in ETAPAS_SONDAGEM
    )


class RedeSme:
    """Consulta a rede, montada uma vez por dia e guardada no cache."""

    def __init__(
        self,
        institucional: InstitucionalAPI | None = None,
        pedagogico: PedagogicoAPI | None = None,
        cache: RedeSmeCacheRepository | None = None,
        cache_integracao: IntegracaoEolCacheRepository | None = None,
    ) -> None:
        self._institucional = institucional
        self._pedagogico = pedagogico
        self._cache = cache or RedeSmeCacheRepository()
        self._cache_integracao = (
            cache_integracao or IntegracaoEolCacheRepository()
        )
        self._memo: _RedeSme | None = None

    def dres(self) -> list[str]:
        """Lista os codigos das DREs da rede, ordenados."""
        return list(self._rede_sme().dres)

    def codigos_dres(self) -> list[str]:
        """Lista os codigos das DREs da rede, ordenados.

        Raises:
            RedeSmeIncompletaError: O Institucional nao trouxe DRE.
        """
        codigos = lista(self._api_inst().codigos_dres())
        if not codigos:
            raise RedeSmeIncompletaError("codigos-dres sem DRE")
        return sorted(str(codigo) for codigo in codigos)

    def atributos_dres(self, codigos: Iterable[str]) -> Atributos:
        """Devolve `nome` e `sigla` das DREs."""
        return {
            codigo: {"nome": dre.get("nomeDRE"), "sigla": dre.get("siglaDRE")}
            for codigo, dre in self._dres(codigos).items()
        }

    def ues(self) -> frozenset[str]:
        """Lista as UEs da rede: tipo exibido e alguma turma."""
        return self._rede_sme().ues

    def atributos_ues(self, codigos: Iterable[str]) -> Atributos:
        """Devolve `nome`, `sigla` e `dre_codigo` das UEs da rede."""
        rede = self._rede_sme()
        pedidas = [codigo for codigo in codigos if codigo in rede.ues]
        return {
            codigo: {
                "nome": escola.get("nomeEscola"),
                "sigla": rede.siglas.get(codigo),
                "dre_codigo": _texto(escola.get("codigoDRE")),
            }
            for codigo, escola in self._escolas(pedidas).items()
        }

    def unidades_da_dre(self, dre: str) -> frozenset[str]:
        """Lista as unidades da DRE no Institucional, sem montar a rede."""
        return frozenset(
            str(unidade["codigoEol"])
            for unidade in self._api_inst().unidades_da_dre(dre)
        )

    def turmas(
        self,
        codigos: Iterable[str],
        ano_letivo: int,
        *,
        sondagem: bool,
    ) -> Atributos:
        """Devolve `nome` e `ue_codigo` das turmas listaveis do ano.

        Args:
            codigos: Turmas pedidas.
            ano_letivo: Ano letivo que a turma precisa ter.
            sondagem: Restringe as turmas de sondagem.

        Returns:
            Turma listavel, do ano e de UE de tipo exibido. As demais nao
            aparecem.
        """
        tipos = self._rede_sme().tipos_escolas_exibidos
        turmas = {
            codigo: turma
            for codigo, turma in self._turmas(codigos).items()
            if turma.get("ano_letivo") == ano_letivo
            and turma_listavel(turma)
            and (not sondagem or turma_de_sondagem(turma))
        }
        escolas = self._escolas(
            {_texto(turma.get("ue_codigo")) for turma in turmas.values()}
        )
        return {
            codigo: {"nome": turma.get("nome_turma"), "ue_codigo": ue}
            for codigo, turma in turmas.items()
            if (ue := _texto(turma.get("ue_codigo"))) in escolas
            and escolas[ue].get("codigoTipoEscola") in tipos
        }

    def turmas_de_sondagem(self, ano_letivo: int) -> Atributos:
        """Devolve as turmas de sondagem da estrutura vigente no ano."""
        codigos = self._rede_sme().turmas_vigentes.get(ano_letivo, ())
        return self.turmas(codigos, ano_letivo, sondagem=True)

    def carregar(self) -> None:
        """Monta a rede vigente, se ainda nao estiver no cache."""
        self._rede_sme()

    def _rede_sme(self) -> _RedeSme:
        """Devolve a rede vigente, montando-a so quando ausente no cache."""
        if self._memo is not None:
            return self._memo
        rede = self._rede_sme_em_cache()
        if rede is None:
            with self._cache.bloquear_rede_sme() as adquirido:
                rede = self._rede_sme_em_cache() if adquirido else None
                if rede is None:
                    rede = self._montar()
                    self._cache.armazenar_rede_sme(rede)
        self._memo = rede
        return rede

    def _rede_sme_em_cache(self) -> _RedeSme | None:
        """Le a rede do cache."""
        rede = self._cache.obter_rede_sme()
        if not isinstance(rede, _RedeSme):
            return None
        atuais = {campo.name for campo in fields(_RedeSme)}
        return rede if atuais <= set(vars(rede)) else None

    def _montar(self) -> _RedeSme:
        """Monta a rede pelas DREs, unidades e estrutura vigente."""
        ano = agora().year
        tipos = tipos_escola_exibidos(ano)
        dres = sorted(
            str(codigo) for codigo in lista(self._api_inst().codigos_dres())
        )
        self._dres(dres)

        siglas: dict[str, str | None] = {}
        dres_sem_unidade: list[str] = []
        for dre in dres:
            unidades = self._api_inst().unidades_da_dre(dre)
            if not unidades:
                dres_sem_unidade.append(dre)
            for unidade in unidades:
                siglas[str(unidade["codigoEol"])] = unidade.get(
                    "nomeNaoOficial"
                )
        exibidas = {
            codigo
            for codigo, escola in self._escolas(sorted(siglas)).items()
            if escola.get("codigoTipoEscola") in tipos
        }

        vigentes, dres_sem_estrutura = self._turmas_vigentes(dres, tipos)
        turmas = self._turmas(
            codigo for codigos in vigentes.values() for codigo in codigos
        )
        ues: set[str] = set()
        por_ano: dict[int, list[str]] = {}
        for ue, codigos in vigentes.items():
            for codigo in codigos:
                turma = turmas.get(codigo)
                if turma and turma_listavel(turma):
                    ues.add(ue)
                    por_ano.setdefault(turma["ano_letivo"], []).append(codigo)
        for ue in sorted(exibidas - ues):
            if self._tem_turma_listavel(ue, ano):
                ues.add(ue)

        rede = _RedeSme(
            tipos_escolas_exibidos=tipos,
            dres=tuple(dres),
            siglas={ue: siglas[ue] for ue in sorted(ues) if ue in siglas},
            ues=frozenset(ues),
            turmas_vigentes={
                ano_letivo: tuple(sorted(set(codigos)))
                for ano_letivo, codigos in por_ano.items()
            },
        )
        _validar(rede, dres_sem_unidade, dres_sem_estrutura)
        return rede

    def _turmas_vigentes(
        self, dres: list[str], tipos: frozenset[int]
    ) -> tuple[dict[str, list[str]], list[str]]:
        """Agrupa por UE de tipo exibido as turmas da estrutura vigente.

        Returns:
            As turmas por UE e as DREs cuja estrutura vigente veio vazia.
        """
        vigentes: dict[str, list[str]] = {}
        sem_estrutura: list[str] = []
        for dre in dres:
            estrutura = estrutura_vigente_por_dre(
                dre, self._api_ped(), self._cache_integracao
            )
            if not estrutura["dres"]:
                sem_estrutura.append(dre)
            for item in estrutura["dres"]:
                for ue in item.get("ues") or []:
                    if ue.get("codTipoEscola") not in tipos:
                        continue
                    turmas = ue.get("turmas") or []
                    vigentes.setdefault(str(ue["codigo"]), []).extend(
                        str(turma["codigo"]) for turma in turmas
                    )
        return vigentes, sem_estrutura

    def _tem_turma_listavel(self, ue: str, ano: int) -> bool:
        """Procura turma da UE no ano e, sem ela, nos anteriores."""
        for anos in ([ano], list(range(ANO_INICIO_GRADE, ano))):
            if not anos:
                continue
            codigos = self._api_ped().codigos_turma_da_ue(ue, anos)
            if any(map(turma_listavel, self._turmas(codigos).values())):
                return True
        return False

    def _dres(self, codigos: Iterable[str]) -> Atributos:
        return self._por_codigo(
            "dre", codigos, self._api_inst().dres, "codigoDRE"
        )

    def _escolas(self, codigos: Iterable[str]) -> Atributos:
        return self._por_codigo(
            "ue", codigos, self._api_inst().escolas, "codigoEscola"
        )

    def _turmas(self, codigos: Iterable[str]) -> Atributos:
        def listar(lote: list[str]) -> list[dict[str, Any]]:
            return self._api_ped().listar_turmas([int(c) for c in lote])

        return self._por_codigo("turma", codigos, listar, "codigo")

    def _por_codigo(
        self,
        tipo: str,
        codigos: Iterable[str],
        buscar: Callable[[list[str]], list[dict[str, Any]]],
        campo: str,
    ) -> Atributos:
        """Le do cache por codigo."""
        pedidos = [c for c in dict.fromkeys(codigos) if c]
        achados = self._cache.obter_codigos(tipo, pedidos)
        faltam = [codigo for codigo in pedidos if codigo not in achados]
        for inicio in range(0, len(faltam), _LOTE):
            lote = faltam[inicio : inicio + _LOTE]
            novos = dict.fromkeys(lote, _AUSENTE)
            itens = buscar(lote)
            for item in itens:
                novos[_texto(item.get(campo))] = item
            if itens:
                self._cache.armazenar_codigos(tipo, novos)
            achados.update(novos)
        return {
            codigo: achados[codigo]
            for codigo in pedidos
            if achados.get(codigo)
        }

    def _api_inst(self) -> InstitucionalAPI:
        if self._institucional is None:
            self._institucional = InstitucionalAPI()
        return self._institucional

    def _api_ped(self) -> PedagogicoAPI:
        if self._pedagogico is None:
            self._pedagogico = PedagogicoAPI()
        return self._pedagogico


def _validar(
    rede: _RedeSme,
    dres_sem_unidade: list[str],
    dres_sem_estrutura: list[str],
) -> None:
    """Recusa a rede que ficou vazia, antes de ir para o cache.

    Raises:
        RedeSmeIncompletaError: Com o que faltou.
    """
    faltas = []
    if not rede.dres:
        faltas.append("codigos-dres sem DRE")
    if dres_sem_unidade:
        faltas.append(f"DRE sem unidade: {', '.join(dres_sem_unidade)}")
    if dres_sem_estrutura:
        faltas.append(
            "DRE sem estrutura vigente: " + ", ".join(dres_sem_estrutura)
        )
    if not rede.ues:
        faltas.append("rede sem UE")
    if not rede.turmas_vigentes:
        faltas.append("estrutura vigente sem turma listavel")
    if faltas:
        raise RedeSmeIncompletaError("; ".join(faltas))


def _texto(valor: Any) -> str:
    return "" if valor is None else str(valor)


def obter_rede_sme() -> RedeSme:
    """Devolve uma rede nova, para um request."""
    return RedeSme()
