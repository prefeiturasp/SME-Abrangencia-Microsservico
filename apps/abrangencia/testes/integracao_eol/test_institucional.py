"""Testes das chamadas ao SME-IntegracaoEOL-Institucional-Microsservico."""

from unittest.mock import MagicMock

from django.test import SimpleTestCase

from apps.abrangencia.integracao_eol import InstitucionalAPI


class TestInstitucionalAPI(SimpleTestCase):
    """Trava método e path de cada chamada."""

    def test_codigos_dres(self) -> None:
        """Garante o GET na lista de códigos de DRE."""
        cliente = MagicMock()

        resposta = InstitucionalAPI(cliente).codigos_dres()

        cliente.get.assert_called_once_with("/abrangencia/codigos-dres/")
        self.assertIs(resposta, cliente.get.return_value)

    def test_dres_nome_abreviacao(self) -> None:
        """Garante o GET na lista de DREs com nome e abreviação."""
        cliente = MagicMock()

        resposta = InstitucionalAPI(cliente).dres_nome_abreviacao()

        cliente.get.assert_called_once_with(
            "/abrangencia/nome-abreviacao-dres/"
        )
        self.assertIs(resposta, cliente.get.return_value)

    def test_sem_cliente_usa_o_configurado_em_apis_externas(self) -> None:
        """Garante que o nome da classe existe em `APIS_EXTERNAS`.

        O mesmo nome identifica o breaker e o `upstream` nos logs.
        """
        cliente = InstitucionalAPI()._cliente

        self.assertEqual(cliente.dominio, "institucional")
