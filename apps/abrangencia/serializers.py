"""Serializers do domínio Abrangência.

As chaves saem em camelCase porque são contrato externo, não escolha de
estilo. `allow_null=True` é explícito em toda coleção de escopo: `null` e
`[]` são valores distintos do contrato, e a escolha depende do ramo do
perfil consultado.
"""

from rest_framework import serializers


class GrupoCargosSerializer(serializers.Serializer):
    """Representa o perfil e os vínculos funcionais que o concedem."""

    grupoID = serializers.CharField()  # noqa: N815
    cargosId = serializers.ListField(  # noqa: N815
        child=serializers.IntegerField()
    )
    funcoesId = serializers.ListField(  # noqa: N815
        child=serializers.IntegerField()
    )
    grupo = serializers.IntegerField()
    abrangencia = serializers.IntegerField()
    ehPerfilManual = serializers.BooleanField()  # noqa: N815


class DreExpandidaSerializer(serializers.Serializer):
    """Representa uma DRE da coleção expandida de sondagem.

    `nomeDRE` e `siglaDRE` saem sempre `null`: este serviço guarda apenas
    o código, que é o que decide abrangência.
    """

    codigoDRE = serializers.CharField(allow_null=True)  # noqa: N815
    nomeDRE = serializers.CharField(allow_null=True)  # noqa: N815
    siglaDRE = serializers.CharField(allow_null=True)  # noqa: N815


class UeExpandidaSerializer(serializers.Serializer):
    """Representa uma UE da coleção expandida de sondagem.

    `codigoDRE`, `nome` e `sigla` saem sempre `null`: este serviço guarda
    apenas o código.
    """

    codigo = serializers.CharField(allow_null=True)
    codigoDRE = serializers.CharField(allow_null=True)  # noqa: N815
    nome = serializers.CharField(allow_null=True)
    sigla = serializers.CharField(allow_null=True)


class TurmaExpandidaSerializer(serializers.Serializer):
    """Representa uma turma da coleção expandida de sondagem.

    `codigo` é emitido como texto, embora o contrato o declare numérico:
    convertê-lo perderia zeros à esquerda.
    """

    codigo = serializers.CharField(allow_null=True)
    nome = serializers.CharField(allow_null=True)
    codigoEscola = serializers.CharField(allow_null=True)  # noqa: N815


class AbrangenciaCompactaSerializer(serializers.Serializer):
    """Representa o escopo de um usuário em um perfil.

    As oito chaves estão sempre presentes. O nível que o ramo não resolve sai
    `null` ou `[]` conforme o ramo, e as coleções expandidas só se preenchem
    quando explicitamente solicitadas (endpoint de sondagem).
    """

    login = serializers.CharField()
    abrangencia = GrupoCargosSerializer(allow_null=True)
    idDres = serializers.ListField(  # noqa: N815
        child=serializers.CharField(), allow_null=True
    )
    dres = DreExpandidaSerializer(many=True, allow_null=True)
    idUes = serializers.ListField(  # noqa: N815
        child=serializers.CharField(), allow_null=True
    )
    ues = UeExpandidaSerializer(many=True, allow_null=True)
    idTurmas = serializers.ListField(  # noqa: N815
        child=serializers.CharField(), allow_null=True
    )
    turmas = TurmaExpandidaSerializer(many=True, allow_null=True)


class PerfilAbrangenciaSerializer(serializers.Serializer):
    """Representa um perfil do usuário e as UEs em que ele o exerce."""

    perfil = serializers.CharField()
    ues = serializers.ListField(child=serializers.CharField())


class UsuarioPerfilsAbrangenciaSerializer(serializers.Serializer):
    """Representa um usuário e seus perfis na UE consultada.

    `perfils`, sem o `i`, é a grafia mantida pelo contrato consumido pelos
    sistemas integrados — corrigi-la quebraria quem já consome esta API.
    """

    usuarioRf = serializers.CharField()  # noqa: N815
    perfils = PerfilAbrangenciaSerializer(many=True)


class BuscarUsuariosPerfisSerializer(serializers.Serializer):
    """Valida o corpo da busca de usuários por perfil.

    `ue` e `perfis` são obrigatórios; `dre` é opcional.
    """

    ue = serializers.CharField()
    dre = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, default=None
    )
    perfis = serializers.ListField(
        child=serializers.UUIDField(), allow_empty=False
    )


class DetalheErroSerializer(serializers.Serializer):
    """Corpo de erro genérico, usado nas respostas 400 deste domínio."""

    detail = serializers.CharField()
