"""Contratos da integração Django com o SME Sidecar SDK."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

_ROTEIRO = """
import json
from unittest.mock import patch
import django

django.setup()

from django.apps import apps
from django.conf import settings
from django.test import Client
from django.urls import reverse
from sme_sidecar_sdk import runtime
from sme_sidecar_sdk.config import Settings

client = Client()
respostas = []
for rota in (reverse('health-check'),
             reverse('perfil', kwargs={'id_perfil': 'perfil-ficticio'}),
             '/rota-inexistente/'):
    for headers in ({'HTTP_X_REQUEST_ID': 'request-abrangencia-123'}, {}):
        resposta = client.get(rota, **headers)
        respostas.append({'status': resposta.status_code,
                          'request_id': resposta.headers.get('X-Request-ID'),
                          'path': rota})

with patch('sme_sidecar_sdk.runtime.configure') as configurar:
    apps.get_app_config('core').ready()
    configurar.assert_called_once_with()

with patch.dict('os.environ', {
    'SME_BROKER_URL': 'amqp://broker-ficticio:5672/%2F',
    'SME_LOG_QUEUE': 'fila-ficticia',
}):
    transporte = Settings(_env_file=None)

estado = runtime.state()
print('RESULTADO=' + json.dumps({
    'apps': settings.INSTALLED_APPS, 'middleware': settings.MIDDLEWARE,
    'respostas': respostas, 'logging': estado.logging_enabled,
    'tracing': estado.tracing_enabled, 'fila': estado.settings.log_queue,
    'broker_configurado': transporte.broker_url,
    'fila_configurada': transporte.log_queue,
}))
"""


@pytest.fixture(scope="module")
def execucao_sdk() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Isola o boot e o cache de configuração do SDK em outro processo."""
    ambiente = {
        **{
            chave: os.environ[chave]
            for chave in ("PATH", "SYSTEMROOT", "TEMP", "TMP", "HOME")
            if chave in os.environ
        },
        "DJANGO_SETTINGS_MODULE": "config.settings",
        "DJANGO_ALLOWED_HOSTS": "testserver",
        "DJANGO_DEBUG": "0",
        "USE_SQLITE_TEST": "1",
        "SME_SDK_ENABLED": "true",
        "SME_SERVICE_NAME": "abrangencia-ms",
        "SME_SERVICE_VERSION": "0.0.1",
        "SME_ENVIRONMENT": "test",
        "SME_LOGGING_ENABLED": "true",
        "SME_LOG_LEVEL": "INFO",
        "SME_LOG_FORMAT": "json",
        "SME_CORRELATION_ID_HEADER": "X-Request-ID",
        "SME_OBSERVABILITY_BACKEND": "elastic",
        "SME_OTEL_ENABLED": "false",
        "SME_LOG_QUEUE": "",
    }
    processo = subprocess.run(
        [sys.executable, "-c", _ROTEIRO],
        cwd=Path(__file__).resolve().parents[3],
        env=ambiente,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert processo.returncode == 0, processo.stderr
    resultado = None
    eventos = []
    for linha in processo.stdout.splitlines():
        if linha.startswith("RESULTADO="):
            resultado = json.loads(linha.removeprefix("RESULTADO="))
        elif linha.startswith("{"):
            eventos.append(json.loads(linha))
    assert resultado is not None
    return resultado, eventos


def test_inicializa_runtime_sem_destinos_externos(
    execucao_sdk: tuple[dict[str, Any], list[dict[str, Any]]],
) -> None:
    """Configura o SDK e correlação sem tracing ou conexão com broker."""
    resultado, _ = execucao_sdk
    assert "apps.core.apps.CoreConfig" in resultado["apps"]
    assert resultado["middleware"][0] == (
        "sme_sidecar_sdk.integrations.django.ObservabilityMiddleware"
    )
    assert resultado["logging"] is True
    assert resultado["tracing"] is False
    assert resultado["fila"] == ""


@pytest.mark.parametrize("indice,status", [(0, 200), (2, 401), (4, 404)])
def test_correlaciona_respostas_sem_vazar_contexto(
    execucao_sdk: tuple[dict[str, Any], list[dict[str, Any]]],
    indice: int,
    status: int,
) -> None:
    """Reutiliza o header e gera UUID independente no request seguinte."""
    resultado, _ = execucao_sdk
    recebida, gerada = resultado["respostas"][indice : indice + 2]
    assert recebida["status"] == gerada["status"] == status
    assert recebida["request_id"] == "request-abrangencia-123"
    assert str(UUID(gerada["request_id"])) == gerada["request_id"]
    identificadores = [
        resposta["request_id"] for resposta in resultado["respostas"][1::2]
    ]
    assert len(set(identificadores)) == 3


def test_emite_um_evento_json_por_requisicao(
    execucao_sdk: tuple[dict[str, Any], list[dict[str, Any]]],
) -> None:
    """Emite campos HTTP, identidade e correlação sem duplicar eventos."""
    resultado, eventos = execucao_sdk
    requests = [
        evento
        for evento in eventos
        if evento.get("event") == "http_request_completed"
    ]
    assert len(requests) == len(resultado["respostas"]) == 6
    for evento, resposta in zip(requests, resultado["respostas"], strict=True):
        assert evento["service"] == "abrangencia-ms"
        assert evento["environment"] == "test"
        assert evento["level"] == "info"
        assert evento["request_id"] == resposta["request_id"]
        assert evento["http_method"] == "GET"
        assert evento["http_path"] == resposta["path"]
        assert evento["http_status_code"] == resposta["status"]
        assert evento["http_duration_ms"] >= 0
        assert evento["timestamp"]


def test_le_variaveis_de_transporte_pelos_nomes_do_sdk(
    execucao_sdk: tuple[dict[str, Any], list[dict[str, Any]]],
) -> None:
    """Lê SME_BROKER_URL e SME_LOG_QUEUE sem abrir conexão externa."""
    resultado, _ = execucao_sdk
    assert resultado["broker_configurado"] == (
        "amqp://broker-ficticio:5672/%2F"
    )
    assert resultado["fila_configurada"] == "fila-ficticia"
