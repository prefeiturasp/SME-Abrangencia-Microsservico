"""Serializers base para todos os apps do core."""

from rest_framework import serializers


class HealthStatusSerializer(serializers.Serializer):
    """Contrato do health check.

    `degraded`/`unhealthy` estão no contrato para o dia em que o endpoint
    passar a checar dependências reais (banco, por exemplo); hoje a view
    só emite `healthy`.
    """

    status = serializers.ChoiceField(
        choices=["healthy", "degraded", "unhealthy"],
        help_text="Estado geral do servico.",
    )
