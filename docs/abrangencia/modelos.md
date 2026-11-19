# Modelos

Esta seção descreve os modelos de leitura do **SME-Abrangencia-Microsservico**. Todos herdam de `ModeloBase`, portanto não são gerenciados pelo Django (`managed = False`): o schema pertence ao pipeline `sme-airflow`, versionado por Flyway.

## Relacionamento entre os modelos

```text
Perfil ──────────► PerfilVinculoFuncional
   │
   └─────────────► AbrangenciaResolvida (mv_abrangencia_resolvida)

UsuarioPorPerfil (mv_abrangencia_usuarios_perfil)

VinculoFuncional (usuario_vinculo_funcional)

Sistema ─────────► ParametroSistema
```

## Perfil

Perfil do CoreSSO, com o ramo de abrangência (`TipoAbrangencia`) que ele resolve.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `perfil_guid` | UUID | Identificador do perfil (PK). |
| `grupo_codigo` | Integer | Código do grupo do legado. |
| `nome` | Text | Nome do perfil. |
| `abrangencia_id` | Integer | Ramo de `TipoAbrangencia` que decide a forma do escopo. |
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
| `dre_codigo` / `ue_codigo` / `turma_codigo` | Text | Código EOL. |
| `origem` | Text | Fonte do dado, usada em regras de projeção do escopo. |
| `grupo_codigo` / `grupo_nome` | Integer/Text | Grupo do perfil no legado. |
| `tipo_abrangencia` | Integer | Tipo de abrangência do perfil. |
| `eh_perfil_manual` / `eh_perfil_misto` | Boolean | Flags agregadas do perfil. |

## UsuarioPorPerfil

Materialized view `mv_abrangencia_usuarios_perfil`. Base do endpoint `perfis/usuarios`, com usuários vigentes por perfil e UE. O filtro por DRE usa a DRE de cada UE no MS Institucional.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `usuario_rf` | Text | RF do usuário (parte da PK composta). |
| `perfil_guid` | UUID | Perfil do usuário (parte da PK composta). |
| `ano_letivo` | Integer | Ano letivo (parte da PK composta). |
| `ue_codigo` | Text | Código da UE (parte da PK composta). |

## VinculoFuncional

Tabela `usuario_vinculo_funcional`, carregada pelo `sme-airflow`: um vínculo do servidor por origem.

Quando a unidade do vínculo é a própria DRE, `ue_codigo` e `ue_nome` vêm nulos e a unidade fica só em `dre_codigo` e `dre_nome`.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `ano_letivo` | Integer | Ano da carga. |
| `login` | Varchar(50) | RF do servidor. |
| `origem` | Varchar(30) | `CARGO_BASE`, `CARGO_SOBREPOSTO`, `ATRIBUICAO_AULA` ou `FUNCAO_ATIVIDADE`. |
| `cargo_base_servidor` | BigInteger | Cargo base do servidor no EOL. |
| `lotacao_servidor` | BigInteger | Lotação do cargo base; só em `CARGO_BASE`. |
| `cargo_codigo` | Integer | Código do cargo; em `CARGO_SOBREPOSTO`, o sobreposto. |
| `cargo_nome` | Text | Nome do cargo. |
| `funcao_atividade_codigo` | Integer | Função-atividade; só em `FUNCAO_ATIVIDADE`. |
| `funcao_atividade_nome` | Text | Nome da função-atividade. |
| `dre_codigo` | Varchar(15) | DRE da unidade do vínculo; nulo fora de DRE. |
| `dre_nome` | Text | Nome da DRE. |
| `ue_codigo` | Varchar(15) | Unidade do vínculo; nulo quando ela é a própria DRE. |
| `ue_tipo` | SmallInteger | `tp_unidade_educacao` da unidade: 1 escola, 3 unidade administrativa. |
| `ue_nome` | Text | Nome da unidade como o legado devolve (`SIGLA - NOME` para escola); nulo quando ela é a própria DRE. |

## Sistema e ParametroSistema

Tabelas `sistema` e `parametro_sistema`. O serviço lê delas só `tipos_escola_exibidos`: a linha ativa do ano corrente de um sistema ativo, ou a global (`sistema_id = 0`) quando o sistema não tem a sua. Ausente ou vazia é erro de configuração.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `sistema_id` | Integer | Sistema dono do parâmetro; `0` é o global. |
| `nome` | Varchar | Nome do parâmetro. |
| `valor` | Text | Valor, em lista separada por vírgula nos formatos `array_*`. |
| `ano_letivo` | Integer | Ano de vigência. |
| `ativo` | Boolean | Linha em uso. |
