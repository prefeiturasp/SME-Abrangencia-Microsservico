"""Testes da rede lida dos MS Institucional e Pedagogico."""

from datetime import datetime
from typing import Any
from unittest.mock import ANY, MagicMock, patch
from zoneinfo import ZoneInfo

import httpx
from django.core.cache.backends.locmem import LocMemCache
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings

from apps.abrangencia.cache_repository import (
    IntegracaoEolCacheRepository,
    RedeSmeCacheRepository,
)
from apps.abrangencia.models import ParametroSistema, Sistema
from apps.abrangencia.rede_sme import (
    RedeSme,
    RedeSmeIncompletaError,
    _RedeSme,
    estrutura_vigente_por_dre,
    tipos_escola_exibidos,
    turma_de_sondagem,
    turma_listavel,
)
from apps.core.cache import CacheRepository

_FUSO = ZoneInfo("America/Sao_Paulo")
_AGORA = datetime(2026, 10, 21, 10, 0, tzinfo=_FUSO)
_COMANDO = (
    "apps.abrangencia.management.commands.carregar_rede_sme.obter_rede_sme"
)

_DRE_A = "900100"
_DRE_B = "900200"

_UE_VIGENTE = "900101"

_UE_NAO_EXIBIDA = "900102"

_UE_ANTIGA = "900103"

_UE_FORA_DA_ESTRUTURA = "900104"

_UE_OUTRA_DRE = "900201"

_UNIDADES = {
    _DRE_A: [
        {"codigoEol": _UE_VIGENTE, "nomeNaoOficial": "EMEF TESTE A"},
        {"codigoEol": _UE_NAO_EXIBIDA, "nomeNaoOficial": "CEI TESTE B"},
        {"codigoEol": _UE_ANTIGA, "nomeNaoOficial": "EMEF TESTE C"},
        {"codigoEol": _UE_FORA_DA_ESTRUTURA, "nomeNaoOficial": "EMEI TESTE D"},
    ],
    _DRE_B: [{"codigoEol": _UE_OUTRA_DRE, "nomeNaoOficial": "CIEJA TESTE E"}],
}

_TIPOS_ESCOLA = {
    _UE_VIGENTE: 1,
    _UE_NAO_EXIBIDA: 10,
    _UE_ANTIGA: 1,
    _UE_FORA_DA_ESTRUTURA: 3,
    _UE_OUTRA_DRE: 16,
}

_DRE_DA_UE = {
    ue: dre for dre, unidades in _UNIDADES.items() for ue in
    (unidade["codigoEol"] for unidade in unidades)
}


def _turma(
    codigo: int, ue: str, ano_letivo: int, serie: str, etapa: int
) -> dict[str, Any]:
    return {
        "codigo": codigo,
        "ano_letivo": ano_letivo,
        "ano": serie,
        "codigo_etapa_ensino": etapa,
        "nome_turma": f"TURMA {codigo}",
        "ue_codigo": ue,
    }


_TURMAS = {
    9999101: _turma(9999101, _UE_VIGENTE, 2026, "1", 5),
    9999102: _turma(9999102, _UE_VIGENTE, 2026, "10", 13),
    9999103: _turma(9999103, _UE_VIGENTE, 2026, "7", 5),
    9999104: _turma(9999104, _UE_VIGENTE, 2026, "1", 1),
    9999105: _turma(9999105, _UE_VIGENTE, 2025, "2", 5),
    9999201: _turma(9999201, _UE_NAO_EXIBIDA, 2026, "1", 5),
    9999301: _turma(9999301, _UE_OUTRA_DRE, 2026, "3", 13),
    9999401: _turma(9999401, _UE_ANTIGA, 2009, "1", 5),
    9999501: _turma(9999501, _UE_FORA_DA_ESTRUTURA, 2015, "1", 5),
}

_ESTRUTURA = {
    _DRE_A: [
        {
            "codigo": _UE_VIGENTE,
            "codTipoEscola": 1,
            "turmas": [
                {"codigo": c}
                for c in (9999101, 9999102, 9999103, 9999104, 9999105)
            ],
        },
        {
            "codigo": _UE_NAO_EXIBIDA,
            "codTipoEscola": 10,
            "turmas": [{"codigo": 9999201}],
        },
    ],
    _DRE_B: [
        {
            "codigo": _UE_OUTRA_DRE,
            "codTipoEscola": 16,
            "turmas": [{"codigo": 9999301}],
        }
    ],
}

