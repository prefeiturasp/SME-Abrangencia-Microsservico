# Visão Geral

## Objetivo

O **SME-Abrangencia-Microsservico** é responsável por resolver a abrangência territorial de um perfil de acesso: quais DREs, quais Unidades Educacionais e quais turmas aquele perfil possui acesso.

Este é um domínio distinto do vínculo funcional de um servidor (cargo, lotação real, vínculo empregatício) esse último é tratado em outra frente do projeto Identidade, a partir do banco legado SE1426, e não é responsabilidade deste serviço.

## Papel na arquitetura

O serviço é **somente leitura**: o schema (`perfil`, `perfil_vinculo_funcional` e as materialized views `mv_abrangencia_resolvida`, `mv_abrangencia_unidade` e `mv_abrangencia_usuarios_perfil`) é populado e mantido pelo pipeline `sme-airflow`, com as migrations versionadas por Flyway do lado do pipeline. Este microsserviço nunca escreve nesse banco, nem gera migration para essas tabelas todos os models Django são `managed = False`.

```text
CoreSSO / API EOL legada
        │
        │  extração e agregação (sme-airflow, Flyway)
        ▼
+---------------------------+
|  Banco de Abrangência     |
|  (perfil, vínculos e      |
|   materialized views)     |
+-------------+-------------+
              │
              │  leitura via ORM (managed=False)
              ▼
+---------------------------+
| SME-Abrangencia-          |
| Microsservico             |
|                           |
| • Models managed=False    |
| • Service (projeção       |
|   de escopo por ramo)     |
| • API REST                |
+-------------+-------------+
              │
              ▼
     Sistemas consumidores
     (ex. SME-Identidade-
     Token-Microsservico)
```

## Principais responsabilidades

- Consultar o perfil e os cargos/funções que o concedem (`GrupoCargosDTO`).
- Projetar as linhas de `mv_abrangencia_resolvida` no ramo correto de `TipoAbrangencia` (UE, Professor, DRE, SME etc.), zerando os níveis que aquele ramo não resolve.
- Suportar os dois algoritmos de resolução de escopo já existentes no legado (padrão e alternativo), que divergem por design em alguns ramos.
- Expandir DREs, UEs e turmas a partir de `mv_abrangencia_unidade` quando solicitado.
- Listar usuários lotados em uma UE/DRE para um conjunto de perfis.

## Limites de responsabilidade

O SME-Abrangencia-Microsservico **não** é responsável por:

- Extrair ou consolidar dados do CoreSSO ou da API EOL isso é feito pelo pipeline `sme-airflow`.
- Persistir vínculo funcional de servidor (cargo, lotação real, contrato externo) domínio distinto, tratado por outro serviço.
- Autenticar usuários finais ou emitir tokens isso é responsabilidade do Keycloak e do Token-Microsservico.

## Domínios da aplicação

| Domínio | Responsabilidade |
|---|---|
| Core | Autenticação por API Key e health check. |
| Abrangência | Consulta de perfis, projeção de escopo territorial e listagem de usuários por perfil. |
