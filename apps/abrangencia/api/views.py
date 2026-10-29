"""Views do domínio Abrangência."""

import logging
import re
from collections.abc import Callable
from typing import Any
from uuid import UUID

import httpx
from django.http import HttpResponse, JsonResponse
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.abrangencia.cache_repository import (
    IntegracaoEolCacheRepository,
    PerfilCacheRepository,
)
from apps.abrangencia.constants import GUID_VAZIO
from apps.abrangencia.integracao_eol import InstitucionalAPI, PedagogicoAPI
from apps.abrangencia.rede_sme import (
    RedeSmeIncompletaError,
    estrutura_vigente_por_dre,
)
from apps.abrangencia.serializers import (
    AbrangenciaCompactaSerializer,
    BuscarUsuariosPerfisSerializer,
    CicloEnsinoSerializer,
    DetalheErroSerializer,
    DreNomeAbreviacaoSerializer,
    EstruturaVigenteSerializer,
    GrupoCargosSerializer,
    UsuarioPerfilsAbrangenciaSerializer,
)
from apps.abrangencia.services import AbrangenciaService
from apps.core.api.responses import (
    resposta_detalhe,
    resposta_externa,
    resposta_indisponivel,
    sem_conteudo,
)
from apps.core.api.views import APIExternaView

logger = logging.getLogger(__name__)

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
    """Perfil e seus vínculos."""

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
        cache = PerfilCacheRepository()
        dados = cache.obter_perfil(id_perfil)
        if dados is None:
            dados = AbrangenciaService().grupo_cargos(id_perfil)
            if dados is None:
                return Response(status=status.HTTP_204_NO_CONTENT)
            cache.armazenar_perfil(id_perfil, dados)
        return Response(dados)


class _RedeSmeView(APIExternaView):
    """Base das views que leem DREs, UEs e turmas."""

    dominio = "DREs, UEs e turmas"

    def handle_exception(self, exc: Exception) -> Response:
        if isinstance(exc, RedeSmeIncompletaError):
            logger.error("Rede SME incompleta: %s", exc)
            return resposta_indisponivel(self.dominio)
        if isinstance(exc, httpx.HTTPStatusError):
            logger.warning(
                "Respondeu %s em %s",
                exc.response.status_code,
                exc.request.url,
            )
            return resposta_indisponivel(self.dominio)
        return super().handle_exception(exc)


class _CompactaBaseView(_RedeSmeView):
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
            503: DetalheErroSerializer,
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
            503: DetalheErroSerializer,
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
            503: DetalheErroSerializer,
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
            503: DetalheErroSerializer,
        },
        operation_id="abrangencia_compacta_sem_redis",
    )
    def get(self, request: Request, login: str, id_perfil: str) -> Response:
        return super().get(request, login, id_perfil)