_TURMAS_DE_ANOS_ANTERIORES = {
    _UE_ANTIGA: ["9999401"],
    _UE_FORA_DA_ESTRUTURA: ["9999501"],
}


def _institucional() -> MagicMock:
    api = MagicMock()
    api.codigos_dres.side_effect = lambda: httpx.Response(
        200, json=[_DRE_B, _DRE_A]
    )
    api.dres.side_effect = lambda codigos: [
        {"codigoDRE": c, "nomeDRE": f"DRE TESTE {c}", "siglaDRE": f"DT{c}"}
        for c in codigos
        if c in _UNIDADES
    ]
    api.unidades_da_dre.side_effect = lambda dre: _UNIDADES.get(dre, [])
    api.escolas.side_effect = lambda codigos: [
        {
            "codigoEscola": c,
            "nomeEscola": f"ESCOLA TESTE {c}",
            "codigoDRE": _DRE_DA_UE[c],
            "codigoTipoEscola": _TIPOS_ESCOLA[c],
        }
        for c in codigos
        if c in _TIPOS_ESCOLA
    ]
    return api


def _pedagogico() -> MagicMock:
    api = MagicMock()
    api.estrutura_vigente_por_dre.side_effect = lambda dre: {
        "dres": [{"codigo": dre, "ues": _ESTRUTURA.get(dre, [])}]
    }
    api.listar_turmas.side_effect = lambda codigos: [
        _TURMAS[c] for c in codigos if c in _TURMAS
    ]

    def turmas_da_ue(ue: str, anos: list[int]) -> list[str]:
        if anos == [_AGORA.year]:
            return []
        return _TURMAS_DE_ANOS_ANTERIORES.get(ue, [])

    api.codigos_turma_da_ue.side_effect = turmas_da_ue
    return api


def _chamadas(*apis: MagicMock) -> int:
    return sum(len(api.method_calls) for api in apis)


class _BaseRede(TestCase):
    """Rede com valores falsos, cache limpo e o relogio fixo."""

    def setUp(self) -> None:
        """Cria o parametro, valores falsos e fixa a data."""
        Sistema.objects.create(sistema_id=0, sistema="Global", ativo=True)
        Sistema.objects.create(sistema_id=1000, sistema="Teste", ativo=True)
        self.parametro(1000, "1,3,4,16")
        self.keydb = LocMemCache("rede-teste", {})
        self.keydb.clear()
        self.cliente_redis = MagicMock()
        self.cliente_redis.lock.return_value.acquire.return_value = True
        self.agora = _AGORA
        for alvo in (
            "apps.abrangencia.cache_repository.agora",
            "apps.abrangencia.rede_sme.agora",
        ):
            relogio = patch(alvo, side_effect=lambda: self.agora)
            relogio.start()
            self.addCleanup(relogio.stop)
        self.institucional = _institucional()
        self.pedagogico = _pedagogico()
        self.rede_sme = self.nova_rede_sme()

    def nova_rede_sme(self) -> RedeSme:
        """Cria outra instancia, como a de outro request."""
        repositorio = CacheRepository(self.keydb, self.cliente_redis)
        return RedeSme(
            self.institucional,
            self.pedagogico,
            RedeSmeCacheRepository(repositorio),
            IntegracaoEolCacheRepository(repositorio),
        )

    def parametro(
        self, sistema: int, valor: str, *, ano: int = 2026, ativo: bool = True
    ) -> None:
        """Grava `tipos_escola_exibidos` de um sistema."""
        ParametroSistema.objects.create(
            parametro_sistema_id=ParametroSistema.objects.count() + 1,
            sistema_id=sistema,
            nome="tipos_escola_exibidos",
            formato="array_int",
            categoria="regra_negocio",
            descricao="Tipos de escola exibidos.",
            valor=valor,
            ano_letivo=ano,
            ativo=ativo,
        )


