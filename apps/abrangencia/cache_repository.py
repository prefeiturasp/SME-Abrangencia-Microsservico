"""Cache compartilhado da rede."""

from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from typing import Any

from django.conf import settings
from django.utils import timezone

from apps.core.cache import CacheRepository

TTL_LEGADO = 24 * 60 * 60
TTL_TURMA = 4 * 60 * 60

_TTL_POR_TIPO = {"dre": TTL_LEGADO, "ue": TTL_LEGADO, "turma": TTL_TURMA}


def agora() -> datetime:
    """Devolve o instante atual no fuso local."""
    return timezone.localtime()


class RedeSmeCacheRepository:
    """Guarda a rede vigente e os atributos por código."""

    def __init__(
        self,
        cache_repository: CacheRepository | None = None,
    ) -> None:
        """Inicializa o repositório com o cache compartilhado.

        Args:
            cache_repository: Repositório genérico opcional para testes.
        """
        self._cache_repository = cache_repository or CacheRepository()

    CHAVE_REDE_SME = "abrangencia:rede-sme"

    @staticmethod
    def chave_codigo(tipo: str, codigo: str) -> str:
        """Gera a chave de um código, por tipo (dre, ue, turma)."""
        return f"abrangencia:{tipo}:{codigo}"

    def obter_rede_sme(self) -> object | None:
        """Busca a rede vigente."""
        return self._cache_repository.obter(self.CHAVE_REDE_SME)

    def armazenar_rede_sme(self, rede: object) -> None:
        """Armazena a rede até a virada do dia."""
        self._cache_repository.armazenar(
            self.CHAVE_REDE_SME, rede, ttl=_ate_meia_noite()
        )

    def obter_codigos(
        self, tipo: str, codigos: Iterable[str]
    ) -> dict[str, dict[str, Any]]:
        """Busca os atributos já guardados; código ausente não aparece."""
        chaves = {self.chave_codigo(tipo, c): c for c in codigos}
        return {
            chaves[chave]: valor
            for chave, valor in self._cache_repository.obter_varios(
                list(chaves)
            ).items()
            if isinstance(valor, dict)
        }

    def armazenar_codigos(
        self, tipo: str, valores: Mapping[str, dict[str, Any]]
    ) -> None:
        """Armazena os atributos por código."""
        self._cache_repository.armazenar_varios(
            {
                self.chave_codigo(tipo, codigo): valor
                for codigo, valor in valores.items()
            },
            ttl=_TTL_POR_TIPO[tipo],
        )

    @contextmanager
    def bloquear_rede_sme(self) -> Iterator[bool]:
        """Protege a montagem da rede contra montagens simultâneas.

        Yields:
            `True` quando o lock foi adquirido; caso contrário, `False`.
        """
        with self._cache_repository.bloquear(
            self.CHAVE_REDE_SME,
            ttl=settings.CACHE_LOCK_TTL,
            espera=settings.CACHE_LOCK_WAIT_TIMEOUT,
        ) as adquirido:
            yield adquirido



class IntegracaoEolCacheRepository:
    """Guarda o retorno dos repasses de DREs e estrutura com o TTL."""

    CHAVE_NOME_ABREVIACAO_DRES = "abrangencia:nome-abreviacao-dres"

    def __init__(
        self,
        cache_repository: CacheRepository | None = None,
    ) -> None:
        """Inicializa o repositório com o cache compartilhado.

        Args:
            cache_repository: Repositório genérico opcional para testes.
        """
        self._cache_repository = cache_repository or CacheRepository()

    @staticmethod
    def chave_estrutura_vigente(codigo_dre: str) -> str:
        """Gera a chave da estrutura vigente de uma DRE."""
        return f"abrangencia:estrutura-vigente:{codigo_dre}"

    def obter_lista(self, chave: str) -> list[Any] | None:
        """Busca a lista JSON."""
        lista = self._cache_repository.obter(chave)
        return lista if isinstance(lista, list) else None

    def armazenar_lista(self, chave: str, lista: list[Any]) -> None:
        """Armazena a lista JSON."""
        self._cache_repository.armazenar(chave, lista, ttl=TTL_LEGADO)

    def obter_estrutura_vigente(self, codigo_dre: str) -> dict | None:
        """Busca a estrutura vigente, ja adaptada, de uma DRE."""
        estrutura = self._cache_repository.obter(
            self.chave_estrutura_vigente(codigo_dre)
        )
        return estrutura if isinstance(estrutura, dict) else None

    def armazenar_estrutura_vigente(
        self, codigo_dre: str, estrutura: dict
    ) -> None:
        """Armazena a estrutura vigente de uma DRE."""
        self._cache_repository.armazenar(
            self.chave_estrutura_vigente(codigo_dre),
            estrutura,
            ttl=TTL_LEGADO,
        )


class PerfilCacheRepository:
    """Guarda o retorno de por perfil, com o TTL do legado."""

    def __init__(
        self,
        cache_repository: CacheRepository | None = None,
    ) -> None:
        """Inicializa o repositório com o cache compartilhado.

        Args:
            cache_repository: Repositório genérico opcional para testes.
        """
        self._cache_repository = cache_repository or CacheRepository()

    @staticmethod
    def chave_perfil(perfil_guid: str) -> str:
        """Gera a chave de um perfil, com o GUID."""
        return f"abrangencia:perfil:{perfil_guid.lower()}"

    def obter_perfil(self, perfil_guid: str) -> dict | None:
        """Busca o payload de um perfil."""
        perfil = self._cache_repository.obter(self.chave_perfil(perfil_guid))
        return perfil if isinstance(perfil, dict) else None

    def armazenar_perfil(self, perfil_guid: str, perfil: dict) -> None:
        """Armazena o payload de um perfil."""
        self._cache_repository.armazenar(
            self.chave_perfil(perfil_guid), perfil, ttl=TTL_LEGADO
        )


def _ate_meia_noite() -> int:
    """Segundos até a virada do dia no fuso local."""
    instante = agora()
    amanha: date = instante.date() + timedelta(days=1)
    virada = datetime.combine(amanha, time.min, tzinfo=instante.tzinfo)
    return max(1, int((virada - instante).total_seconds()))
