"""Testes da autenticação por API Key."""

from django.test import RequestFactory, TestCase, override_settings
from rest_framework.exceptions import AuthenticationFailed

from apps.autenticacao.api_key import AutenticacaoApiKey


@override_settings(API_KEY="chave-valida", API_KEY_HEADER="X-API-Key")
class TestAutenticacaoApiKey(TestCase):
    """Testes de `AutenticacaoApiKey.authenticate`."""

    def setUp(self) -> None:
        """Prepara a fábrica de requisições e a instância autenticada."""
        self.factory = RequestFactory()
        self.auth = AutenticacaoApiKey()

    def test_sem_header_retorna_none(self) -> None:
        """Requisição sem o header de API Key não é autenticada."""
        request = self.factory.get("/qualquer/")

        self.assertIsNone(self.auth.authenticate(request))

    def test_header_com_chave_invalida_levanta_erro(self) -> None:
        """Chave diferente da configurada é rejeitada."""
        request = self.factory.get("/qualquer/", HTTP_X_API_KEY="chave-errada")

        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(request)

    def test_header_com_chave_valida_autentica(self) -> None:
        """Chave igual à configurada autentica a requisição."""
        request = self.factory.get("/qualquer/", HTTP_X_API_KEY="chave-valida")

        resultado = self.auth.authenticate(request)

        assert resultado is not None
        usuario, credencial = resultado
        self.assertTrue(usuario.is_authenticated)
        self.assertIsNone(credencial)

    def test_authenticate_header_retorna_nome_configurado(self) -> None:
        """O header exigido é o mesmo configurado em `API_KEY_HEADER`."""
        request = self.factory.get("/qualquer/")

        self.assertEqual(self.auth.authenticate_header(request), "X-API-Key")
