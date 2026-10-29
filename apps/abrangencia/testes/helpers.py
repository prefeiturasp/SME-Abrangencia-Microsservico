"""Helpers compartilhados pelos testes do domínio Abrangência."""

from collections.abc import Iterable
from typing import Any
from unittest import TestCase
from unittest.mock import patch

from apps.abrangencia.constants import TIPO_RESOLUCAO_COMPACTA
from apps.abrangencia.models import AbrangenciaResolvida

_PERFIL_GUID = "2e89cf10-e42b-476f-8673-2dfbeeee3cd0"
_LOGIN = "9999001"
_ANO = 2026


def criar_escopo(**overrides: object) -> None:
    """Cria uma linha de escopo resolvido para os testes."""
    base = {
        "usuario_abrangencia_id": _proximo_id(AbrangenciaResolvida),
        "login": _LOGIN,
        "perfil_guid": _PERFIL_GUID,
        "ano_letivo": _ANO,
        "tipo_resolucao": TIPO_RESOLUCAO_COMPACTA,
        "dre_codigo": None,
        "ue_codigo": None,
        "turma_codigo": None,
        "origem": "LOTACAO_CARGO",
        "grupo_codigo": 10,
        "grupo_nome": None,
        "tipo_abrangencia": 1,
        "eh_perfil_manual": False,
        "eh_perfil_misto": False,
    }
    base.update(overrides)
    AbrangenciaResolvida.objects.create(**base)


class RedeSmeFalsa:
    """Rede em memória, com a mesma interface de `RedeSme`."""

    def __init__(self) -> None:
        self._dres: dict[str, dict[str, Any]] = {}
        self._ues: dict[str, dict[str, Any]] = {}
        self._turmas: dict[str, dict[str, Any]] = {}
        self._unidades: dict[str, str] = {}

    def com_dre(
        self, codigo: str, nome: str | None = None, sigla: str | None = None
    ) -> "RedeSmeFalsa":
        """Acrescenta uma DRE à rede."""
        self._dres[codigo] = {
            "nome": nome or f"DRE {codigo}",
            "sigla": sigla or f"D{codigo}",
        }
        return self

    def com_ue(
        self,
        codigo: str,
        *,
        dre: str | None = None,
        nome: str | None = None,
        sigla: str | None = None,
    ) -> "RedeSmeFalsa":
        """Acrescenta uma UE à rede, ligada à DRE informada."""
        self._ues[codigo] = {
            "nome": nome or f"Unidade {codigo}",
            "sigla": sigla or f"U{codigo}",
            "dre_codigo": dre,
        }
        if dre:
            self._unidades[codigo] = dre
        return self

    def com_unidade(self, codigo: str, dre: str) -> "RedeSmeFalsa":
        """Liga uma unidade fora da rede à DRE, como no Institucional."""
        self._unidades[codigo] = dre
        return self

    def com_turma(
        self,
        codigo: str,
        *,
        ue: str = "019331",
        nome: str | None = None,
        sondagem: bool = True,
    ) -> "RedeSmeFalsa":
        """Acrescenta uma turma listável do ano à rede."""
        self._turmas[codigo] = {
            "nome": nome or f"Turma {codigo}",
            "ue_codigo": ue,
            "sondagem": sondagem,
        }
        return self

    def dres(self) -> list[str]:
        """Lista as DREs da rede."""
        return sorted(self._dres)

    def codigos_dres(self) -> list[str]:
        """Lista as DREs da rede, como `codigos-dres`."""
        return sorted(self._dres)

    def atributos_dres(
        self, codigos: Iterable[str]
    ) -> dict[str, dict[str, Any]]:
        """Devolve as DREs pedidas que existem."""
        return {c: self._dres[c] for c in codigos if c in self._dres}

    def ues(self) -> frozenset[str]:
        """Lista as UEs da rede."""
        return frozenset(self._ues)

    def atributos_ues(
        self, codigos: Iterable[str]
    ) -> dict[str, dict[str, Any]]:
        """Devolve as UEs pedidas que estão na rede."""
        return {c: self._ues[c] for c in codigos if c in self._ues}

    def unidades_da_dre(self, dre: str) -> frozenset[str]:
        """Lista as unidades ligadas à DRE."""
        return frozenset(c for c, pai in self._unidades.items() if pai == dre)

    def turmas(
        self, codigos: Iterable[str], ano_letivo: int, *, sondagem: bool
    ) -> dict[str, dict[str, Any]]:
        """Devolve as turmas pedidas que estão na rede."""
        return {
            codigo: {"nome": turma["nome"], "ue_codigo": turma["ue_codigo"]}
            for codigo in codigos
            if (turma := self._turmas.get(codigo))
            and (not sondagem or turma["sondagem"])
        }

    def turmas_de_sondagem(
        self, ano_letivo: int
    ) -> dict[str, dict[str, Any]]:
        """Devolve as turmas de sondagem da rede."""
        return self.turmas(sorted(self._turmas), ano_letivo, sondagem=True)


def usar_rede_sme(teste: TestCase) -> RedeSmeFalsa:
    """Troca a rede do serviço por uma `RedeSmeFalsa` durante o teste."""
    rede = RedeSmeFalsa()
    troca = patch(
        "apps.abrangencia.services.obter_rede_sme", return_value=rede
    )
    troca.start()
    teste.addCleanup(troca.stop)
    return rede


def _proximo_id(modelo: type[AbrangenciaResolvida]) -> int:
    maior_id = modelo.objects.order_by("-usuario_abrangencia_id").first()
    if maior_id is None:
        return 1
    return int(maior_id.usuario_abrangencia_id) + 1
