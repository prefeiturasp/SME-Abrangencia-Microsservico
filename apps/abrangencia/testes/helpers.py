"""Helpers compartilhados pelos testes do domínio Abrangência."""

from apps.abrangencia.constants import (
    TIPO_ESCOPO_DRE,
    TIPO_ESCOPO_UE,
    TIPO_RESOLUCAO_COMPACTA,
)
from apps.abrangencia.models import AbrangenciaResolvida, Unidade

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
        "tipo_escopo": TIPO_ESCOPO_UE,
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


def criar_unidade(**overrides: object) -> None:
    """Cria uma unidade expandida para os testes."""
    codigo = overrides.get("codigo", "019331")
    base = {
        "ano_letivo": _ANO,
        "tipo_escopo": TIPO_ESCOPO_UE,
        "codigo": codigo,
        "nome": f"Unidade {codigo}",
        "sigla": f"U{codigo}",
        "dre_codigo_pai": None,
        "ue_codigo_pai": None,
        "elegivel_sondagem": False,
    }
    if overrides.get("tipo_escopo") == TIPO_ESCOPO_DRE:
        base["nome"] = f"DRE {codigo}"
        base["sigla"] = f"D{codigo}"
    base.update(overrides)
    Unidade.objects.create(**base)


def _proximo_id(modelo: type[AbrangenciaResolvida]) -> int:
    maior_id = modelo.objects.order_by("-usuario_abrangencia_id").first()
    if maior_id is None:
        return 1
    return int(maior_id.usuario_abrangencia_id) + 1
