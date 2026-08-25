"""Constantes do domínio Abrangência."""

from enum import IntEnum


class TipoAbrangencia(IntEnum):
    """Ramos de abrangência territorial de um perfil.

    Cada valor define como o escopo agregado é projetado (ver
    `services.ESCOPO_POR_ABRANGENCIA`); `DRE_ESCOLAS_ATRIBUIDAS` não tem
    entrada lá, e por isso sai com os três níveis zerados.
    """

    UE = 1
    PROFESSOR = 2
    UE_TURMAS_DISCIPLINAS = 3
    DRE = 4
    DRE_ESCOLAS_ATRIBUIDAS = 5
    SME = 6


# Grupo do perfil (não `TipoAbrangencia`) do Professor Readaptado.
GRUPO_PROFESSOR_READAPTADO = 2

# GUIDs dos perfis POA (Alfabetização, Língua Portuguesa, Matemática,
# Humanas, Naturais).
PERFIS_POA: frozenset[str] = frozenset(
    {
        "2e89cf10-e42b-476f-8673-2dfbeeee3cd0",  # POAAlfabetizacao
        "57a7b9ab-8e61-4093-b692-a0bb1f9f46bd",  # POALinguaPortuguesa
        "cf181fd4-dd30-47cf-a97d-57e602fd8d10",  # POAMatematica
        "2c7ced81-7109-4276-9262-5c56efd8992f",  # POAHumanas
        "3104735d-c369-4710-ae64-bca37bc78f3b",  # POANaturais
    }
)

# Origens de lotação (exclui atribuição de aula).
ORIGENS_LOTACAO: tuple[str, ...] = (
    "LOTACAO_CARGO",
    "LOTACAO_EXERCICIO",
    "LOTACAO_CARGO_BASE",
    "FUNCAO_ATIVIDADE",
    "CORESSO_MANUAL",
)

# `UUID()` aceita esse valor sem erro; recusado à parte para não virar
# um 204 (perfil inexistente) em vez de 400.
GUID_VAZIO = "00000000-0000-0000-0000-000000000000"
