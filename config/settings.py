"""Configuração Django do SME-Abrangencia-Microsservico."""

import os
import sys
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "dev-inseguro-apenas-desenvolvimento",
)
API_KEY = os.getenv("API_KEY", "dev-key-default")
API_KEY_HEADER = os.getenv("API_KEY_HEADER", "X-API-Key")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [
    host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",")
]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "apps.core.apps.CoreConfig",
    "apps.autenticacao",
    "apps.abrangencia",
]

MIDDLEWARE = [
    "sme_sidecar_sdk.integrations.django.ObservabilityMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

_DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
_POOL_OPTIONS: dict[str, Any] = {
    "POOL_SIZE": _DB_POOL_SIZE,
    "MAX_OVERFLOW": 0,
    "POOL_TIMEOUT": 30,
    "POOL_RECYCLE": 1800,
    "PRE_PING": True,
}


def _url_para_bd(url: str | None) -> dict[str, Any]:
    """Converta a URL do banco de Abrangência em configuração Django.

    Args:
        url: URL PostgreSQL, no formato de
            ``AIRFLOW_CONN_ABRANGENCIA_POSTGRES``.

    Returns:
        Dicionário de configuração do Django, com pool de conexões via
        ``dj_db_conn_pool``. Sem URL, cai em SQLite em memória usado
        pela suíte de testes, que nunca toca o banco real.
    """
    if not url:
        return {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}

    parsed = urllib.parse.urlparse(url)

    return {
        "ENGINE": "dj_db_conn_pool.backends.postgresql",
        "NAME": parsed.path.lstrip("/"),
        "USER": parsed.username or "postgres",
        "PASSWORD": parsed.password or "postgres",
        "HOST": parsed.hostname or "localhost",
        "PORT": parsed.port or 5432,
        "POOL_OPTIONS": _POOL_OPTIONS,
    }


DATABASES = {
    "default": _url_para_bd(os.getenv("AIRFLOW_CONN_ABRANGENCIA_POSTGRES")),
}

_RODANDO_TESTES = (
    "test" in sys.argv
    or "pytest" in sys.argv[0]
    or "PYTEST_CURRENT_TEST" in os.environ
    or os.getenv("USE_SQLITE_TEST", "0") == "1"
)
if _RODANDO_TESTES:
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    },
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

ABRANGENCIA_ANO_LETIVO = int(
    os.getenv("ABRANGENCIA_ANO_LETIVO") or datetime.now().year
)

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.autenticacao.api_key.AutenticacaoApiKey",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "apps.core.api.parsers.ParserTextJson",
        "apps.core.api.parsers.ParserJsonPatch",
    ],
}

SPECTACULAR_SETTINGS = {
    "TITLE": "SME-Abrangencia-Microsservico API",
    "DESCRIPTION": (
        "Microsserviço de abrangência dos perfis em DREs, UEs e turmas."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "APPEND_COMPONENTS": {
        "securitySchemes": {
            "ApiKey": {
                "type": "apiKey",
                "in": "header",
                "name": API_KEY_HEADER,
            }
        }
    },
    "SECURITY": [{"ApiKey": []}],
}

TEST_RUNNER = "config.test_runner.AbrangenciaTestRunner"
