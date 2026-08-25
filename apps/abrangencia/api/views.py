"""Views do domínio Abrangência."""

from uuid import UUID

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.abrangencia.constants import GUID_VAZIO
from apps.abrangencia.serializers import (
    AbrangenciaCompactaSerializer,
    BuscarUsuariosPerfisSerializer,
    DetalheErroSerializer,
    GrupoCargosSerializer,
    UsuarioPerfilsAbrangenciaSerializer,
)
from apps.abrangencia.services import AbrangenciaService

_TAG = ["Abrangência"]

_PARAM_PERFIL = OpenApiParameter(
    "id_perfil", str, OpenApiParameter.PATH, description="GUID do perfil."
)
_PARAM_LOGIN = OpenApiParameter(
    "login", str, OpenApiParameter.PATH, description="RF ou CPF do usuário."
)


def _perfil_invalido(id_perfil: str) -> bool:
    """Verifica se o GUID do perfil é vazio ou malformado."""
    if not id_perfil or id_perfil == GUID_VAZIO:
        return True
    try:
        UUID(id_perfil)
    except ValueError:
        return True
    return False


class PerfilView(APIView):
    """Consulta isolada de um perfil, sem depender de um usuário.

    Serve o mesmo payload que `_CompactaBaseView` aninha em `abrangencia`
    — reaproveitado via `AbrangenciaService.grupo_cargos`, ponto único de
    montagem desse objeto.
    """

    @extend_schema(
        tags=_TAG,
        parameters=[_PARAM_PERFIL],
        responses={
            200: GrupoCargosSerializer,
            204: None,
            400: DetalheErroSerializer,
        },
        operation_id="abrangencia_perfil",
    )
    def get(self, _request: Request, id_perfil: str) -> Response:
        """Retorna o perfil consultado."""
        if _perfil_invalido(id_perfil):
            return Response(
                {"detail": "O perfil é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        dados = AbrangenciaService().grupo_cargos(id_perfil)
        if dados is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(dados)


class _CompactaBaseView(APIView):
    """Base dos quatro endpoints de escopo compacto.

    As subclasses só alternam os quatro atributos de classe abaixo — todas
    chamam o mesmo `AbrangenciaService.abrangencia_compacta`, evitando que
    cada endpoint reimplemente a orquestração de perfil, escopo e
    expansões.
    """

    expandir_dres = False
    expandir_ues = False
    expandir_turmas = False
    algoritmo_alternativo = False

    def get(self, _request: Request, login: str, id_perfil: str) -> Response:
        """Retorna o escopo do usuário no perfil, conforme os atributos."""
        if _perfil_invalido(id_perfil):
            return Response(
                {"detail": "O perfil é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        dados = AbrangenciaService().abrangencia_compacta(
            login,
            id_perfil,
            expandir_dres=self.expandir_dres,
            expandir_ues=self.expandir_ues,
            expandir_turmas=self.expandir_turmas,
            algoritmo_alternativo=self.algoritmo_alternativo,
        )
        return Response(dados)


class CompactaVigenteView(_CompactaBaseView):
    """Retorna o escopo vigente do usuário no perfil."""

    @extend_schema(
        tags=_TAG,
        parameters=[_PARAM_LOGIN, _PARAM_PERFIL],
        responses={
            200: AbrangenciaCompactaSerializer,
            400: DetalheErroSerializer,
        },
        operation_id="abrangencia_compacta_vigente",
    )
    def get(self, request: Request, login: str, id_perfil: str) -> Response:
        return super().get(request, login, id_perfil)


class CompactaDreDetalhesView(_CompactaBaseView):
    """Retorna o escopo vigente pelo algoritmo alternativo."""

    algoritmo_alternativo = True

    @extend_schema(
        tags=_TAG,
        parameters=[_PARAM_LOGIN, _PARAM_PERFIL],
        responses={
            200: AbrangenciaCompactaSerializer,
            400: DetalheErroSerializer,
        },
        operation_id="abrangencia_compacta_dre_detalhes",
    )
    def get(self, request: Request, login: str, id_perfil: str) -> Response:
        return super().get(request, login, id_perfil)


class CompactaSondagemView(_CompactaBaseView):
    """Retorna o escopo vigente com as coleções expandidas."""

    expandir_dres = True
    expandir_ues = True
    expandir_turmas = True
    algoritmo_alternativo = True

    @extend_schema(
        tags=_TAG,
        parameters=[_PARAM_LOGIN, _PARAM_PERFIL],
        responses={
            200: AbrangenciaCompactaSerializer,
            400: DetalheErroSerializer,
        },
        operation_id="abrangencia_compacta_sondagem",
    )
    def get(self, request: Request, login: str, id_perfil: str) -> Response:
        return super().get(request, login, id_perfil)


class CompactaSemRedisView(_CompactaBaseView):
    """Retorna o escopo vigente sem passar por cache intermediário."""

    algoritmo_alternativo = True

    @extend_schema(
        tags=_TAG,
        parameters=[_PARAM_LOGIN, _PARAM_PERFIL],
        responses={
            200: AbrangenciaCompactaSerializer,
            400: DetalheErroSerializer,
        },
        operation_id="abrangencia_compacta_sem_redis",
    )
    def get(self, request: Request, login: str, id_perfil: str) -> Response:
        return super().get(request, login, id_perfil)


class PerfisUsuariosView(APIView):
    """Ponto de entrada que sustenta a listagem em massa por UE.

    Único endpoint deste domínio que recebe filtros no corpo em vez de na
    URL — a lista de perfis não cabe em um parâmetro de rota.
    """

    @extend_schema(
        tags=_TAG,
        request=BuscarUsuariosPerfisSerializer,
        responses={
            200: UsuarioPerfilsAbrangenciaSerializer(many=True),
            400: DetalheErroSerializer,
        },
        operation_id="abrangencia_perfis_usuarios",
    )
    def post(self, request: Request) -> Response:
        serializer = BuscarUsuariosPerfisSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dados = AbrangenciaService().usuarios_por_perfil(
            serializer.validated_data["ue"],
            serializer.validated_data.get("dre"),
            [str(perfil) for perfil in serializer.validated_data["perfis"]],
        )
        return Response(dados)
