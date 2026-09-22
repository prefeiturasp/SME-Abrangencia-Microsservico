# SME Abrangência Microsserviço

O microsserviço responde, para um perfil de acesso de um sistema (CoreSSO), até onde aquele perfil alcança em termos territoriais: quais DREs, quais Unidades Educacionais e quais turmas ele dá acesso a ver ou mexer. Não trata de vínculo empregatício (cargo/lotação real do servidor) — esse é um domínio distinto, descrito em outra frente do projeto Identidade.

O serviço é somente leitura: o schema (`perfil`, `perfil_vinculo_funcional` e as materialized views `mv_abrangencia_resolvida`, `mv_abrangencia_unidade` e `mv_abrangencia_usuarios_perfil`) é mantido pelo pipeline `sme-airflow`, versionado por Flyway. Este microsserviço nunca escreve nesse banco.

```{toctree}
:maxdepth: 2
:caption: Conteúdo

arquitetura/visao_geral
abrangencia/index
api
```