class TestUesDaRede(_BaseRede):
    """Testes de `RedeSme.ues` e dos atributos de UE."""

    def test_ue_de_tipo_exibido_com_turma_listavel(self) -> None:
        """Garante a rede pela estrutura vigente e pelos anos anteriores."""
        self.assertEqual(
            self.rede_sme.ues(),
            {_UE_VIGENTE, _UE_OUTRA_DRE, _UE_FORA_DA_ESTRUTURA},
        )

    def test_ue_de_tipo_nao_exibido_fica_fora(self) -> None:
        """Garante que a UE de tipo nao exibido nao entra, mesmo com turma."""
        self.assertNotIn(_UE_NAO_EXIBIDA, self.rede_sme.ues())

    def test_ue_so_com_turma_antes_de_2010_fica_fora(self) -> None:
        """Garante que turma de 2009, sem grade, nao poe a UE na rede."""
        self.assertNotIn(_UE_ANTIGA, self.rede_sme.ues())

    def test_ue_pedida_fora_da_rede_nao_tem_atributos(self) -> None:
        """Garante que so UE da rede aparece na colecao."""
        atributos = self.rede_sme.atributos_ues(
            [_UE_VIGENTE, _UE_NAO_EXIBIDA, _UE_ANTIGA]
        )

        self.assertEqual(list(atributos), [_UE_VIGENTE])

    def test_rede_guarda_sigla_so_das_ues_da_rede(self) -> None:
        """Garante que a rede no cache leva so a sigla das UEs da rede."""
        self.rede_sme.ues()
        rede = self.keydb.get("abrangencia:rede-sme")

        self.assertEqual(set(rede.siglas), set(rede.ues))
        self.assertNotIn(_UE_NAO_EXIBIDA, rede.siglas)
        self.assertEqual(rede.siglas[_UE_VIGENTE], "EMEF TESTE A")

    def test_rede_de_outra_versao_e_montada_de_novo(self) -> None:
        """Garante que rede gravada sem um campo atual nao quebra a consulta."""
        antiga = object.__new__(_RedeSme)
        object.__setattr__(antiga, "dres", (_DRE_A,))
        self.keydb.set("abrangencia:rede-sme", antiga)

        self.assertIn(_UE_VIGENTE, self.rede_sme.ues())
        self.institucional.codigos_dres.assert_called_once_with()

    def test_atributos_da_ue(self) -> None:
        """Garante sigla do `nomeNaoOficial`; nome e DRE da escola."""
        atributos = self.rede_sme.atributos_ues([_UE_VIGENTE])

        self.assertEqual(
            atributos[_UE_VIGENTE],
            {
                "nome": f"ESCOLA TESTE {_UE_VIGENTE}",
                "sigla": "EMEF TESTE A",
                "dre_codigo": _DRE_A,
            },
        )

    def test_unidades_da_dre_pelo_institucional(self) -> None:
        """Garante o retorno com unidades."""
        self.assertEqual(
            self.rede_sme.unidades_da_dre(_DRE_A),
            {_UE_VIGENTE, _UE_NAO_EXIBIDA, _UE_ANTIGA, _UE_FORA_DA_ESTRUTURA},
        )
        self.assertEqual(
            self.rede_sme.unidades_da_dre(_DRE_B), {_UE_OUTRA_DRE}
        )
        self.assertEqual(self.rede_sme.unidades_da_dre("900900"), frozenset())

    def test_unidades_da_dre_nao_montam_a_rede(self) -> None:
        """Garante uma chamada so, a da DRE pedida."""
        self.rede_sme.unidades_da_dre(_DRE_A)

        self.institucional.unidades_da_dre.assert_called_once_with(_DRE_A)
        self.institucional.codigos_dres.assert_not_called()
        self.pedagogico.estrutura_vigente_por_dre.assert_not_called()
        self.pedagogico.listar_turmas.assert_not_called()
        self.assertIsNone(self.keydb.get("abrangencia:rede-sme"))


