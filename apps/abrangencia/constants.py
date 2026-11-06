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

STATUS_NEGOCIO = 601

MSG_PERFIL_OBRIGATORIO = "O perfil são obrigatórios."
MSG_LOGIN_PERFIL_OBRIGATORIOS = (
    "Os parametros de login e perfil são obrigatórios"
)
MSG_ABRANGENCIA_NAO_ENCONTRADA = (
    "Abrangência não encontrada para o perfil informado."
)
MSG_COMPORTAMENTO_INESPERADO = (
    "Houve um comportamento inesperado do sistema. Por favor, contate a SME."
)
MSG_CODIGO_DRE_OBRIGATORIO = "O codigo da Dre é obrigatório"
MSG_TURMA_OBRIGATORIA = "É necessário informar ao menos uma turma"

TIPO_RESOLUCAO_COMPACTA = "COMPACTA"
TIPO_RESOLUCAO_DETALHES = "DETALHES"

GRUPO_COMUNICADOS_UE = 43

ORIGENS_UE_POR_EXERCICIO = frozenset(
    {"LOTACAO_EXERCICIO", "PAEE", "UE_FUNCOES_ATIVIDADES_CIEJA"}
)

PARAMETRO_TIPOS_ESCOLA_EXIBIDOS = "tipos_escola_exibidos"

ETAPAS_LISTAGEM = frozenset({2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 17, 18})

ANO_INICIO_GRADE = 2010

ETAPAS_SONDAGEM = frozenset({5, 13})

SERIE_SONDAGEM_INICIO = "1"

SERIE_SONDAGEM_FIM = "6"
