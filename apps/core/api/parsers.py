"""Parsers de JSON para os content-types aceitos pela API legada."""

from rest_framework.parsers import JSONParser


class ParserTextJson(JSONParser):
    """Aceita corpo JSON enviado como `text/json`."""

    media_type = "text/json"


class ParserJsonPatch(JSONParser):
    """Aceita `application/json-patch+json` como JSON comum."""

    media_type = "application/json-patch+json"