class TestDresDaRede(_BaseRede):
    """Testes das DREs da rede."""

    def test_dres_de_codigos_dres_ordenadas(self) -> None:
        """Garante as DREs que o perfil SME recebe."""
        self.assertEqual(self.rede_sme.dres(), [_DRE_A, _DRE_B])

    def test_codigos_dres_nao_montam_a_rede(self) -> None:
        """Garante so `codigos-dres`, sem unidade, estrutura nem turma."""
        self.assertEqual(self.rede_sme.codigos_dres(), [_DRE_A, _DRE_B])

        self.institucional.codigos_dres.assert_called_once_with()
        self.institucional.unidades_da_dre.assert_not_called()
        self.pedagogico.estrutura_vigente_por_dre.assert_not_called()
        self.pedagogico.listar_turmas.assert_not_called()

    def test_codigos_dres_nao_tem_cache_aqui(self) -> None:
        """Garante a chamada ao Institucional, que ja possui essa lista."""
        self.rede_sme.codigos_dres()
        self.nova_rede_sme().codigos_dres()

        self.assertEqual(self.institucional.codigos_dres.call_count, 2)

    def test_codigos_dres_vazio_e_erro(self) -> None:
        """Garante 503, e nao `idDres` vazio, sem DRE."""
        self.institucional.codigos_dres.side_effect = lambda: httpx.Response(
            204
        )

        with self.assertRaises(RedeSmeIncompletaError):
            self.rede_sme.codigos_dres()

    def test_atributos_das_dres(self) -> None:
        """Garante nome e sigla do `POST /dres/`, so das existentes."""
        atributos = self.rede_sme.atributos_dres([_DRE_A, "900900"])

        self.assertEqual(
            atributos,
            {_DRE_A: {"nome": f"DRE TESTE {_DRE_A}", "sigla": f"DT{_DRE_A}"}},
        )


class TestTurmas(_BaseRede):
    """Testes de `RedeSme.turmas`."""

    _PEDIDAS = [
        "9999101",
        "9999102",
        "9999103",
        "9999104",
        "9999105",
        "9999201",
        "9999999",
    ]

    def test_so_turma_listavel_do_ano_e_de_ue_exibida(self) -> None:
        """Garante que turma de outro ano, etapa ou UE nao exibida sai."""
        turmas = self.rede_sme.turmas(self._PEDIDAS, 2026, sondagem=False)

        self.assertEqual(sorted(turmas), ["9999101", "9999102", "9999103"])
        self.assertEqual(
            turmas["9999101"],
            {"nome": "TURMA 9999101", "ue_codigo": _UE_VIGENTE},
        )

    def test_sondagem_compara_a_serie_como_texto(self) -> None:
        """Garante que a serie `"10"` entra e a `"7"` nao, como no legado."""
        turmas = self.rede_sme.turmas(self._PEDIDAS, 2026, sondagem=True)

        self.assertEqual(sorted(turmas), ["9999101", "9999102"])

    def test_turmas_de_sondagem_da_estrutura_vigente(self) -> None:
        """Garante as turmas de sondagem da rede."""
        turmas = self.rede_sme.turmas_de_sondagem(2026)

        self.assertEqual(sorted(turmas), ["9999101", "9999102", "9999301"])

    def test_ano_sem_estrutura_vigente_nao_tem_turma(self) -> None:
        """Garante colecao vazia para um ano sem turma vigente."""
        self.assertEqual(self.rede_sme.turmas_de_sondagem(2024), {})


class TestRegrasDaTurma(SimpleTestCase):
    """Testes de `turma_listavel` e `turma_de_sondagem`."""

    def test_turma_listavel(self) -> None:
        """Garante etapa da lista e ano letivo de 2010 em diante."""
        casos = {
            (2010, 5): True,
            (2009, 5): False,
            (2026, 1): False,
            (2026, 18): True,
        }

        for (ano_letivo, etapa), esperado in casos.items():
            with self.subTest(ano_letivo=ano_letivo, etapa=etapa):
                turma = {
                    "ano_letivo": ano_letivo,
                    "codigo_etapa_ensino": etapa,
                }
                self.assertEqual(turma_listavel(turma), esperado)

    def test_turma_de_sondagem(self) -> None:
        """Garante serie de `"1"` a `"6"` como texto e etapa 5 ou 13."""
        casos = {
            ("1", 5): True,
            ("6", 13): True,
            ("10", 5): True,
            ("7", 5): False,
            ("", 5): False,
            ("1", 6): False,
        }

        for (serie, etapa), esperado in casos.items():
            with self.subTest(serie=serie, etapa=etapa):
                turma = {"ano": serie, "codigo_etapa_ensino": etapa}
                self.assertEqual(turma_de_sondagem(turma), esperado)


