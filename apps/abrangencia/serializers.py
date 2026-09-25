"""Serializers do domínio Abrangência."""

from drf_spectacular.utils import OpenApiExample, extend_schema_serializer
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
    """Representa detalhes da DRE."""

    codigoDRE = serializers.CharField(allow_null=True)  # noqa: N815
    nomeDRE = serializers.CharField(allow_null=True)  # noqa: N815
    siglaDRE = serializers.CharField(allow_null=True)  # noqa: N815


class UeExpandidaSerializer(serializers.Serializer):
    """Representa detalhes da UE."""

    codigo = serializers.CharField(allow_null=True)
    codigoDRE = serializers.CharField(allow_null=True)  # noqa: N815
    nome = serializers.CharField(allow_null=True)
    sigla = serializers.CharField(allow_null=True)


class TurmaExpandidaSerializer(serializers.Serializer):
    """Representa detalhes da turma."""

    codigo = serializers.CharField(allow_null=True)
    nome = serializers.CharField(allow_null=True)
    codigoEscola = serializers.CharField(allow_null=True)  # noqa: N815


class AbrangenciaCompactaSerializer(serializers.Serializer):
    """Representa o escopo de um usuário em um perfil."""

    login = serializers.CharField()
    abrangencia = GrupoCargosSerializer(allow_null=True)
    idDres = serializers.ListField(  # noqa: N815
        child=serializers.CharField(), allow_null=True
    )
    dres = DreExpandidaSerializer(many=True, allow_null=True)
    idUes = serializers.ListField(  # noqa: N815
        child=serializers.CharField(allow_null=True), allow_null=True
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
    """Representa um usuário e seus perfis na UE consultada."""

    usuarioRf = serializers.CharField()  # noqa: N815
    perfils = PerfilAbrangenciaSerializer(many=True)


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Payload legado",
            value={
                "ue": "string",
                "dre": "string",
                "perfis": ["string"],
            },
            request_only=True,
        )
    ]
)
class BuscarUsuariosPerfisSerializer(serializers.Serializer):
    """Valida o corpo da busca de usuários por perfil."""

    ue = serializers.CharField()
    dre = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, default=None
    )
    perfis = serializers.ListField(
        child=serializers.UUIDField(), allow_empty=False
    )


class DreNomeAbreviacaoSerializer(serializers.Serializer):
    """Representa uma DRE da rede com nome e abreviação."""

    codigo = serializers.CharField()
    nome = serializers.CharField(allow_null=True)
    abreviacao = serializers.CharField(allow_null=True)


class CicloEnsinoSerializer(serializers.Serializer):
    """Representa um ciclo de ensino."""

    codigoModalidadeEnsino = serializers.IntegerField()  # noqa: N815
    codigoEtapaEnsino = serializers.IntegerField()  # noqa: N815
    codigo = serializers.IntegerField()
    descricao = serializers.CharField()
    dtAtualizacao = serializers.CharField()  # noqa: N815


class DetalheErroSerializer(serializers.Serializer):
    """Corpo de erro genérico, usado nas respostas 400 e 503 do domínio."""

    detail = serializers.CharField()
