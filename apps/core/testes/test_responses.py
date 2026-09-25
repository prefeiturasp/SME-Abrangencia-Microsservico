"""Testes das fábricas de respostas HTTP."""

import httpx
import pytest
from rest_framework import status

from apps.core.api.responses import (
    resposta_detalhe,
    resposta_erro_status_livre,
    resposta_externa,
    resposta_indisponivel,
    sem_conteudo,
)


def _erro_http(
    status_code: int, conteudo: bytes | None = None, **kwargs: object
) -> httpx.HTTPStatusError:
    requisicao = httpx.Request("GET", "https://api-externa.teste/recurso/")
    resposta = httpx.Response(
        status_code, content=conteudo, request=requisicao, **kwargs
    )
    return httpx.HTTPStatusError("erro", request=requisicao, response=resposta)


class TestRespostaDetalhe:
    """Testes de `resposta_detalhe`."""

    def test_responde_400_com_detail_por_padrao(self) -> None:
        """Garante o corpo `{"detail": ...}` e o 400 como default."""
        resposta = resposta_detalhe("O perfil é obrigatório.")

        assert resposta.status_code == status.HTTP_400_BAD_REQUEST
        assert resposta.data == {"detail": "O perfil é obrigatório."}

    def test_aceita_outro_status(self) -> None:
        """Garante o status informado no lugar do default."""
        resposta = resposta_detalhe("Não encontrado.", 404)

        assert resposta.status_code == status.HTTP_404_NOT_FOUND


def test_indisponivel_responde_503_com_o_nome_da_api() -> None:
    """Garante 503 com o nome lógico da API no `detail`."""
    resposta = resposta_indisponivel("externa")

    assert resposta.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert resposta.data == {"detail": "Serviço de externa indisponível."}


class TestRespostaErroStatusLivre:
    """Testes de `resposta_erro_status_livre`."""

    def test_repete_status_e_corpo_json(self) -> None:
        """Garante que a mensagem de erro da API externa chega intacta."""
        resposta = resposta_erro_status_livre(
            _erro_http(400, json={"detail": "mensagem da API externa"})
        )

        assert resposta.status_code == status.HTTP_400_BAD_REQUEST
        assert resposta.data == {"detail": "mensagem da API externa"}

    def test_preserva_status_fora_do_intervalo_http(self) -> None:
        """Garante que um código como 601 chega sem virar erro interno."""
        resposta = resposta_erro_status_livre(
            _erro_http(601, json={"detail": "erro de negocio"})
        )

        assert resposta.status_code == 601
        assert resposta.data == {"detail": "erro de negocio"}

    def test_corpo_texto_vira_detail(self) -> None:
        """Garante `detail` com o texto quando o corpo não é JSON."""
        resposta = resposta_erro_status_livre(
            _erro_http(404, b"  nao encontrado  ")
        )

        assert resposta.status_code == status.HTTP_404_NOT_FOUND
        assert resposta.data == {"detail": "nao encontrado"}

    def test_sem_corpo_usa_a_frase_do_status(self) -> None:
        """Garante um `detail` mesmo sem corpo na resposta de erro."""
        resposta = resposta_erro_status_livre(_erro_http(500))

        assert resposta.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert resposta.data == {"detail": "Internal Server Error"}


def test_resposta_externa_devolve_os_mesmos_bytes_e_status() -> None:
    """Garante o corpo da API externa sem transformação, como JSON."""
    corpo = (
        b'[{"codigo": "000100", "dtAtualizacao": "2011-01-21T19:10:37.937"}]'
    )

    resposta = resposta_externa(httpx.Response(200, content=corpo))

    assert resposta.status_code == status.HTTP_200_OK
    assert resposta.content == corpo
    assert resposta["Content-Type"] == "application/json"


@pytest.mark.parametrize(
    ("status_code", "conteudo"),
    [(204, b""), (200, b""), (200, b"[]"), (200, b"{}")],
)
def test_sem_conteudo_para_204_corpo_vazio_ou_json_vazio(
    status_code: int, conteudo: bytes
) -> None:
    """Garante que resposta vazia é reconhecida em todas as formas."""
    assert sem_conteudo(httpx.Response(status_code, content=conteudo))


@pytest.mark.parametrize("conteudo", [b'["000100"]', b"texto qualquer"])
def test_com_conteudo_para_json_preenchido_ou_texto(conteudo: bytes) -> None:
    """Garante que lista preenchida ou corpo não JSON contam como conteúdo."""
    assert not sem_conteudo(httpx.Response(200, content=conteudo))