class TestCacheDaRede(_BaseRede):
    """Testes do cache diario da rede."""

    def test_segundo_request_do_dia_nao_chama_os_ms(self) -> None:
        """Garante a rede do cache, na mesma instancia e em outra."""
        self.rede_sme.ues()
        antes = _chamadas(self.institucional, self.pedagogico)

        self.rede_sme.ues()
        self.nova_rede_sme().ues()
        self.nova_rede_sme().dres()

        self.assertGreater(antes, 0)
        self.assertEqual(
            _chamadas(self.institucional, self.pedagogico), antes
        )

    def test_consulta_por_codigo_fica_em_cache(self) -> None:
        """Garante que turma ja buscada no cache."""
        self.rede_sme.turmas(["9999101"], 2026, sondagem=False)
        antes = self.pedagogico.listar_turmas.call_count

        self.nova_rede_sme().turmas(["9999101"], 2026, sondagem=False)

        self.assertEqual(self.pedagogico.listar_turmas.call_count, antes)

    def test_rede_vale_ate_a_virada_do_dia(self) -> None:
        """Garante a rede gravada com TTL."""
        with patch.object(self.keydb, "set", wraps=self.keydb.set) as gravar:
            self.rede_sme.ues()

        gravar.assert_any_call("abrangencia:rede-sme", ANY, timeout=14 * 3600)

class TestEstruturaVigenteDividida(_BaseRede):
    """Testes da estrutura vigente dividida entre a rede SME."""

    def test_montagem_grava_a_estrutura_para_o_e04(self) -> None:
        """Garante a estrutura buscada."""
        self.rede_sme.ues()
        cache = IntegracaoEolCacheRepository(
            CacheRepository(self.keydb, self.cliente_redis)
        )
        antes = self.pedagogico.estrutura_vigente_por_dre.call_count

        estrutura = estrutura_vigente_por_dre(_DRE_A, self.pedagogico, cache)

        self.assertEqual(
            self.pedagogico.estrutura_vigente_por_dre.call_count, antes
        )
        self.assertEqual(estrutura["dres"][0]["codigo"], _DRE_A)

    def test_montagem_usa_a_estrutura_ja_em_cache(self) -> None:
        """Garante que a montagem nao repete a chamada feita."""
        cache = IntegracaoEolCacheRepository(
            CacheRepository(self.keydb, self.cliente_redis)
        )
        for dre in (_DRE_A, _DRE_B):
            estrutura_vigente_por_dre(dre, self.pedagogico, cache)
        self.pedagogico.estrutura_vigente_por_dre.reset_mock()

        self.rede_sme.ues()

        self.pedagogico.estrutura_vigente_por_dre.assert_not_called()

    def test_estrutura_sem_dre_volta_ao_ms(self) -> None:
        """Garante que estrutura sem DRE nao fica no cache."""
        cache = IntegracaoEolCacheRepository(
            CacheRepository(self.keydb, self.cliente_redis)
        )

        self.pedagogico.estrutura_vigente_por_dre.side_effect = None
        self.pedagogico.estrutura_vigente_por_dre.return_value = {"dres": []}

        for _ in range(2):
            estrutura = estrutura_vigente_por_dre(
                "900900", self.pedagogico, cache
            )

        self.assertEqual(estrutura, {"dres": []})
        self.assertEqual(
            self.pedagogico.estrutura_vigente_por_dre.call_count, 2
        )


@override_settings(CACHE_LOCK_TTL=120, CACHE_LOCK_WAIT_TIMEOUT=90)
class TestLockDaMontagem(_BaseRede):
    """Testes do lock distribuido da montagem da rede."""

    def test_monta_com_o_lock_e_o_libera(self) -> None:
        """Garante a montagem dentro do lock da chave da rede."""
        self.rede_sme.ues()

        self.cliente_redis.lock.assert_called_once_with(
            "lock:abrangencia:rede-sme",
            timeout=120,
            blocking_timeout=90,
        )
        self.cliente_redis.lock.return_value.release.assert_called_once()

    def test_rede_montada_por_outro_enquanto_esperava(self) -> None:
        """Garante que quem esperou o lock le a rede."""
        montada = self.nova_rede_sme()
        montada.ues()
        antes = _chamadas(self.institucional, self.pedagogico)
        rede = self.nova_rede_sme()

        with patch.object(
            rede, "_rede_sme_em_cache", side_effect=[None, montada._rede_sme()]
        ):
            rede.ues()

        self.assertEqual(
            _chamadas(self.institucional, self.pedagogico), antes
        )

    def test_sem_lock_monta_mesmo_assim(self) -> None:
        """Garante a resposta mesmo sem o lock, montando a rede."""
        self.cliente_redis.lock.return_value.acquire.return_value = False

        self.assertIn(_UE_VIGENTE, self.rede_sme.ues())
        self.cliente_redis.lock.return_value.release.assert_not_called()

    def test_keydb_fora_do_ar_nao_derruba_a_consulta(self) -> None:
        """Garante que o KeyDB indisponivel so faz a rede ser montada."""
        keydb = MagicMock()
        keydb.get.side_effect = ConnectionError("KeyDB indisponivel")
        keydb.get_many.side_effect = ConnectionError("KeyDB indisponivel")
        keydb.set.side_effect = ConnectionError("KeyDB indisponivel")
        keydb.set_many.side_effect = ConnectionError("KeyDB indisponivel")
        cache = RedeSmeCacheRepository(CacheRepository(keydb, MagicMock()))
        rede = RedeSme(self.institucional, self.pedagogico, cache)

        with self.assertLogs("apps.core.cache", level="ERROR"):
            self.assertIn(_UE_VIGENTE, rede.ues())


