"""Views do domínio Abrangência."""

from uuid import UUID

from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.abrangencia.constants import GUID_VAZIO
from apps.abrangencia.integracao_eol import InstitucionalAPI, PedagogicoAPI
from apps.abrangencia.serializers import (
    AbrangenciaCompactaSerializer,
    BuscarUsuariosPerfisSerializer,
    CicloEnsinoSerializer,
    DetalheErroSerializer,
    DreNomeAbreviacaoSerializer,
    GrupoCargosSerializer,
    UsuarioPerfilsAbrangenciaSerializer,
)
from apps.abrangencia.services import AbrangenciaService
from apps.core.api.responses import (
    resposta_detalhe,
    resposta_externa,
    sem_conteudo,
)
from apps.core.api.views import APIExternaView

_TAG = ["Abrangencia"]

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
    """Consulta isolada de um perfil, sem depender de um usuário."""

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
        """Retorna os vínculos funcionais e a abrangência do perfil."""
        if _perfil_invalido(id_perfil):
            return resposta_detalhe("O perfil é obrigatório.")
        dados = AbrangenciaService().grupo_cargos(id_perfil)
        if dados is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(dados)


class _CompactaBaseView(APIView):
    """Base dos quatro endpoints de escopo compacto."""

    expandir_dres = False
    expandir_ues = False
    expandir_turmas = False
    algoritmo_alternativo = False

    def get(self, _request: Request, login: str, id_perfil: str) -> Response:
        """Retorna as DREs, UEs e turmas a partir do login e perfil."""
        if _perfil_invalido(id_perfil):
            return resposta_detalhe("O perfil é obrigatório.")
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
    """Serve escopo vigente, sem expandir nenhuma lista."""

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
    """Serve escopo alternativo com a lista de DREs expandida."""

    expandir_dres = True
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
        """Retorna detalhes de DREs a partir do login e perfil."""
        return super().get(request, login, id_perfil)


class CompactaSondagemView(_CompactaBaseView):
    """Serve escopo alternativo com as três coleções expandidas."""

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
        """Retorna turmas elegíveis para sondagem do login e perfil."""
        return super().get(request, login, id_perfil)


class CompactaSemRedisView(_CompactaBaseView):
    """Serve escopo alternativo, sem expandir nenhuma lista."""

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
    """Lista usuários e seus perfis a partir de uma UE e DRE."""

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


_RESPOSTAS_DRES = {204: None, 503: DetalheErroSerializer}


class CodigosDresView(APIExternaView):
    dominio = InstitucionalAPI.nome

    @extend_schema(
        tags=_TAG,
        responses={
            200: serializers.ListSerializer(child=serializers.CharField()),
            **_RESPOSTAS_DRES,
        },
        operation_id="abrangencia_codigos_dres",
    )
    def get(self, _request: Request) -> HttpResponse:
        """Retorna os códigos das DREs."""
        resposta = InstitucionalAPI().codigos_dres()
        if sem_conteudo(resposta):
            return HttpResponse(status=status.HTTP_204_NO_CONTENT)
        return resposta_externa(resposta)


class DresNomeAbreviacaoView(APIExternaView):
    dominio = InstitucionalAPI.nome

    @extend_schema(
        tags=_TAG,
        responses={
            200: DreNomeAbreviacaoSerializer(many=True),
            **_RESPOSTAS_DRES,
        },
        operation_id="abrangencia_nome_abreviacao_dres",
    )
    def get(self, _request: Request) -> HttpResponse:
        """Retorna nome e abreviação das DREs."""
        resposta = InstitucionalAPI().dres_nome_abreviacao()
        if sem_conteudo(resposta):
            return HttpResponse(status=status.HTTP_204_NO_CONTENT)
        return resposta_externa(resposta)


class CicloEnsinoView(APIExternaView):
    dominio = PedagogicoAPI.nome

    @extend_schema(
        tags=_TAG,
        responses={
            200: CicloEnsinoSerializer(many=True),
            503: DetalheErroSerializer,
        },
        operation_id="abrangencia_ciclo_ensino",
    )
    def get(self, _request: Request) -> HttpResponse:
        """Retorna os ciclos de ensino."""
        resposta = PedagogicoAPI().ciclos_ensino()
        if sem_conteudo(resposta):
            return HttpResponse(b"[]", content_type="application/json")
        return resposta_externa(resposta)
