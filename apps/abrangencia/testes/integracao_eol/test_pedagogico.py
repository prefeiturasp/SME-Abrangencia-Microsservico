"""Testes das chamadas ao SME-IntegracaoEOL-Pedagogico-Microsservico."""

from unittest.mock import MagicMock

from apps.abrangencia.integracao_eol import PedagogicoAPI


class TestPedagogicoAPI:
    """Trava método e path de cada chamada."""

    def test_ciclos_ensino_chama_o_catalogo(self) -> None:
        """Garante o GET no catálogo, com a resposta devolvida como veio."""
        cliente = MagicMock()

        resposta = PedagogicoAPI(cliente).ciclos_ensino()

        cliente.get.assert_called_once_with("/abrangencia/ciclo-ensino/")
        assert resposta is cliente.get.return_value

    def test_sem_cliente_usa_o_configurado_em_apis_externas(self) -> None:
        """Garante que o nome da classe existe em `APIS_EXTERNAS`.

        O mesmo nome identifica o breaker e o `upstream` nos logs.
        """
        cliente = PedagogicoAPI()._cliente

        assert cliente.dominio == "pedagogico"