class TestRedeIncompleta(_BaseRede):
    """Garante que a rede vazia nao vai para o cache."""

    def _assert_incompleta(self, falta: str) -> None:
        with self.assertRaises(RedeSmeIncompletaError) as erro:
            self.rede_sme.ues()
        self.assertIn(falta, str(erro.exception))
        self.assertIsNone(self.keydb.get("abrangencia:rede-sme"))

    def test_codigos_dres_vazio(self) -> None:
        """Garante erro, e nao rede sem DRE."""
        self.institucional.codigos_dres.side_effect = lambda: httpx.Response(
            204
        )

        self._assert_incompleta("codigos-dres sem DRE")

    def test_dre_sem_unidade(self) -> None:
        """Garante erro quando nao traz unidade da DRE."""
        self.institucional.unidades_da_dre.side_effect = lambda dre: (
            [] if dre == _DRE_B else _UNIDADES[dre]
        )

        self._assert_incompleta(f"DRE sem unidade: {_DRE_B}")

    def test_dre_sem_estrutura_vigente(self) -> None:
        """Garante erro quando nao traz a estrutura da DRE."""
        self.pedagogico.estrutura_vigente_por_dre.side_effect = lambda dre: (
            {"dres": []}
            if dre == _DRE_B
            else {"dres": [{"codigo": dre, "ues": _ESTRUTURA[dre]}]}
        )

        self._assert_incompleta(f"DRE sem estrutura vigente: {_DRE_B}")

    def test_sem_turma_listavel(self) -> None:
        """Garante erro quando `listar-turmas` nao traz turma nenhuma."""
        self.pedagogico.listar_turmas.side_effect = lambda codigos: []

        self._assert_incompleta("estrutura vigente sem turma listavel")

    def test_proxima_consulta_monta_de_novo(self) -> None:
        """Garante que a rede e montada e gravada."""
        self.institucional.codigos_dres.side_effect = lambda: httpx.Response(
            204
        )
        with self.assertRaises(RedeSmeIncompletaError):
            self.rede_sme.ues()

        self.institucional.codigos_dres.side_effect = lambda: httpx.Response(
            200, json=[_DRE_B, _DRE_A]
        )

        self.assertIn(_UE_VIGENTE, self.nova_rede_sme().ues())
        self.assertIsNotNone(
            self.keydb.get("abrangencia:rede-sme")
        )


class TestLoteVazio(_BaseRede):
    """Garante que lote inteiro vazio nao fica no cache como ausente."""

    def test_lote_vazio_e_pedido_de_novo(self) -> None:
        """Garante que a falha passageira nao tira os codigos do dia."""
        self.rede_sme.ues()
        listar = self.pedagogico.listar_turmas
        listar.reset_mock()
        listar.side_effect = lambda codigos: []
        self.rede_sme.turmas(["9999777"], 2026, sondagem=False)

        listar.side_effect = lambda codigos: [
            _turma(9999777, _UE_VIGENTE, 2026, "1", 5)
        ]
        turmas = self.nova_rede_sme().turmas(
            ["9999777"], 2026, sondagem=False
        )

        self.assertEqual(listar.call_count, 2)
        self.assertEqual(list(turmas), ["9999777"])

    def test_ausente_num_lote_com_outros_fica_no_cache(self) -> None:
        """Garante o ausente gravado quando retorna parte do lote."""
        self.rede_sme.ues()
        listar = self.pedagogico.listar_turmas
        listar.reset_mock()
        listar.side_effect = lambda codigos: [
            _turma(9999777, _UE_VIGENTE, 2026, "1", 5)
        ]

        for _ in range(2):
            self.nova_rede_sme().turmas(
                ["9999777", "9999998"], 2026, sondagem=False
            )

        listar.assert_called_once_with([9999777, 9999998])