class PerfisUsuariosView(_RedeSmeView):
    """Lista usuários e seus perfis a partir de uma UE e DRE."""

    @extend_schema(
        tags=_TAG,
        request=BuscarUsuariosPerfisSerializer,
        responses={
            200: UsuarioPerfilsAbrangenciaSerializer(many=True),
            400: DetalheErroSerializer,
            503: DetalheErroSerializer,
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
_JSON_COMPACTO = {"separators": (",", ":"), "ensure_ascii": False}


def _repasse_com_cache(
    chave: str, buscar: Callable[[], httpx.Response]
) -> HttpResponse:
    """Repassa o retorno do cache."""
    cache = IntegracaoEolCacheRepository()
    guardada = cache.obter_lista(chave)
    if guardada is not None:
        return JsonResponse(
            guardada, safe=False, json_dumps_params=_JSON_COMPACTO
        )
    resposta = buscar()
    if sem_conteudo(resposta):
        return HttpResponse(status=status.HTTP_204_NO_CONTENT)
    if resposta.status_code == status.HTTP_200_OK:
        try:
            corpo = resposta.json()
        except ValueError:
            corpo = None
        if isinstance(corpo, list):
            cache.armazenar_lista(chave, corpo)
    return resposta_externa(resposta)


class CodigosDresView(APIExternaView):
    """Lista os códigos da DREs."""

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
        """Retorna os códigos das DREs, do cache do Institucional."""
        resposta = InstitucionalAPI().codigos_dres()
        if sem_conteudo(resposta):
            return HttpResponse(status=status.HTTP_204_NO_CONTENT)
        return resposta_externa(resposta)


class DresNomeAbreviacaoView(APIExternaView):
    """Lista código, nome e abreviação das DREs."""

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
        """Retorna nome e abreviação das DREs, guardados por 24 horas."""
        return _repasse_com_cache(
            IntegracaoEolCacheRepository.CHAVE_NOME_ABREVIACAO_DRES,
            InstitucionalAPI().dres_nome_abreviacao,
        )


_MSG_CODIGO_DRE_OBRIGATORIO = "O codigo da Dre é obrigatório"
_MSG_TURMA_OBRIGATORIA = "É necessário informar ao menos uma turma"
_CODIGO_NUMERICO = re.compile(r"[0-9]+")

_RESPOSTAS_ESTRUTURA = {
    200: EstruturaVigenteSerializer,
    204: None,
    400: DetalheErroSerializer,
    503: DetalheErroSerializer,
}


def _numerico(valor: str) -> bool:
    """Verifica se valor contém apenas números."""
    return _CODIGO_NUMERICO.fullmatch(valor) is not None


def _codigos_turma(corpo: Any) -> list[int]:
    """Extrai os códigos numéricos ignorando os demais itens."""
    if not isinstance(corpo, list):
        return []
    codigos = (str(item).strip() for item in corpo)
    return [int(codigo) for codigo in codigos if _numerico(codigo)]


def _resposta_estrutura(dados: dict[str, Any]) -> Response:
    """Monta a resposta HTTP com os dados ou status 204 se estiver vazio."""
    if not dados["dres"]:
        return Response(status=status.HTTP_204_NO_CONTENT)
    return Response(dados)


class EstruturaVigentePorDreView(APIExternaView):
    """Estrutura vigente de uma DRE."""

    dominio = PedagogicoAPI.nome

    @extend_schema(
        tags=_TAG,
        parameters=[
            OpenApiParameter(
                "codigo_dre",
                str,
                OpenApiParameter.PATH,
                description="Código EOL da DRE.",
            )
        ],
        responses=_RESPOSTAS_ESTRUTURA,
        operation_id="abrangencia_estrutura_vigente_por_dre",
    )
    def get(self, _request: Request, codigo_dre: str) -> Response:
        """Retorna DRE, UE e turma vigente da DRE."""
        codigo_dre = codigo_dre.strip()
        if not codigo_dre:
            return resposta_detalhe(_MSG_CODIGO_DRE_OBRIGATORIO)
        if not _numerico(codigo_dre):
            return Response(status=status.HTTP_204_NO_CONTENT)
        dados = estrutura_vigente_por_dre(codigo_dre)
        return _resposta_estrutura(dados)


class EstruturaVigenteView(APIExternaView):
    """Estrutura vigente de uma lista de códigos de turmas."""

    dominio = PedagogicoAPI.nome

    @extend_schema(
        tags=_TAG,
        request=serializers.ListSerializer(child=serializers.CharField()),
        responses=_RESPOSTAS_ESTRUTURA,
        operation_id="abrangencia_estrutura_vigente_por_turmas",
    )
    def post(self, request: Request) -> Response:
        """Retorna a árvore DRE -> UE -> turma vigente das turmas."""
        codigos = _codigos_turma(request.data)
        if not codigos:
            return resposta_detalhe(_MSG_TURMA_OBRIGATORIA)
        dados = PedagogicoAPI().estrutura_vigente_por_turmas(codigos)
        return _resposta_estrutura(dados)


class CicloEnsinoView(APIExternaView):
    """Lista os ciclos de ensino."""

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
