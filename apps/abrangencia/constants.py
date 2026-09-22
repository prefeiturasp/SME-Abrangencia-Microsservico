"""Constantes do dominio Abrangencia."""

from enum import IntEnum


class TipoAbrangencia(IntEnum):
    """Tipos de abrangencia territorial de um perfil."""

    UE = 1
    PROFESSOR = 2
    UE_TURMAS_DISCIPLINAS = 3
    DRE = 4
    DRE_ESCOLAS_ATRIBUIDAS = 5
    SME = 6


GUID_VAZIO = "00000000-0000-0000-0000-000000000000"

TIPO_RESOLUCAO_COMPACTA = "COMPACTA"
TIPO_RESOLUCAO_DETALHES = "DETALHES"

GRUPO_COMUNICADOS_UE = 43

ORIGENS_UE_POR_EXERCICIO = frozenset(
    {"LOTACAO_EXERCICIO", "PAEE", "UE_FUNCOES_ATIVIDADES_CIEJA"}
)

TIPO_ESCOPO_DRE = "DRE"
TIPO_ESCOPO_UE = "UE"
TIPO_ESCOPO_TURMA = "TURMA"
