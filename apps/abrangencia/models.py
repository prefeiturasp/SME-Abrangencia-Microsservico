"""Modelos de leitura do domínio Abrangência."""

import json
from typing import Any, cast

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.backends.base.base import BaseDatabaseWrapper

from apps.core.models import ModeloBase


class Perfil(ModeloBase):
    """Perfil do CoreSSO, com o ramo de abrangência que ele resolve."""

    perfil_guid = models.UUIDField(primary_key=True)
    grupo_codigo = models.IntegerField(unique=True)
    nome = models.TextField(null=True, blank=True)
    tipo_abrangencia = models.IntegerField()
    eh_perfil_manual = models.BooleanField(default=False)
    eh_perfil_misto = models.BooleanField(default=False)
    atualizado_em = models.DateTimeField(null=True, blank=True)

    class Meta(ModeloBase.Meta):
        db_table = "perfil"
        verbose_name = "perfil"
        verbose_name_plural = "perfis"

    def __str__(self) -> str:
        return f"{self.perfil_guid} - {self.nome}"


class PerfilVinculoFuncional(ModeloBase):
    """Cargo ou função-atividade que concede um perfil."""

    # `perfil_guid` sozinho não é único: um perfil é concedido por
    # vários cargos.
    pk = models.CompositePrimaryKey("perfil_guid", "tipo", "codigo")
    perfil_guid = models.UUIDField()
    tipo = models.TextField()
    codigo = models.IntegerField()
    atualizado_em = models.DateTimeField(null=True, blank=True)

    class Meta(ModeloBase.Meta):
        db_table = "perfil_vinculo_funcional"
        verbose_name = "vínculo funcional do perfil"
        verbose_name_plural = "vínculos funcionais do perfil"

    def __str__(self) -> str:
        return f"{self.perfil_guid} - {self.tipo} - {self.codigo}"


class UsuarioAbrangencia(ModeloBase):
    """Fato de abrangência: um nível de escopo de um usuário, por origem."""

    usuario_abrangencia_id = models.BigAutoField(primary_key=True)
    login = models.TextField()
    perfil_guid = models.UUIDField()
    ano_letivo = models.IntegerField()
    dre_codigo = models.TextField(null=True, blank=True)
    ue_codigo = models.TextField(null=True, blank=True)
    turma_codigo = models.TextField(null=True, blank=True)
    origem = models.TextField()
    tipo_login = models.TextField(default="RF")
    nivel_abrangencia = models.TextField()
    cargo_codigo = models.IntegerField(null=True, blank=True)
    funcao_atividade_codigo = models.IntegerField(null=True, blank=True)
    componente_curricular_codigo = models.BigIntegerField(
        null=True, blank=True
    )
    regencia_turma = models.BooleanField(default=False)
    codigo_dre_normalizado = models.BooleanField(default=False)
    vigente = models.BooleanField(default=True)
    etapa_ensino_codigo = models.IntegerField(null=True, blank=True)
    tipo_escola_codigo = models.IntegerField(null=True, blank=True)
    elegivel_sondagem = models.BooleanField(default=False)
    atualizado_em = models.DateTimeField(null=True, blank=True)

    class Meta(ModeloBase.Meta):
        db_table = "usuario_abrangencia"
        verbose_name = "abrangência do usuário"
        verbose_name_plural = "abrangências do usuário"

    def __str__(self) -> str:
        return f"{self.login} - {self.perfil_guid} - {self.origem}"


class ArrayDeTexto(ArrayField):
    """Coluna `text[]`, com fallback para bancos sem tipo array nativo.

    Em SQLite a coluna vira `text` com serialização JSON; em qualquer
    caso o atributo entrega `list[str] | None`.
    """

    @staticmethod
    def _e_postgres(connection: BaseDatabaseWrapper | None) -> bool:
        """Informa se o backend tem tipo array nativo."""
        return getattr(connection, "vendor", "") == "postgresql"

    def db_type(self, connection: BaseDatabaseWrapper) -> str:
        """Escolhe o tipo da coluna conforme o backend."""
        if self._e_postgres(connection):
            return str(super().db_type(connection))
        return "text"

    def get_placeholder(
        self,
        value: Any,
        compiler: Any,
        connection: BaseDatabaseWrapper,
    ) -> str:
        """Remove o cast `::text[]`, que só o PostgreSQL entende."""
        if self._e_postgres(connection):
            return str(super().get_placeholder(value, compiler, connection))
        return "%s"

    def from_db_value(
        self,
        value: Any,
        _expression: Any = None,
        connection: BaseDatabaseWrapper | None = None,
    ) -> list[str] | None:
        """Reconstrói a lista a partir do texto lido fora do PostgreSQL."""
        if self._e_postgres(connection):
            return cast("list[str] | None", value)
        if value is None or isinstance(value, list):
            return cast("list[str] | None", value)
        return cast("list[str]", json.loads(value))

    def get_db_prep_value(
        self,
        value: Any,
        connection: BaseDatabaseWrapper,
        prepared: bool = False,
    ) -> Any:
        """Serializa a lista quando o backend não tem tipo array."""
        if self._e_postgres(connection):
            return super().get_db_prep_value(value, connection, prepared)
        if value is None or isinstance(value, str):
            return value
        return json.dumps(list(value))


def _array_de_texto() -> ArrayDeTexto:
    """Declara coluna `text[]` da MV, opcional como no destino."""
    return ArrayDeTexto(
        models.TextField(),
        null=True,
        blank=True,
    )


class AbrangenciaCompacta(ModeloBase):
    """Escopo agregado de `(login, perfil, ano letivo)`.

    Materialized view: para o ORM em leitura, MV e tabela são
    indistinguíveis.
    """

    # `login` sozinho não é único: o mesmo servidor aparece em vários
    # perfis e anos.
    pk = models.CompositePrimaryKey("login", "perfil_guid", "ano_letivo")
    login = models.TextField()
    perfil_guid = models.UUIDField()
    ano_letivo = models.IntegerField()
    grupo_codigo = models.IntegerField()
    tipo_abrangencia = models.IntegerField()
    eh_perfil_manual = models.BooleanField(default=False)

    id_dres = _array_de_texto()
    id_ues = _array_de_texto()
    id_turmas = _array_de_texto()
    id_ues_exercicio = _array_de_texto()
    id_turmas_poa = _array_de_texto()
    id_ues_alternativo = _array_de_texto()
    id_turmas_alternativo = _array_de_texto()
    id_ues_readaptado = _array_de_texto()
    id_ues_detalhaveis = _array_de_texto()

    class Meta(ModeloBase.Meta):
        db_table = "mv_abrangencia_compacta"
        verbose_name = "abrangência compacta"
        verbose_name_plural = "abrangências compactas"

    def __str__(self) -> str:
        return f"{self.login} - {self.perfil_guid} - {self.ano_letivo}"
