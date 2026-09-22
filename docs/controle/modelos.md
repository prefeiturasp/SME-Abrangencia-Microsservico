# Modelos

Esta seção descreve os modelos de leitura do **SME-Abrangencia-Microsservico**. Nenhum é gerenciado pelo Django (`managed = False`): o schema pertence ao pipeline `sme-airflow`, versionado por Flyway — este serviço nunca gera migration para essas tabelas.

## Relacionamento entre os modelos

```text
Perfil ──────────► PerfilVinculoFuncional
   │
   └──────────────► AbrangenciaCompacta (materialized view)

UsuarioAbrangencia (fato granular, com origem)
```

---

# Perfil

Perfil do CoreSSO, com o ramo de abrangência (`TipoAbrangencia`) que ele resolve.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `perfil_guid` | UUID | Identificador do perfil (PK). |
| `grupo_codigo` | Integer | Código do grupo do legado. |
| `nome` | Text | Nome do perfil. |
| `tipo_abrangencia` | Integer | Ramo de `TipoAbrangencia` que decide a forma do escopo. |
| `eh_perfil_manual` | Boolean | Indica perfil de concessão manual. |
| `eh_perfil_misto` | Boolean | Indica perfil misto. |

---

# PerfilVinculoFuncional

Cargo ou função-atividade que concede um perfil. Um perfil pode ser concedido por vários cargos/funções — não é uma relação 1:1.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `perfil_guid` | UUID | Perfil concedido (parte da PK composta). |
| `tipo` | Text | `CARGO` ou `FUNCAO_ATIVIDADE` (parte da PK composta). |
| `codigo` | Integer | Código do cargo/função (parte da PK composta). |

---

# UsuarioAbrangencia

Fato de abrangência: um nível de escopo de um usuário, por origem. Carrega a `origem` que o produziu, o que permite restringir consultas a determinadas origens (ex.: só lotação, não atribuição de aula).

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `login` | Text | RF ou CPF do usuário. |
| `perfil_guid` | UUID | Perfil ao qual o registro pertence. |
| `ano_letivo` | Integer | Ano letivo do escopo. |
| `dre_codigo` / `ue_codigo` / `turma_codigo` | Text | Nível territorial do registro. |
| `origem` | Text | Fonte do dado (ex. `LOTACAO_CARGO`, `ATRIBUICAO_AULA`). |
| `vigente` | Boolean | Se o vínculo está ativo. |
| `elegivel_sondagem` | Boolean | Se a turma entra nas consultas de sondagem. |

---

# AbrangenciaCompacta

Materialized view: escopo agregado de `(login, perfil_guid, ano_letivo)`, com os arrays de DREs/UEs/turmas já agregados por dois algoritmos concorrentes (padrão e alternativo). É a fonte dos endpoints `compacta-*`.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `login`, `perfil_guid`, `ano_letivo` | — | Chave composta (PK). |
| `id_dres`, `id_ues`, `id_turmas` | Array de texto | Escopo do algoritmo padrão (E-07). |
| `id_ues_alternativo`, `id_turmas_alternativo` | Array de texto | Escopo do algoritmo alternativo (E-08/E-09/E-10). |
| `id_ues_detalhaveis` | Array de texto | Base para expansão de nomes em E-09. |
| `id_turmas_poa` | Array de texto | Turmas da origem POA, exceção de perfis POA no ramo UE. |
