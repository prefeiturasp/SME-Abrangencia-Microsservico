"""Testes do acesso compartilhado ao cache."""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings
from redis.exceptions import RedisError

from apps.core.cache import (
    CacheRepository,
    _obter_cliente_redis,
    preservar_chave_cache,
)


class TestCacheRepository(SimpleTestCase):
    """Valida o acesso genérico e tolerante a falhas ao cache."""

    def test_preserva_chave_sem_versao_do_backend(self) -> None:
        """Evita que o Django acrescente versão ou prefixo à chave."""
        resultado = preservar_chave_cache("dominio:recurso:abc", "sme", 1)

        self.assertEqual(resultado, "dominio:recurso:abc")

    def test_armazena_valor_com_ttl_informado(self) -> None:
        """Permite que cada caso de uso defina seu tempo de vida."""
        cache = MagicMock()

        CacheRepository(cache).armazenar("chave", {"valor": 1}, ttl=300)

        cache.set.assert_called_once_with("chave", {"valor": 1}, timeout=300)

    def test_armazena_varios_com_ttl_informado(self) -> None:
        """Grava vários valores numa chamada só."""
        cache = MagicMock()

        CacheRepository(cache).armazenar_varios({"a": 1, "b": 2}, ttl=60)

        cache.set_many.assert_called_once_with({"a": 1, "b": 2}, timeout=60)

    def test_lista_vazia_nao_chama_o_cache(self) -> None:
        """Evita ida ao cache sem chave nenhuma."""
        cache = MagicMock()
        repositorio = CacheRepository(cache)

        self.assertEqual(repositorio.obter_varios([]), {})
        repositorio.armazenar_varios({}, ttl=60)

        cache.get_many.assert_not_called()
        cache.set_many.assert_not_called()

    def test_obter_varios_devolve_so_as_chaves_achadas(self) -> None:
        """Repassa o retorno do `get_many` do backend."""
        cache = MagicMock()
        cache.get_many.return_value = {"a": 1}

        resultado = CacheRepository(cache).obter_varios(["a", "b"])

        self.assertEqual(resultado, {"a": 1})

    def test_falha_de_leitura_retorna_cache_vazio(self) -> None:
        """Permite continuar o caso de uso quando o cache falha."""
        cache = MagicMock()
        cache.get.side_effect = ConnectionError("KeyDB indisponível")
        cache.get_many.side_effect = ConnectionError("KeyDB indisponível")
        repositorio = CacheRepository(cache)

        with self.assertLogs("apps.core.cache", level="ERROR"):
            self.assertIsNone(repositorio.obter("chave"))
            self.assertEqual(repositorio.obter_varios(["chave"]), {})

    def test_falha_de_escrita_nao_interrompe_fluxo(self) -> None:
        """Ignora a indisponibilidade durante a escrita no cache."""
        cache = MagicMock()
        cache.set.side_effect = ConnectionError("KeyDB indisponível")
        cache.set_many.side_effect = ConnectionError("KeyDB indisponível")
        repositorio = CacheRepository(cache)

        with self.assertLogs("apps.core.cache", level="ERROR"):
            repositorio.armazenar("chave", "valor", ttl=300)
            repositorio.armazenar_varios({"chave": "valor"}, ttl=300)

    def test_lock_adquirido_e_liberado(self) -> None:
        """Mantém o lock apenas durante o bloco protegido."""
        cliente_redis = MagicMock()
        lock = cliente_redis.lock.return_value
        lock.acquire.return_value = True
        repositorio = CacheRepository(MagicMock(), cliente_redis)

        with repositorio.bloquear("recurso:1", ttl=30, espera=2) as adquirido:
            self.assertTrue(adquirido)
            lock.release.assert_not_called()

        cliente_redis.lock.assert_called_once_with(
            "lock:recurso:1", timeout=30, blocking_timeout=2
        )
        lock.acquire.assert_called_once_with(blocking=True)
        lock.release.assert_called_once_with()

    def test_lock_ocupado_nao_e_liberado(self) -> None:
        """Não libera um lock pertencente a outro processamento."""
        cliente_redis = MagicMock()
        lock = cliente_redis.lock.return_value
        lock.acquire.return_value = False
        repositorio = CacheRepository(MagicMock(), cliente_redis)

        with repositorio.bloquear("recurso:1", ttl=30, espera=2) as adquirido:
            self.assertFalse(adquirido)

        lock.release.assert_not_called()

    def test_sem_keydb_nao_ha_lock(self) -> None:
        """Sem cliente Redis, o bloco roda sem lock."""
        repositorio = CacheRepository(MagicMock())

        with repositorio.bloquear("recurso:1", ttl=30, espera=2) as adquirido:
            self.assertFalse(adquirido)

    def test_falha_do_lock_nao_interrompe_fluxo(self) -> None:
        """Erro do KeyDB ao adquirir ou liberar o lock só é registrado."""
        cliente_redis = MagicMock()
        lock = cliente_redis.lock.return_value
        lock.acquire.side_effect = RedisError("indisponível")
        repositorio = CacheRepository(MagicMock(), cliente_redis)

        with (
            self.assertLogs("apps.core.cache", level="ERROR"),
            repositorio.bloquear("recurso:1", ttl=30, espera=2) as adquirido,
        ):
            self.assertFalse(adquirido)

        lock.acquire.side_effect = None
        lock.acquire.return_value = True
        lock.release.side_effect = RedisError("indisponível")
        with (
            self.assertLogs("apps.core.cache", level="ERROR"),
            repositorio.bloquear("recurso:1", ttl=30, espera=2) as ok,
        ):
            self.assertTrue(ok)


class TestTimeoutDoKeydb(SimpleTestCase):
    """Garante que KeyDB inalcancavel nao prende o request."""

    def setUp(self) -> None:
        """Limpa o cliente compartilhado entre os testes."""
        _obter_cliente_redis.cache_clear()
        self.addCleanup(_obter_cliente_redis.cache_clear)

    @override_settings(
        KEYDB_ENABLED=True, KEYDB_URL="redis://keydb.teste:6379/0"
    )
    def test_cliente_do_lock_tem_timeout(self) -> None:
        """Garante timeout ao conectar e em cada comando do lock.

        Sem ele, uma queda de rede que nao recusa a conexao prendeu uma
        chamada por mais de uma hora, esperando o KeyDB responder.
        """
        with (
            override_settings(KEYDB_TIMEOUT=2.0),
            patch("apps.core.cache.Redis.from_url") as criar,
        ):
            CacheRepository(MagicMock())

        criar.assert_called_once_with(
            "redis://keydb.teste:6379/0",
            socket_connect_timeout=2.0,
            socket_timeout=2.0,
        )
