"""Modelos de leitura do dominio Abrangencia."""

from django.db import models

from apps.core.models import ModeloBase


class Perfil(ModeloBase):
    """Perfil com o tipo de abrangencia que ele resolve."""

    perfil_guid = models.UUIDField(primary_key=True)
    grupo_codigo = models.IntegerField(unique=True)
    nome = models.TextField(null=True, blank=True)
    tipo_abrangencia = models.IntegerField()
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
    tipo_escopo = models.TextField()
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
        return (
            f"{self.login} - {self.perfil_guid} - "
            f"{self.tipo_resolucao}/{self.tipo_escopo}"
        )


class Unidade(ModeloBase):
    """Nome, sigla e vinculo de uma unidade, por ano e tipo de escopo."""

    pk = models.CompositePrimaryKey("ano_letivo", "tipo_escopo", "codigo")
    ano_letivo = models.IntegerField()
    tipo_escopo = models.TextField()
    codigo = models.TextField()
    nome = models.TextField(null=True, blank=True)
    sigla = models.TextField(null=True, blank=True)
    dre_codigo_pai = models.TextField(null=True, blank=True)
    ue_codigo_pai = models.TextField(null=True, blank=True)
    elegivel_sondagem = models.BooleanField(default=False)

    class Meta(ModeloBase.Meta):
        db_table = "mv_abrangencia_unidade"
        verbose_name = "unidade"
        verbose_name_plural = "unidades"

    def __str__(self) -> str:
        return f"{self.ano_letivo} - {self.tipo_escopo} - {self.codigo}"


class UsuarioPorPerfil(ModeloBase):
    """Usuario vigente em um perfil, por ano, UE e DRE."""

    pk = models.CompositePrimaryKey(
        "usuario_rf", "perfil_guid", "ano_letivo", "ue_codigo", "dre_codigo"
    )
    usuario_rf = models.TextField()
    perfil_guid = models.UUIDField()
    ano_letivo = models.IntegerField()
    ue_codigo = models.TextField()
    dre_codigo = models.TextField()

    class Meta(ModeloBase.Meta):
        db_table = "mv_abrangencia_usuarios_perfil"
        verbose_name = "usuario por perfil"
        verbose_name_plural = "usuarios por perfil"

    def __str__(self) -> str:
        return f"{self.usuario_rf} - {self.perfil_guid} - {self.ue_codigo}"
