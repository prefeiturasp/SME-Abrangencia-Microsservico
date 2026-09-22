"""Configuração da app core."""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Configura o app core."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "core"

    def ready(self) -> None:
        """Inicializa a observabilidade compartilhada da aplicação."""
        from sme_sidecar_sdk import runtime

        runtime.configure()
