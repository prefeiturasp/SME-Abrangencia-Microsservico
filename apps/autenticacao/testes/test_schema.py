"""Testes da integração da autenticação com o schema OpenAPI."""

from django.test import TestCase, override_settings

from apps.autenticacao.api_key import AutenticacaoApiKey
from apps.autenticacao.schema import AutenticacaoApiKeyScheme


class TestAutenticacaoApiKeyScheme(TestCase):
    """Testes de `AutenticacaoApiKeyScheme.get_security_definition`."""

    @override_settings(API_KEY_HEADER="X-Chave-Customizada")
    def test_get_security_definition_usa_header_configurado(self) -> None:
        """A definição de segurança reflete o header configurado."""
        extensao = AutenticacaoApiKeyScheme(AutenticacaoApiKey)

        definicao = extensao.get_security_definition(auto_schema=None)

        self.assertEqual(
            definicao,
            {
                "type": "apiKey",
                "in": "header",
                "name": "X-Chave-Customizada",
            },
        )
