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

As rotas `GET` são registradas com barra final; o `POST` `perfis/usuarios` não, como no legado, porque o redirecionamento para a barra final não vale para `POST`.

## `Content-Type`

São aceitos os mesmos content-types JSON da API legada:

| `Content-Type` | Resultado |
|----------------|-----------|
| `application/json` | aceito |
| `text/json` | aceito, lido como JSON |
| `application/json-patch+json` | aceito, lido como JSON comum |
| qualquer outro | **415** |

`application/json-patch+json` é aceito apenas como cabeçalho: o corpo é o mesmo JSON dos demais, e nenhuma operação de JSON Patch é aplicada.

**Divergência deliberada:** o Swagger do legado também lista o coringa `application/*+json`, que aqui **não** é reproduzido — `application/vnd.qualquer+json` responde 415. O coringa vem da configuração padrão do framework no legado, e não há consumidor conhecido que envie sufixo próprio.

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
| GET | `/api/abrangencia/compacta-vigente/{login}/perfil/{id_perfil}/` | Escopo vigente, algoritmo padrão. |
| GET | `/api/abrangencia/compacta-vigente/{login}/perfil/{id_perfil}/DreDetalhes/` | Escopo vigente, algoritmo alternativo, com DREs expandidas quando aplicável. |
| GET | `/api/abrangencia/compacta-vigente/{login}/perfil/{id_perfil}/Sondagem/` | Escopo alternativo com DREs, UEs e turmas expandidas quando aplicável. |
| GET | `/api/abrangencia/compacta-semRedis/{login}/perfil/{id_perfil}/` | Escopo pelo algoritmo alternativo, sem expandir DREs, UEs ou turmas. |

### Usuários por perfil

| Método | Endpoint | Descrição |
|---------|----------|-----------|
| POST | `/api/abrangencia/perfis/usuarios` | Lista os usuários lotados em uma UE, para os perfis informados (E-13). |

### DREs e ciclo de ensino

Vêm de APIs da IntegracaoEOL; nenhuma dessas rotas lê o banco de abrangência.

| Método | Endpoint | Descrição | API de origem |
|---------|----------|-----------|---------------|
| GET | `/api/abrangencia/codigos-dres/` | Lista de códigos das DREs (E-02). | SME-IntegracaoEOL-Institucional-Microsservico |
| GET | `/api/abrangencia/nome-abreviacao-dres/` | DREs com `codigo`, `nome` e `abreviacao` (E-03). | SME-IntegracaoEOL-Institucional-Microsservico |
| GET | `/api/abrangencia/ciclo-ensino/` | Catálogo de ciclos de ensino (E-12). | SME-IntegracaoEOL-Pedagogico-Microsservico |

As três rotas devolvem o retorno como a API de origem o entrega.

Variáveis de cada API: `INSTITUCIONAL_API_URL`, `INSTITUCIONAL_API_KEY`, `PEDAGOGICO_API_URL` e `PEDAGOGICO_API_KEY`. A URL inclui o prefixo da API (`https://<host>/api/v1/institucional`, `https://<host>/api/v1/pedagogico`). A chave vai sempre no header `X-API-Key`. URL vazia não impede o serviço de subir: a rota responde 503.

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
