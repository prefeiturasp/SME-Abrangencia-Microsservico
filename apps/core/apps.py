"""Configuração da app core."""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Configura o app core."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "core"
