"""Testes das chamadas ao SME-IntegracaoEOL-Institucional-Microsservico."""

import json
from typing import Any
from unittest.mock import MagicMock

import httpx
from django.test import SimpleTestCase

from apps.abrangencia.integracao_eol import InstitucionalAPI


def _resposta(corpo: Any = None, status_code: int = 200) -> httpx.Response:
    conteudo = b"" if corpo is None else json.dumps(corpo).encode()
    return httpx.Response(status_code, content=conteudo)


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

    def test_dres_envia_os_codigos_no_corpo(self) -> None:
        """Garante o POST em `/dres/` com a lista de códigos."""
        cliente = MagicMock()
        dre = {"codigoDRE": "108100", "nomeDRE": "DRE", "siglaDRE": "D"}
        cliente.post.return_value = _resposta([dre])

        dres = InstitucionalAPI(cliente).dres(["108100"])

        cliente.post.assert_called_once_with("/dres/", payload=["108100"])
        self.assertEqual(dres, [dre])

    def test_escolas_envia_os_codigos_no_corpo(self) -> None:
        """Garante o POST em `/escolas/` com a lista de códigos."""
        cliente = MagicMock()
        cliente.post.return_value = _resposta([{"codigoEscola": "019331"}])

        escolas = InstitucionalAPI(cliente).escolas(["019331"])

        cliente.post.assert_called_once_with("/escolas/", payload=["019331"])
        self.assertEqual(escolas, [{"codigoEscola": "019331"}])

    def test_unidades_da_dre_leva_a_dre_no_path(self) -> None:
        """Garante o GET em `/dres/{dre}/unidades/`."""
        cliente = MagicMock()
        cliente.get.return_value = _resposta([{"codigoEol": "019331"}])

        unidades = InstitucionalAPI(cliente).unidades_da_dre("108100")

        cliente.get.assert_called_once_with("/dres/108100/unidades/")
        self.assertEqual(unidades, [{"codigoEol": "019331"}])

    def test_sem_conteudo_vira_lista_vazia(self) -> None:
        """Garante `[]` com 204 ou corpo vazio, que não são falha."""
        for resposta in (_resposta(status_code=204), _resposta()):
            with self.subTest(status=resposta.status_code):
                cliente = MagicMock()
                cliente.post.return_value = resposta

                self.assertEqual(InstitucionalAPI(cliente).dres(["1"]), [])

    def test_corpo_que_nao_e_lista_e_erro(self) -> None:
        """Garante erro, e não lista vazia, com corpo fora do contrato."""
        cliente = MagicMock()
        cliente.post.return_value = _resposta({"codigos": []})

        with self.assertRaises(httpx.DecodingError):
            InstitucionalAPI(cliente).escolas(["019331"])

    def test_sem_cliente_usa_o_configurado_em_apis_externas(self) -> None:
        """Garante que o nome da classe existe em `APIS_EXTERNAS`."""
        cliente = InstitucionalAPI()._cliente

        self.assertEqual(cliente.dominio, "institucional")
