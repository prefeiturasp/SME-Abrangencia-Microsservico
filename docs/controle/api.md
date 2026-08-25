# API

Esta seção apresenta uma visão geral dos recursos disponibilizados pelo **SME-Abrangencia-Microsservico**.

## Autenticação

Todos os endpoints protegidos utilizam autenticação por **API Key**.

A chave deve ser enviada no cabeçalho HTTP configurado pela variável de ambiente `API_KEY_HEADER`.

Exemplo:

```text
X-API-Key: <API_KEY>
```

Caso a chave seja inválida ou esteja ausente, a requisição será rejeitada com **HTTP 401 (Unauthorized)**.

## Recursos disponíveis

### Health Check

| Método | Endpoint | Descrição |
|---------|----------|-----------|
| GET | `/abrangencia/api/v1/health/` | Verifica se o serviço está disponível. |

---

### Perfil

| Método | Endpoint | Descrição |
|---------|----------|-----------|
| GET | `/abrangencia/api/v1/{id_perfil}` | Retorna o perfil e os cargos/funções que o concedem. |

### Escopo compacto de um usuário em um perfil

| Método | Endpoint | Descrição |
|---------|----------|-----------|
| GET | `/abrangencia/api/v1/compacta-vigente/{login}/perfil/{id_perfil}` | Escopo vigente, algoritmo padrão (E-07). |
| GET | `/abrangencia/api/v1/compacta-vigente/{login}/perfil/{id_perfil}/DreDetalhes` | Escopo vigente, algoritmo alternativo (E-08). |
| GET | `/abrangencia/api/v1/compacta-vigente/{login}/perfil/{id_perfil}/Sondagem` | Escopo com DREs, UEs e turmas expandidas (E-09). |
| GET | `/abrangencia/api/v1/compacta-semRedis/{login}/perfil/{id_perfil}` | Escopo pelo algoritmo alternativo, sem cache (E-10). |

### Usuários por perfil

| Método | Endpoint | Descrição |
|---------|----------|-----------|
| POST | `/abrangencia/api/v1/perfis/usuarios` | Lista os usuários lotados em uma UE, para os perfis informados (E-13). |

---

# OpenAPI

A documentação completa da API pode ser consultada através do Swagger da aplicação, em:

- `/abrangencia/api/v1/docs/`
