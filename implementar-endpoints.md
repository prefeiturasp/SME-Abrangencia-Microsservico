### GET /api/abrangencia/codigos-dres/
```
[
  "000001",
   ...
]
```
---
### GET /api/abrangencia/nome-abreviacao-dres/
```json
[
  {
    "codigo": "000001",
    "nome": "NOME DRE",
    "abreviacao": "SIGLA DRE"
  }
]
```
---

### GET /api/abrangencia/estrutura-vigente/{codigo_dre}/ | POST api/abrangencia/estrutura-vigente/{codigo_dre}

```json
{
        "dres": [
            {
                "abreviacao": "string",
                "codigo": "string",
                "nome": "string",
                "ues": [
                    {
                        "codigo": "string",
                        "nome": "string",
                        "codTipoEscola": 0,
                        "turmas": [
                            {
                                "ano": "string",
                                "anoLetivo": 0,
                                "codigo": 0,
                                "tipoTurma": 0,
                                "modalidade": "string",
                                "codigoModalidade": 0,
                                "nomeTurma": "string",
                                "semestre": 0,
                                "duracaoTurno": 0,
                                "tipoTurno": 0,
                                "dataFim": "2026-07-29T00:00:00.000Z",
                                "ehistorico": true,
                                "ensinoEspecial": true,
                                "etapaEJA": 0,
                                "serieEnsino": "string",
                                "dataInicioTurma": "2026-07-29T00:00:00.000Z",
                                "extinta": true,
                                "situacao": "string",
                                "ueCodigo": "string"
                            }
                        ]
                    }
                ]
            }
        ]
}
```
---

### GET /api/abrangencia/ciclo-ensino
```json
[
  {
    "codigoModalidadeEnsino": 0,
    "codigoEtapaEnsino": 0,
    "codigo": 0,
    "descricao": "DESCRICAO",
    "dtAtualizacao": "2011-01-21T19:10:37.937"
  }
]
```

