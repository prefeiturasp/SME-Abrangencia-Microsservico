"""Testes das chamadas ao SME-IntegracaoEOL-Pedagogico-Microsservico."""

import json
from typing import Any
from unittest.mock import MagicMock

import httpx
from django.test import SimpleTestCase

from apps.abrangencia.integracao_eol import PedagogicoAPI


def _resposta(corpo: Any = None, status_code: int = 200) -> httpx.Response:
    conteudo = b"" if corpo is None else json.dumps(corpo).encode()
    return httpx.Response(status_code, content=conteudo)


def _turma(**campos: Any) -> dict[str, Any]:
    return {
        "ano": "1",
        "anoLetivo": 2026,
        "codigo": 9000001,
        "dataFim": None,
        "dataInicioTurma": "2026-02-01T00:00:00.000Z",
        "extinta": False,
        "ueCodigo": "000191",
        **campos,
    }


def _estrutura(*turmas: dict[str, Any]) -> dict[str, Any]:
    return {
        "abrangencia": None,
        "dres": [
            {
                "abreviacao": "DRE - TT",
                "codigo": "000100",
                "nome": "DIRETORIA TESTE",
                "ues": [
                    {
                        "codigo": "000191",
                        "nome": "EMEF TESTE",
                        "codTipoEscola": 1,
                        "turmas": list(turmas),
                    }
                ],
            }
        ],
    }


def _turmas(dados: dict[str, Any]) -> Any:
    return dados["dres"][0]["ues"][0]["turmas"]


class TestPedagogicoAPI(SimpleTestCase):
    """Trava método e path de cada chamada."""

    def test_ciclos_ensino_chama_o_catalogo(self) -> None:
        """Garante o GET no catálogo, com a resposta devolvida como veio."""
        cliente = MagicMock()

        resposta = PedagogicoAPI(cliente).ciclos_ensino()

        cliente.get.assert_called_once_with("/abrangencia/ciclo-ensino/")
        self.assertIs(resposta, cliente.get.return_value)

    def test_estrutura_por_dre_envia_o_codigo_em_query(self) -> None:
        """Garante o GET em `todas/` com `codigo_dre` na query."""
        cliente = MagicMock()
        cliente.get.return_value = _resposta(_estrutura(_turma()))

        PedagogicoAPI(cliente).estrutura_vigente_por_dre("000100")

        cliente.get.assert_called_once_with(
            "/turmas/turmas-atribuidas-dre-ue/todas/",
            params={"codigo_dre": "000100"},
        )

    def test_estrutura_por_turmas_envia_os_codigos_no_corpo(self) -> None:
        """Garante o POST em `por-turmas/` com `list[int]`."""
        cliente = MagicMock()
        cliente.post.return_value = _resposta(_estrutura(_turma()))

        PedagogicoAPI(cliente).estrutura_vigente_por_turmas([9000001, 2])

        cliente.post.assert_called_once_with(
            "/turmas/turmas-atribuidas-dre-ue/por-turmas/",
            payload=[9000001, 2],
        )

    def test_sem_conteudo_vira_lista_de_dres_vazia(self) -> None:
        """Garante `{"dres": []}` quando não retorna DRE."""
        casos = {
            "204": _resposta(status_code=204),
            "corpo vazio": _resposta(),
            "sem dres": _resposta({"abrangencia": None}),
            "dres nulo": _resposta({"dres": None}),
            "dres vazio": _resposta({"dres": []}),
        }

        for caso, resposta in casos.items():
            with self.subTest(caso=caso):
                cliente = MagicMock()
                cliente.get.return_value = resposta

                dados = PedagogicoAPI(cliente).estrutura_vigente_por_dre("1")

                self.assertEqual(dados, {"dres": []})

    def test_descarta_a_chave_abrangencia_da_raiz(self) -> None:
        """Garante a raiz do `EstruturaInstitucionalDTO`, só com `dres`."""
        cliente = MagicMock()
        cliente.get.return_value = _resposta(_estrutura(_turma()))

        dados = PedagogicoAPI(cliente).estrutura_vigente_por_dre("000100")

        self.assertEqual(list(dados), ["dres"])

    def test_datas_utc_saem_no_horario_de_sao_paulo(self) -> None:
        """Garante a data do legado: horário local, sem fuso e sem zeros."""
        casos = {
            "2025-09-12T18:53:35.473Z": "2025-09-12T15:53:35.473",
            "2025-09-12T18:53:35.470Z": "2025-09-12T15:53:35.47",
            "2026-02-01T03:00:00.000Z": "2026-02-01T00:00:00",
            "2026-02-01T03:00:00Z": "2026-02-01T00:00:00",
            "2025-09-12T15:53:35.473": "2025-09-12T15:53:35.473",
            "data invalidaZ": "data invalidaZ",
            None: None,
        }

        for entrada, esperado in casos.items():
            with self.subTest(entrada=entrada):
                cliente = MagicMock()
                turma = _turma(dataFim=entrada, dataInicioTurma=entrada)
                cliente.post.return_value = _resposta(_estrutura(turma))

                dados = PedagogicoAPI(cliente).estrutura_vigente_por_turmas(
                    [1]
                )

                turma = _turmas(dados)[0]
                self.assertEqual(turma["dataFim"], esperado)
                self.assertEqual(turma["dataInicioTurma"], esperado)

    def test_demais_chaves_passam_iguais_e_na_mesma_ordem(self) -> None:
        """Garante DRE, UE e turma com as chaves e valores."""
        turma = _turma(dataInicioTurma=None, chaveNova="x")
        estrutura = _estrutura(turma)
        cliente = MagicMock()
        cliente.get.return_value = _resposta(estrutura)

        dados = PedagogicoAPI(cliente).estrutura_vigente_por_dre("000100")

        self.assertEqual(dados["dres"], estrutura["dres"])
        self.assertEqual(list(_turmas(dados)[0]), list(turma))
        self.assertEqual(
            list(dados["dres"][0]), list(estrutura["dres"][0])
        )

    def test_ues_e_turmas_que_nao_sao_lista_passam_como_vieram(self) -> None:
        """Garante que a adaptação não retorna lista onde veio `null`."""
        estrutura = {
            "dres": [
                {"codigo": "000100", "ues": None},
                {"codigo": "000200", "ues": [{"codigo": "1", "turmas": None}]},
            ]
        }
        cliente = MagicMock()
        cliente.get.return_value = _resposta(estrutura)

        dados = PedagogicoAPI(cliente).estrutura_vigente_por_dre("000100")

        self.assertEqual(dados, estrutura)

    def test_sem_cliente_usa_o_configurado_em_apis_externas(self) -> None:
        """Garante que o nome da classe existe em `APIS_EXTERNAS`."""
        cliente = PedagogicoAPI()._cliente

        self.assertEqual(cliente.dominio, "pedagogico")
