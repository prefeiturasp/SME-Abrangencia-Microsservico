# Modelos

Esta seção descreve os modelos de leitura do **SME-Abrangencia-Microsservico**. Todos herdam de `ModeloBase`, portanto não são gerenciados pelo Django (`managed = False`): o schema pertence ao pipeline `sme-airflow`, versionado por Flyway.

## Relacionamento entre os modelos

```text
Perfil ──────────► PerfilVinculoFuncional
   │
   └─────────────► AbrangenciaResolvida (mv_abrangencia_resolvida)

Unidade (mv_abrangencia_unidade)

UsuarioPorPerfil (mv_abrangencia_usuarios_perfil)
```

## Perfil

Perfil do CoreSSO, com o ramo de abrangência (`TipoAbrangencia`) que ele resolve.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `perfil_guid` | UUID | Identificador do perfil (PK). |
| `grupo_codigo` | Integer | Código do grupo do legado. |
| `nome` | Text | Nome do perfil. |
| `tipo_abrangencia` | Integer | Ramo de `TipoAbrangencia` que decide a forma do escopo. |
| `eh_perfil_manual` | Boolean | Indica perfil de concessão manual. |
| `eh_perfil_misto` | Boolean | Indica perfil misto. |
| `atualizado_em` | DateTime | Data/hora da última atualização no pipeline. |
| `eh_grupo_manual` | Boolean | Indica se o grupo é manual no contrato agregado. |

## PerfilVinculoFuncional

Cargo ou função-atividade que concede um perfil. Um perfil pode ser concedido por vários cargos/funções.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `perfil_guid` | UUID | Perfil concedido (parte da PK composta). |
| `tipo` | Text | `CARGO` ou `FUNCAO_ATIVIDADE` (parte da PK composta). |
| `codigo` | Integer | Código do cargo/função (parte da PK composta). |
| `atualizado_em` | DateTime | Data/hora da última atualização no pipeline. |

## AbrangenciaResolvida

Materialized view `mv_abrangencia_resolvida`. Representa uma linha de escopo já resolvida para um usuário, perfil, ano letivo e algoritmo.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `usuario_abrangencia_id` | BigInteger | Identificador da linha de origem (PK no model). |
| `login` | Text | RF ou CPF do usuário. |
| `perfil_guid` | UUID | Perfil ao qual o registro pertence. |
| `ano_letivo` | Integer | Ano letivo do escopo. |
| `tipo_resolucao` | Text | Algoritmo usado na resolução, como `COMPACTA` ou `DETALHES`. |
| `tipo_escopo` | Text | Nível do escopo resolvido: DRE, UE ou TURMA. |
| `dre_codigo` / `ue_codigo` / `turma_codigo` | Text | Código territorial resolvido. |
| `origem` | Text | Fonte do dado, usada em regras de projeção do escopo. |
| `grupo_codigo` / `grupo_nome` | Integer/Text | Grupo do perfil no legado. |
| `tipo_abrangencia` | Integer | Tipo de abrangência do perfil. |
| `eh_perfil_manual` / `eh_perfil_misto` | Boolean | Flags agregadas do perfil. |

## Unidade

Materialized view `mv_abrangencia_unidade`. Resolve nome, sigla e hierarquia de DREs, UEs e turmas por ano letivo.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `ano_letivo` | Integer | Ano letivo da unidade (parte da PK composta). |
| `tipo_escopo` | Text | Tipo da unidade: DRE, UE ou TURMA (parte da PK composta). |
| `codigo` | Text | Código da unidade (parte da PK composta). |
| `nome` | Text | Nome da unidade. |
| `sigla` | Text | Sigla da unidade. |
| `dre_codigo_pai` | Text | DRE pai, quando aplicável. |
| `ue_codigo_pai` | Text | UE pai, quando aplicável. |
| `elegivel_sondagem` | Boolean | Indica se a turma entra nas consultas de sondagem. |

## UsuarioPorPerfil

Materialized view `mv_abrangencia_usuarios_perfil`. Base do endpoint `perfis/usuarios`, com usuários vigentes por perfil, UE e DRE.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `usuario_rf` | Text | RF do usuário (parte da PK composta). |
| `perfil_guid` | UUID | Perfil do usuário (parte da PK composta). |
| `ano_letivo` | Integer | Ano letivo (parte da PK composta). |
| `ue_codigo` | Text | Código da UE (parte da PK composta). |
| `dre_codigo` | Text | Código da DRE (parte da PK composta). |
