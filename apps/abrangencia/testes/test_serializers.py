"""Testes dos serializers do domínio Abrangência."""

from django.test import SimpleTestCase

from apps.abrangencia.serializers import (
    AbrangenciaCompactaSerializer,
    BuscarUsuariosPerfisSerializer,
    GrupoCargosSerializer,
    UsuarioPerfilsAbrangenciaSerializer,
)

_UUID_PERFIL = "2e89cf10-e42b-476f-8673-2dfbeeee3cd0"


class TestGrupoCargosSerializer(SimpleTestCase):
    """Testes de `GrupoCargosSerializer`."""

    def test_serializa_perfil_com_vinculos(self) -> None:
        """Serializa cargos e funções já ordenados."""
        dados = {
            "grupoID": _UUID_PERFIL,
            "cargosId": [1, 2],
            "funcoesId": [3],
            "grupo": 10,
            "abrangencia": 1,
            "ehPerfilManual": False,
        }

        serializer = GrupoCargosSerializer(dados)

        self.assertEqual(serializer.data, dados)


class TestAbrangenciaCompactaSerializer(SimpleTestCase):
    """Testes de `AbrangenciaCompactaSerializer`."""

    def test_campos_de_escopo_aceitam_null(self) -> None:
        """`idDres`/`idUes`/`idTurmas` podem ser `null`."""
        dados = {
            "login": "5059151",
            "abrangencia": None,
            "idDres": None,
            "dres": None,
            "idUes": ["019331"],
            "ues": None,
            "idTurmas": [],
            "turmas": None,
        }

        serializer = AbrangenciaCompactaSerializer(dados)

        self.assertIsNone(serializer.data["idDres"])
        self.assertEqual(serializer.data["idUes"], ["019331"])
        self.assertEqual(serializer.data["idTurmas"], [])

    def test_coleções_expandidas_aceitam_itens(self) -> None:
        """`dres`/`ues`/`turmas` aceitam listas de objetos expandidos."""
        dados = {
            "login": "5059151",
            "abrangencia": None,
            "idDres": ["108100"],
            "dres": [
                {"codigoDRE": "108100", "nomeDRE": None, "siglaDRE": None}
            ],
            "idUes": None,
            "ues": None,
            "idTurmas": None,
            "turmas": None,
        }

        serializer = AbrangenciaCompactaSerializer(dados)

        self.assertEqual(len(serializer.data["dres"]), 1)
        self.assertEqual(serializer.data["dres"][0]["codigoDRE"], "108100")


class TestBuscarUsuariosPerfisSerializer(SimpleTestCase):
    """Testes de validação de `BuscarUsuariosPerfisSerializer`."""

    def test_ue_e_perfis_sao_obrigatorios(self) -> None:
        """Corpo sem `ue`/`perfis` é inválido."""
        serializer = BuscarUsuariosPerfisSerializer(data={})

        self.assertFalse(serializer.is_valid())
        self.assertIn("ue", serializer.errors)
        self.assertIn("perfis", serializer.errors)

    def test_dre_e_opcional_com_default_none(self) -> None:
        """Sem `dre` no corpo, o campo é validado como `None`."""
        serializer = BuscarUsuariosPerfisSerializer(
            data={"ue": "019331", "perfis": [_UUID_PERFIL]}
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIsNone(serializer.validated_data["dre"])

    def test_perfis_deve_conter_guids_validos(self) -> None:
        """Um perfil que não é GUID torna o corpo inválido."""
        serializer = BuscarUsuariosPerfisSerializer(
            data={"ue": "019331", "perfis": ["nao-e-guid"]}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("perfis", serializer.errors)


class TestUsuarioPerfilsAbrangenciaSerializer(SimpleTestCase):
    """Garante a preservação da grafia `perfils` exigida pelo contrato."""

    def test_serializa_com_a_chave_perfils(self) -> None:
        """A chave é `perfils`, sem o `i` — erro de digitação preservado."""
        dados = {
            "usuarioRf": "5059151",
            "perfils": [{"perfil": _UUID_PERFIL, "ues": ["019331"]}],
        }

        serializer = UsuarioPerfilsAbrangenciaSerializer(dados)

        self.assertIn("perfils", serializer.data)
        self.assertNotIn("perfis", serializer.data)