class TestFalhaDosMs(_BaseRede):
    """Testes da falha dos MS."""

    def test_ms_fora_do_ar_sobe_o_erro(self) -> None:
        """Garante erro explicito, e nunca rede vazia."""
        self.institucional.unidades_da_dre.side_effect = httpx.ConnectError(
            "recusada"
        )

        with self.assertRaises(httpx.ConnectError):
            self.rede_sme.ues()

    def test_rede_que_falhou_nao_fica_em_cache(self) -> None:
        """Garante que a consulta seguinte tenta montar a rede de novo."""
        self.institucional.unidades_da_dre.side_effect = httpx.ConnectError(
            "recusada"
        )
        with self.assertRaises(httpx.ConnectError):
            self.rede_sme.ues()

        self.institucional.unidades_da_dre.side_effect = (
            lambda dre: _UNIDADES.get(dre, [])
        )

        self.assertIn(_UE_VIGENTE, self.rede_sme.ues())


class TestTiposEscolaExibidos(_BaseRede):
    """Testes de `tipos_escola_exibidos`."""

    def test_linha_do_sistema_ativo(self) -> None:
        """Garante a linha do sistema antes da global."""
        self.parametro(0, "1")

        self.assertEqual(tipos_escola_exibidos(2026), {1, 3, 4, 16})

    def test_linha_global_sem_a_do_sistema(self) -> None:
        """Garante a linha global quando o sistema nao tem a sua."""
        ParametroSistema.objects.all().delete()
        self.parametro(0, "1,3")

        self.assertEqual(tipos_escola_exibidos(2026), {1, 3})

    def test_ignora_inativo_e_outro_ano(self) -> None:
        """Garante que so vale a linha ativa do ano."""
        ParametroSistema.objects.all().delete()
        self.parametro(1000, "1", ano=2025)
        self.parametro(1000, "3", ativo=False)
        self.parametro(0, "4")

        self.assertEqual(tipos_escola_exibidos(2026), {4})

    def test_ausente_ou_vazio_e_erro_de_configuracao(self) -> None:
        """Garante erro, e nao lista vazia, sem o parametro."""
        ParametroSistema.objects.all().delete()
        with self.assertRaises(ImproperlyConfigured):
            tipos_escola_exibidos(2026)

        self.parametro(1000, "")
        with self.assertRaises(ImproperlyConfigured):
            tipos_escola_exibidos(2026)

    def test_sistema_inativo_nao_conta(self) -> None:
        """Garante que nem a linha global vale sem sistema ativo."""
        Sistema.objects.filter(sistema_id=1000).update(ativo=False)

        with self.assertRaises(ImproperlyConfigured):
            tipos_escola_exibidos(2026)


class TestCarregarRedeSme(_BaseRede):
    """Testes do comando `carregar_rede_sme`."""

    def test_monta_a_rede_do_dia(self) -> None:
        """Garante que o primeiro request ja encontra a rede em cache."""
        saida = MagicMock()
        with patch(_COMANDO, return_value=self.rede_sme):
            call_command("carregar_rede_sme", stdout=saida)
        antes = _chamadas(self.institucional, self.pedagogico)

        self.nova_rede_sme().ues()

        self.assertEqual(
            _chamadas(self.institucional, self.pedagogico), antes
        )
        saida.write.assert_called_once()

    def test_rede_incompleta_falha_o_comando(self) -> None:
        """Garante saida diferente de zero quando resposta vem vazia."""
        self.institucional.codigos_dres.side_effect = lambda: httpx.Response(
            204
        )

        with (
            patch(_COMANDO, return_value=self.rede_sme),
            self.assertRaises(CommandError),
        ):
            call_command("carregar_rede_sme", stdout=MagicMock())

    def test_ms_fora_do_ar_falha_o_comando(self) -> None:
        """Garante saida diferente de zero quando nao vem resposta."""
        self.pedagogico.estrutura_vigente_por_dre.side_effect = (
            httpx.ConnectError("recusada")
        )

        with (
            patch(_COMANDO, return_value=self.rede_sme),
            self.assertRaises(CommandError),
        ):
            call_command("carregar_rede_sme", stdout=MagicMock())
