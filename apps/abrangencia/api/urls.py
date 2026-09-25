"""Rotas do domínio Abrangência."""

from django.urls import path

from apps.abrangencia.api.views import (
    CicloEnsinoView,
    CodigosDresView,
    CompactaDreDetalhesView,
    CompactaSemRedisView,
    CompactaSondagemView,
    CompactaVigenteView,
    DresNomeAbreviacaoView,
    PerfilView,
    PerfisUsuariosView,
)

urlpatterns = [
    path("codigos-dres/", CodigosDresView.as_view(), name="codigos-dres"),
    path(
        "nome-abreviacao-dres/",
        DresNomeAbreviacaoView.as_view(),
        name="nome-abreviacao-dres",
    ),
    path("ciclo-ensino/", CicloEnsinoView.as_view(), name="ciclo-ensino"),
    path(
        "perfis/usuarios",
        PerfisUsuariosView.as_view(),
        name="perfis-usuarios",
    ),
    path(
        "compacta-vigente/<str:login>/perfil/<str:id_perfil>/DreDetalhes/",
        CompactaDreDetalhesView.as_view(),
        name="compacta-vigente-dre-detalhes",
    ),
    path(
        "compacta-vigente/<str:login>/perfil/<str:id_perfil>/Sondagem/",
        CompactaSondagemView.as_view(),
        name="compacta-vigente-sondagem",
    ),
    path(
        "compacta-vigente/<str:login>/perfil/<str:id_perfil>/",
        CompactaVigenteView.as_view(),
        name="compacta-vigente",
    ),
    path(
        "compacta-semRedis/<str:login>/perfil/<str:id_perfil>/",
        CompactaSemRedisView.as_view(),
        name="compacta-sem-redis",
    ),
    path("<str:id_perfil>/", PerfilView.as_view(), name="perfil"),
]
