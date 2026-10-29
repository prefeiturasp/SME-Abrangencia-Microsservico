"""Testes do cache da rede."""

from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase

from apps.abrangencia.cache_repository import (
    TTL_LEGADO,
    IntegracaoEolCacheRepository,
    PerfilCacheRepository,
    RedeSmeCacheRepository,
)

_FUSO = ZoneInfo("America/Sao_Paulo")


class TestRedeCacheRepository(SimpleTestCase):
    """Valida chaves e validade do cache da rede."""

    def setUp(self) -> None:
        """Cria o repositorio sobre um cache falso."""
        self.agora = datetime(2026, 10, 21, 23, 0, tzinfo=_FUSO)
        relogio = patch(
            "apps.abrangencia.cache_repository.agora",
            side_effect=lambda: self.agora,
        )
        relogio.start()
        self.addCleanup(relogio.stop)
        self.cache = MagicMock()
        self.repositorio = RedeSmeCacheRepository(self.cache)

    def test_chaves_nao_levam_data(self) -> None:
        """Garante a chave sem data: a validade vem do TTL."""
        self.assertEqual(
            RedeSmeCacheRepository.CHAVE_REDE_SME, "abrangencia:rede-sme"
        )
        self.assertEqual(
            RedeSmeCacheRepository.chave_codigo("turma", "9999101"),
            "abrangencia:turma:9999101",
        )

    def test_rede_vale_ate_a_virada_do_dia(self) -> None:
        """Garante TTL ate a virada do dia."""
        self.repositorio.armazenar_rede_sme({"rede": 1})

        self.cache.armazenar.assert_called_once_with(
            "abrangencia:rede-sme", {"rede": 1}, ttl=3600
        )

    def test_codigos_valem_24_horas_para_dre_e_ue_e_4_para_turma(
        self,
    ) -> None:
        """Garante o TTL por tipo."""
        casos = {
            "dre": ("900100", 24 * 3600),
            "ue": ("900101", 24 * 3600),
            "turma": ("9999101", 4 * 3600),
        }

        for tipo, (codigo, ttl) in casos.items():
            with self.subTest(tipo=tipo):
                self.cache.reset_mock()

                self.repositorio.armazenar_codigos(tipo, {codigo: {"a": 1}})

                self.cache.armazenar_varios.assert_called_once_with(
                    {f"abrangencia:{tipo}:{codigo}": {"a": 1}}, ttl=ttl
                )

    def test_obter_codigos_devolve_pelo_codigo(self) -> None:
        """Garante o codigo como chave do retorno."""
        self.cache.obter_varios.return_value = {
            "abrangencia:dre:900100": {"nomeDRE": "DRE"},
            "abrangencia:dre:900200": "corrompido",
        }

        resultado = self.repositorio.obter_codigos(
            "dre", ["900100", "900200", "900300"]
        )

        self.assertEqual(resultado, {"900100": {"nomeDRE": "DRE"}})


class TestIntegracaoEolCacheRepository(SimpleTestCase):
    """Valida chaves e TTL do cache."""

    def setUp(self) -> None:
        """Cria o repositorio sobre um cache falso."""
        self.cache = MagicMock()
        self.repositorio = IntegracaoEolCacheRepository(self.cache)

    def test_ttl_e_o_do_legado(self) -> None:
        """Garante 24 horas a partir da gravacao, como no legado."""
        self.repositorio.armazenar_lista(
            "abrangencia:nome-abreviacao-dres", ["1"]
        )
        self.repositorio.armazenar_estrutura_vigente(
            "900100", {"dres": [{"codigo": "900100"}]}
        )

        self.assertEqual(TTL_LEGADO, 1440 * 60)
        self.cache.armazenar.assert_any_call(
            "abrangencia:nome-abreviacao-dres", ["1"], ttl=TTL_LEGADO
        )
        self.cache.armazenar.assert_any_call(
            "abrangencia:estrutura-vigente:900100",
            {"dres": [{"codigo": "900100"}]},
            ttl=TTL_LEGADO,
        )

    def test_valor_de_outro_tipo_e_ausencia(self) -> None:
        """Garante que valor corrompido no cache vira ausencia."""
        self.cache.obter.return_value = "corrompido"

        self.assertIsNone(self.repositorio.obter_lista("chave"))
        self.assertIsNone(self.repositorio.obter_estrutura_vigente("900100"))


class TestPerfilCacheRepository(SimpleTestCase):
    """Valida chave e TTL do cache."""

    _GUID = "AAAAAAAA-0000-4000-8000-000000000001"

    def setUp(self) -> None:
        """Cria o repositorio sobre um cache falso."""
        self.cache = MagicMock()
        self.repositorio = PerfilCacheRepository(self.cache)

    def test_chave_nao_depende_da_caixa_do_guid(self) -> None:
        """Garante uma so entrada por perfil."""
        self.assertEqual(
            PerfilCacheRepository.chave_perfil(self._GUID),
            PerfilCacheRepository.chave_perfil(self._GUID.lower()),
        )
        self.assertEqual(
            PerfilCacheRepository.chave_perfil(self._GUID),
            "abrangencia:perfil:aaaaaaaa-0000-4000-8000-000000000001",
        )

    def test_ttl_e_o_do_legado(self) -> None:
        """Garante o periodo a partir da gravacao."""
        self.repositorio.armazenar_perfil(self._GUID, {"grupo": 1})

        self.cache.armazenar.assert_called_once_with(
            "abrangencia:perfil:aaaaaaaa-0000-4000-8000-000000000001",
            {"grupo": 1},
            ttl=TTL_LEGADO,
        )

    def test_valor_de_outro_tipo_e_ausencia(self) -> None:
        """Garante que valor corrompido no cache vira ausencia."""
        self.cache.obter.return_value = "corrompido"

        self.assertIsNone(self.repositorio.obter_perfil(self._GUID))
