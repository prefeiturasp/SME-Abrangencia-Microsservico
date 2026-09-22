# API

Esta seção apresenta uma visão geral dos recursos disponibilizados pelo **SME-Abrangencia-Microsservico**.

## Autenticação

Todos os endpoints do domínio utilizam autenticação por **API Key**.

A chave deve ser enviada no cabeçalho HTTP configurado pela variável de ambiente `API_KEY_HEADER`.

Exemplo:

```text
X-API-Key: <API_KEY>
```

Caso a chave seja inválida ou esteja ausente, a requisição será rejeitada com **HTTP 401 (Unauthorized)**.

## Prefixos

| Recurso | Prefixo |
|---------|---------|
| API do domínio | `/api/abrangencia/` |
| Swagger UI | `/abrangencia/api/v1/docs/` |
| Schema OpenAPI | `/abrangencia/api/v1/docs/schema/` |

As rotas do domínio não usam barra final, mantendo compatibilidade com o contrato legado.

## Recursos disponíveis

### Health Check

| Método | Endpoint | Descrição |
|---------|----------|-----------|
| GET | `/api/abrangencia/health/` | Verifica se o serviço está disponível. |

### Perfil

| Método | Endpoint | Descrição |
|---------|----------|-----------|
| GET | `/api/abrangencia/{id_perfil}` | Retorna o perfil e os cargos/funções que o concedem. |

### Escopo compacto de um usuário em um perfil

| Método | Endpoint | Descrição |
|---------|----------|-----------|
| GET | `/api/abrangencia/compacta-vigente/{login}/perfil/{id_perfil}` | Escopo vigente, algoritmo padrão (E-07). |
| GET | `/api/abrangencia/compacta-vigente/{login}/perfil/{id_perfil}/DreDetalhes` | Escopo vigente, algoritmo alternativo, com DREs expandidas quando aplicável (E-08). |
| GET | `/api/abrangencia/compacta-vigente/{login}/perfil/{id_perfil}/Sondagem` | Escopo alternativo com DREs, UEs e turmas expandidas quando aplicável (E-09). |
| GET | `/api/abrangencia/compacta-semRedis/{login}/perfil/{id_perfil}` | Escopo pelo algoritmo alternativo, sem expandir DREs, UEs ou turmas (E-10). |

### Usuários por perfil

| Método | Endpoint | Descrição |
|---------|----------|-----------|
| POST | `/api/abrangencia/perfis/usuarios` | Lista os usuários lotados em uma UE, para os perfis informados (E-13). |

## Contratos principais

O endpoint de perfil retorna campos compatíveis com o legado: `grupoID`, `cargosId`, `funcoesId`, `grupo`, `abrangencia` e `ehPerfilManual`.

Os endpoints de escopo compacto retornam sempre as chaves `login`, `abrangencia`, `idDres`, `dres`, `idUes`, `ues`, `idTurmas` e `turmas`. Campos não expandidos retornam `null`; listas aplicáveis sem registros retornam `[]`.

O endpoint `perfis/usuarios` recebe:

```json
{
  "ue": "string",
  "dre": "string",
  "perfis": ["00000000-0000-0000-0000-000000000000"]
}
```

E retorna usuários agrupados por RF, preservando a chave legada `perfils`.
