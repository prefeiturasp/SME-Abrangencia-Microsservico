"""Modelos de leitura do dominio Abrangencia."""

from django.db import models

from apps.abrangencia.constants import ORIGEM_DRE_VIGENTE
from apps.core.models import ModeloBase


class Perfil(ModeloBase):
    """Perfil com o tipo de abrangencia que ele resolve."""

    perfil_guid = models.UUIDField(primary_key=True)
    grupo_codigo = models.IntegerField(unique=True)
    nome = models.TextField(null=True, blank=True)
    abrangencia_id = models.IntegerField(null=True, blank=True)
    eh_perfil_manual = models.BooleanField(default=False)
    eh_perfil_misto = models.BooleanField(default=False)
    atualizado_em = models.DateTimeField(null=True, blank=True)
    eh_grupo_manual = models.BooleanField(default=False)

    class Meta(ModeloBase.Meta):
        db_table = "perfil"
        verbose_name = "perfil"
        verbose_name_plural = "perfis"

    def __str__(self) -> str:
        return f"{self.perfil_guid} - {self.nome}"


class PerfilVinculoFuncional(ModeloBase):
    """Cargo ou funcao-atividade que concede um perfil."""

    pk = models.CompositePrimaryKey("perfil_guid", "tipo", "codigo")
    perfil_guid = models.UUIDField()
    tipo = models.TextField()
    codigo = models.IntegerField()
    atualizado_em = models.DateTimeField(null=True, blank=True)

    class Meta(ModeloBase.Meta):
        db_table = "perfil_vinculo_funcional"
        verbose_name = "vinculo funcional do perfil"
        verbose_name_plural = "vinculos funcionais do perfil"

    def __str__(self) -> str:
        return f"{self.perfil_guid} - {self.tipo} - {self.codigo}"


class AbrangenciaResolvida(ModeloBase):
    """Uma linha de escopo ja filtrada pelo perfil."""

    usuario_abrangencia_id = models.BigIntegerField(primary_key=True)
    login = models.TextField()
    perfil_guid = models.UUIDField()
    ano_letivo = models.IntegerField()
    tipo_resolucao = models.TextField()
    dre_codigo = models.TextField(null=True, blank=True)
    ue_codigo = models.TextField(null=True, blank=True)
    turma_codigo = models.TextField(null=True, blank=True)
    origem = models.TextField()
    grupo_codigo = models.IntegerField()
    grupo_nome = models.TextField(null=True, blank=True)
    tipo_abrangencia = models.IntegerField()
    eh_perfil_manual = models.BooleanField(default=False)
    eh_perfil_misto = models.BooleanField(default=False)

    class Meta(ModeloBase.Meta):
        db_table = "mv_abrangencia_resolvida"
        verbose_name = "abrangencia resolvida"
        verbose_name_plural = "abrangencias resolvidas"

    def __str__(self) -> str:
        return f"{self.login} - {self.perfil_guid} - {self.tipo_resolucao}"


class UsuarioPorPerfil(ModeloBase):
    """Usuario vigente em um perfil, por ano e UE."""

    pk = models.CompositePrimaryKey(
        "usuario_rf", "perfil_guid", "ano_letivo", "ue_codigo"
    )
    usuario_rf = models.TextField()
    perfil_guid = models.UUIDField()
    ano_letivo = models.IntegerField()
    ue_codigo = models.TextField()

    class Meta(ModeloBase.Meta):
        db_table = "mv_abrangencia_usuarios_perfil"
        verbose_name = "usuario por perfil"
        verbose_name_plural = "usuarios por perfil"

    def __str__(self) -> str:
        return f"{self.usuario_rf} - {self.perfil_guid} - {self.ue_codigo}"


class DreVigenteManager(models.Manager["DreVigenteUsuario"]):
    """Restringe a leitura de `usuario_abrangencia` a uma origem."""

    def get_queryset(self) -> models.QuerySet["DreVigenteUsuario"]:
        """Devolve so as linhas da origem da DRE vigente."""
        return super().get_queryset().filter(origem=ORIGEM_DRE_VIGENTE)


class DreVigenteUsuario(ModeloBase):
    """DRE da lotacao ativa de um servidor."""

    usuario_abrangencia_id = models.BigIntegerField(primary_key=True)
    login = models.TextField()
    ano_letivo = models.IntegerField()
    dre_codigo = models.TextField(null=True, blank=True)
    origem = models.TextField()

    objects = DreVigenteManager()

    class Meta(ModeloBase.Meta):
        db_table = "usuario_abrangencia"
        verbose_name = "dre vigente do usuario"
        verbose_name_plural = "dres vigentes dos usuarios"

    def __str__(self) -> str:
        return f"{self.login} - {self.dre_codigo}"


class Sistema(ModeloBase):
    """Sistema consumidor dos parametros; o de id 0 e o global."""

    sistema_id = models.IntegerField(primary_key=True)
    sistema = models.CharField(max_length=40)
    ativo = models.BooleanField(default=True)

    class Meta(ModeloBase.Meta):
        db_table = "sistema"
        verbose_name = "sistema"
        verbose_name_plural = "sistemas"

    def __str__(self) -> str:
        return f"{self.sistema_id} - {self.sistema}"


class ParametroSistema(ModeloBase):
    """Parametro de um sistema, por nome e ano letivo."""

    parametro_sistema_id = models.BigIntegerField(primary_key=True)
    sistema_id = models.IntegerField()
    nome = models.CharField(max_length=80)
    formato = models.CharField(max_length=20)
    categoria = models.CharField(max_length=20)
    descricao = models.CharField(max_length=200)
    valor = models.TextField()
    ano_letivo = models.IntegerField()
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(null=True, blank=True)
    alterado_em = models.DateTimeField(null=True, blank=True)

    class Meta(ModeloBase.Meta):
        db_table = "parametro_sistema"
        verbose_name = "parametro do sistema"
        verbose_name_plural = "parametros do sistema"

    def __str__(self) -> str:
        return f"{self.sistema_id} - {self.nome} - {self.ano_letivo}"
