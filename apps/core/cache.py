"""Acesso compartilhado ao cache da aplicação."""

import logging
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from functools import lru_cache
from typing import cast

from django.conf import settings
from django.core.cache import caches
from django.core.cache.backends.base import BaseCache
from redis import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _obter_cliente_redis(url: str, timeout: float) -> Redis:
    """Cria um cliente Redis compartilhado com pool de conexões."""
    return Redis.from_url(
        url, socket_connect_timeout=timeout, socket_timeout=timeout
    )


def preservar_chave_cache(
    chave: str,
    prefixo: str,
    versao: int,
) -> str:
    """Mantém a chave lógica sem prefixo ou versão do backend Django."""
    del prefixo, versao
    return chave


class CacheRepository:
    """Lê e escreve valores no cache."""

    def __init__(
        self,
        cache: BaseCache | None = None,
        cliente_redis: Redis | None = None,
    ) -> None:
        """Inicializa o repositório.

        Args:
            cache: Backend opcional usado para facilitar testes isolados.
            cliente_redis: Cliente opcional responsável pelos locks.
        """
        self._cache = cache or caches["keydb"]
        self._cliente_redis = cliente_redis
        if self._cliente_redis is None and settings.KEYDB_ENABLED:
            self._cliente_redis = _obter_cliente_redis(
                settings.KEYDB_URL, settings.KEYDB_TIMEOUT
            )

    def obter(self, chave: str) -> object | None:
        """Busca um valor sem interromper o fluxo em falhas do cache."""
        try:
            return cast(object | None, self._cache.get(chave))
        except Exception:
            logger.exception("Falha ao consultar o cache compartilhado.")
            return None

    def obter_varios(self, chaves: list[str]) -> dict[str, object]:
        """Busca vários valores; chave ausente não aparece no retorno."""
        if not chaves:
            return {}
        try:
            return cast(dict[str, object], self._cache.get_many(chaves))
        except Exception:
            logger.exception("Falha ao consultar o cache compartilhado.")
            return {}

    def armazenar(
        self,
        chave: str,
        valor: object,
        ttl: int,
    ) -> None:
        """Armazena um valor pelo tempo informado em segundos."""
        try:
            self._cache.set(chave, valor, timeout=ttl)
        except Exception:
            logger.exception("Falha ao armazenar o cache compartilhado.")

    def armazenar_varios(
        self,
        valores: Mapping[str, object],
        ttl: int,
    ) -> None:
        """Armazena vários valores pelo mesmo tempo."""
        if not valores:
            return
        try:
            self._cache.set_many(dict(valores), timeout=ttl)
        except Exception:
            logger.exception("Falha ao armazenar o cache compartilhado.")

    @contextmanager
    def bloquear(
        self,
        chave: str,
        ttl: int,
        espera: float,
    ) -> Iterator[bool]:
        """Tenta manter um lock distribuído durante uma operação.

        Args:
            chave: Chave do recurso protegido, sem o prefixo de lock.
            ttl: Tempo máximo do lock em segundos.
            espera: Tempo máximo de espera pela aquisição em segundos.

        Yields:
            `True` quando o lock foi adquirido; caso contrário, `False`.
        """
        if self._cliente_redis is None:
            yield False
            return

        lock = self._cliente_redis.lock(
            f"lock:{chave}",
            timeout=ttl,
            blocking_timeout=espera,
        )
        try:
            adquirido = bool(lock.acquire(blocking=True))
        except RedisError:
            logger.exception("Falha ao operar o lock do cache compartilhado.")
            yield False
            return

        try:
            yield adquirido
        finally:
            if adquirido:
                try:
                    lock.release()
                except RedisError:
                    logger.exception(
                        "Falha ao liberar o lock do cache compartilhado."
                    )
