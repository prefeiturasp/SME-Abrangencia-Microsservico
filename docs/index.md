# SME Abrangência Microsserviço

O microsserviço responde o acesso que perfil alcança: quais DREs, quais Unidades Educacionais e quais turmas ele possui. Não trata de vínculo empregatício (cargo/lotação real do servidor).

O serviço é somente leitura: o schema (`perfil`, `perfil_vinculo_funcional`, `sistema`, `parametro_sistema` e as materialized views `mv_abrangencia_resolvida` e `mv_abrangencia_usuarios_perfil`) é mantido pelo pipeline `sme-airflow`, versionado por Flyway. Nome, sigla e hierarquia de DREs, UEs e turmas vêm do MS Institucional e do MS Pedagógico.

```{toctree}
:maxdepth: 2
:caption: Conteúdo

arquitetura/visao_geral
abrangencia/index
api
```
