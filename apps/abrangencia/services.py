"""Servicos do dominio Abrangencia."""

from collections.abc import Mapping
from typing import Any

from django.conf import settings

from apps.abrangencia.constants import (
    GRUPO_COMUNICADOS_UE,
    ORIGENS_UE_POR_EXERCICIO,
    TIPO_RESOLUCAO_COMPACTA,
    TIPO_RESOLUCAO_DETALHES,
    TipoAbrangencia,
)
from apps.abrangencia.models import (
    AbrangenciaResolvida,
    Perfil,
    PerfilVinculoFuncional,
    UsuarioPorPerfil,
)
from apps.abrangencia.rede_sme import RedeSme, obter_rede_sme

_NIVEIS_VAZIOS_POR_TIPO_ABRANGENCIA: dict[int, frozenset[str]] = {
    TipoAbrangencia.PROFESSOR: frozenset({"idDres", "idUes", "idTurmas"}),
    TipoAbrangencia.SME: frozenset({"idDres", "idUes", "idTurmas"}),
    TipoAbrangencia.UE: frozenset({"idUes"}),
    TipoAbrangencia.UE_TURMAS_DISCIPLINAS: frozenset({"idUes"}),
    TipoAbrangencia.DRE: frozenset(),
    TipoAbrangencia.DRE_ESCOLAS_ATRIBUIDAS: frozenset(),
}

_NIVEIS_VAZIOS_DRE_NAO_MANUAL = frozenset({"idDres"})

_ORIGEM_CONTRATO_EXTERNO = "CONTRATO_EXTERNO"


_NIVEIS_VAZIOS_DETALHES: dict[int, frozenset[str]] = {
    TipoAbrangencia.PROFESSOR: frozenset({"idTurmas"}),
    TipoAbrangencia.SME: frozenset({"idDres"}),
    TipoAbrangencia.UE: frozenset({"idUes"}),
    TipoAbrangencia.UE_TURMAS_DISCIPLINAS: frozenset({"idTurmas"}),
    TipoAbrangencia.DRE: frozenset({"idDres"}),
    TipoAbrangencia.DRE_ESCOLAS_ATRIBUIDAS: frozenset({"idUes"}),
}


_TIPOS_ABRANGENCIA_DRE_DE_ID_DRES = frozenset(
    {TipoAbrangencia.DRE, TipoAbrangencia.SME}
)
_TIPOS_ABRANGENCIA_DRE_DERIVADA_DE_UE = frozenset(
    {TipoAbrangencia.UE, TipoAbrangencia.DRE_ESCOLAS_ATRIBUIDAS}
)
_TIPOS_ABRANGENCIA_QUE_EXPANDEM_UE = _TIPOS_ABRANGENCIA_DRE_DERIVADA_DE_UE
_TIPOS_ABRANGENCIA_QUE_EXPANDEM_TURMA = frozenset(
    {TipoAbrangencia.PROFESSOR, TipoAbrangencia.UE_TURMAS_DISCIPLINAS}
)

_TIPOS_ABRANGENCIA_QUE_EXPANDEM_DRE = (
    _TIPOS_ABRANGENCIA_DRE_DE_ID_DRES | _TIPOS_ABRANGENCIA_DRE_DERIVADA_DE_UE
)


_TIPO_CARGO = "CARGO"
_TIPO_FUNCAO_ATIVIDADE = "FUNCAO_ATIVIDADE"

Codigos = list[str | None]


def _sem_nulos(codigos: Codigos) -> list[str]:
    """Descarta o codigo nulo, que so `idUes` carrega.

    Args:
        codigos: Codigos de um nivel do escopo.

    Returns:
        Os mesmos codigos, sem o nulo.
    """
    return [codigo for codigo in codigos if codigo is not None]


class AbrangenciaService:
    """Servico responsavel pelas operacoes do dominio Abrangencia."""

    def __init__(self, rede_sme: RedeSme | None = None) -> None:
        self._rede_sme = rede_sme or obter_rede_sme()

    def grupo_cargos(
        self,
        perfil_guid: str,
        *,
        funcao_exige_cargo: bool = True,
        eh_grupo_manual: bool = True,
    ) -> dict | None:
        """Monta o payload de perfil com seus cargos e funcoes.

        Args:
            perfil_guid: GUID do perfil consultado.
            funcao_exige_cargo: Quando verdadeiro, perfil sem cargo sai
                sem funcao; ver `_perfil_com_vinculos`.
            eh_grupo_manual: Informa se o grupo do perfil e manual.

        Returns:
            Payload do perfil, ou None quando ele nao existe.
        """
        perfil = self._perfil_com_vinculos(
            perfil_guid, funcao_exige_cargo=funcao_exige_cargo
        )
        if perfil is None:
            return None
        return {
            "grupoID": str(perfil["perfil_guid"]),
            "cargosId": perfil["cargos"],
            "funcoesId": perfil["funcoes"],
            "grupo": perfil["grupo_codigo"],
            "abrangencia": perfil["abrangencia_id"],
            "ehPerfilManual": self._manual_do_perfil(
                perfil, eh_grupo_manual=eh_grupo_manual
            ),
        }

    def abrangencia_compacta(
        self,
        login: str,
        perfil_guid: str,
        ano_letivo: int | None = None,
        *,
        expandir_dres: bool = False,
        expandir_ues: bool = False,
        expandir_turmas: bool = False,
        algoritmo_alternativo: bool = False,
    ) -> dict[str, Any]:
        """Monta o payload de escopo compacto de um usuario em um perfil.

        Args:
            login: RF ou CPF do usuario.
            perfil_guid: GUID do perfil consultado.
            ano_letivo: Ano letivo; None usa `ABRANGENCIA_ANO_LETIVO`.
            expandir_dres: Preenche `dres`.
            expandir_ues: Preenche `ues`.
            expandir_turmas: Preenche `turmas`, restritas a sondagem.
            algoritmo_alternativo: Le as linhas de `tipo_resolucao`
                `DETALHES` em vez das de `COMPACTA`.

        Returns:
            Payload com as oito chaves do contrato, sempre presentes.
            Campo nao expandido sai `None`, nunca `[]`.

        Raises:
            httpx.HTTPError: Falhou ao trazer o que e da rede.
            RedeSmeIncompletaError: A rede SME veio incompleta.
            ImproperlyConfigured: Sem `tipos_escola_exibidos` no ano.
        """
        ano = ano_letivo if ano_letivo is not None else self._ano_letivo()
        tipo_resolucao = (
            TIPO_RESOLUCAO_DETALHES
            if algoritmo_alternativo
            else TIPO_RESOLUCAO_COMPACTA
        )
        (
            tipo_abrangencia,
            eh_perfil_manual,
            grupo_codigo,
        ) = self._tipo_abrangencia_do_perfil(perfil_guid)
        codigos = self._escopo_resolvido(
            login, perfil_guid, ano, tipo_resolucao
        )
        if tipo_abrangencia == TipoAbrangencia.SME and not codigos["idDres"]:
            dres_da_rede: Codigos = list(self._rede_sme.codigos_dres())
            codigos = {**codigos, "idDres": dres_da_rede}
        if algoritmo_alternativo and tipo_abrangencia == TipoAbrangencia.DRE:
            codigos = self._limitar_dre_unica(codigos)

        de_contrato_externo = (
            not algoritmo_alternativo
            and tipo_abrangencia == TipoAbrangencia.UE_TURMAS_DISCIPLINAS
            and self._escopo_veio_de_contrato_externo(login, perfil_guid, ano)
        )
        escopo = self._aplicar_nivel_vazio(
            codigos,
            tipo_abrangencia,
            algoritmo_alternativo=algoritmo_alternativo,
            escopo_de_contrato_externo=de_contrato_externo,
            eh_perfil_manual=eh_perfil_manual,
            grupo_codigo=grupo_codigo,
        )

        payload: dict[str, Any] = {
            "login": login,
            "abrangencia": self.grupo_cargos(
                perfil_guid,
                funcao_exige_cargo=algoritmo_alternativo,
                eh_grupo_manual=algoritmo_alternativo,
            ),
            "idDres": escopo["idDres"],
            "dres": None,
            "idUes": escopo["idUes"],
            "ues": None,
            "idTurmas": escopo["idTurmas"],
            "turmas": None,
        }

        ues_expandidas: list[dict] = []
        if (
            expandir_ues
            and tipo_abrangencia in _TIPOS_ABRANGENCIA_QUE_EXPANDEM_UE
        ):
            ues_expandidas = self._expandir_ues(codigos["idUes"])
            payload["ues"] = ues_expandidas
        elif (
            expandir_ues
            and tipo_abrangencia in _TIPOS_ABRANGENCIA_DRE_DE_ID_DRES
        ):
            ues_expandidas = self._expandir_ues_da_dre(
                _sem_nulos(codigos["idDres"]), tipo_abrangencia
            )
            payload["ues"] = ues_expandidas
        if (
            expandir_dres
            and tipo_abrangencia in _TIPOS_ABRANGENCIA_QUE_EXPANDEM_DRE
        ):
            payload["dres"] = self._expandir_dres(
                _sem_nulos(codigos["idDres"]),
                ues_expandidas,
                tipo_abrangencia,
            )
        if (
            expandir_turmas
            and tipo_abrangencia in _TIPOS_ABRANGENCIA_QUE_EXPANDEM_TURMA
        ):
            payload["turmas"] = self._expandir_turmas(
                _sem_nulos(codigos["idTurmas"]), ano
            )

        return payload

    def usuarios_por_perfil(
        self,
        ue: str,
        dre: str | None,
        perfis: list[str],
    ) -> list[dict[str, Any]]:
        """Lista os usuarios lotados na UE, agrupados por login.

        Args:
            ue: Codigo da unidade educacional.
            dre: Codigo da DRE; None nao filtra.
            perfis: GUIDs dos perfis consultados.

        Returns:
            Um registro por usuario.

        Raises:
            httpx.HTTPError: Com `dre`, o Institucional falhou.
        """
        usuarios: dict[str, dict[str, Any]] = {}
        for registro in self._usuarios_por_perfil(ue, dre, perfis):
            atual = usuarios.setdefault(
                registro["usuario_rf"],
                {"usuarioRf": registro["usuario_rf"], "perfils": []},
            )
            atual["perfils"].append(
                {
                    "perfil": registro["perfil_guid"],
                    "ues": registro["ues"],
                }
            )
        return list(usuarios.values())

    def _ano_letivo(self) -> int:
        """Resolve o ano letivo default do ambiente.

        Returns:
            O valor de `ABRANGENCIA_ANO_LETIVO`, como inteiro.
        """
        return int(settings.ABRANGENCIA_ANO_LETIVO)

    def _aplicar_nivel_vazio(
        self,
        codigos: dict[str, Codigos],
        tipo_abrangencia: int | None,
        *,
        algoritmo_alternativo: bool,
        escopo_de_contrato_externo: bool = False,
        eh_perfil_manual: bool = False,
        grupo_codigo: int | None = None,
    ) -> dict[str, Codigos | None]:
        """Decide quais niveis o tipo de abrangencia projeta.

        Args:
            codigos: Codigos lidos da MV, por chave do payload.
            tipo_abrangencia: Tipo de abrangencia do perfil.
            algoritmo_alternativo: tipo_resolucao `DETALHES` e ignora
                o nivel de abrangencia que o perfil nao preenche.
            escopo_de_contrato_externo: Escopo resolvido pelo contrato
                externo, que nao chega a consulta de turmas do POA.
            eh_perfil_manual: Flag agregado do perfil.
            grupo_codigo: Codigo do grupo do perfil.

        Returns:
            Os tres niveis do payload, usando `[]` ou `None` conforme o
            tipo de abrangencia.
        """
        if algoritmo_alternativo:
            vazios = self._niveis_vazios_detalhes(tipo_abrangencia)
            if tipo_abrangencia is not None:
                return {
                    chave: (valor or []) if chave in vazios else None
                    for chave, valor in codigos.items()
                }
        else:
            vazios = self._niveis_vazios_compacta(
                tipo_abrangencia,
                escopo_de_contrato_externo=escopo_de_contrato_externo,
                eh_perfil_manual=eh_perfil_manual,
                grupo_codigo=grupo_codigo,
            )

        return {
            chave: self._nivel_projetado(valor, chave in vazios)
            for chave, valor in codigos.items()
        }

    def _nivel_projetado(
        self,
        codigos: Codigos,
        sai_vazio: bool,
    ) -> Codigos | None:
        """Escolhe entre `[]` e `None` para um nivel sem codigo.

        Args:
            codigos: Codigos do nivel.
            sai_vazio: Verdadeiro quando o nivel projeta `[]`.

        Returns:
            Os proprios codigos, ou `[]`/`None` quando nao ha nenhum.
        """
        if codigos:
            return codigos
        return [] if sai_vazio else None

    def _niveis_vazios_detalhes(
        self,
        tipo_abrangencia: int | None,
    ) -> frozenset[str]:
        """Lista os niveis que saem `[]` no `tipo_resolucao` DETALHES.

        Args:
            tipo_abrangencia: Tipo de abrangencia do perfil.

        Returns:
            As chaves do payload que o tipo de abrangencia projeta.
        """
        if tipo_abrangencia is None:
            return frozenset()
        return _NIVEIS_VAZIOS_DETALHES.get(tipo_abrangencia, frozenset())

    def _niveis_vazios_compacta(
        self,
        tipo_abrangencia: int | None,
        *,
        escopo_de_contrato_externo: bool,
        eh_perfil_manual: bool,
        grupo_codigo: int | None,
    ) -> frozenset[str]:
        """Lista os niveis que saem `[]` no `tipo_resolucao` COMPACTA.

        Args:
            tipo_abrangencia: Tipo de abrangencia do perfil.
            escopo_de_contrato_externo: Escopo resolvido pelo contrato
                externo, que nao chega a consulta de turmas do POA.
            eh_perfil_manual: Flag agregado do perfil.
            grupo_codigo: Codigo do grupo do perfil.

        Returns:
            As chaves do payload que saem `[]` quando nao ha codigo.
        """
        if tipo_abrangencia is None:
            return frozenset()

        vazios = _NIVEIS_VAZIOS_POR_TIPO_ABRANGENCIA.get(
            tipo_abrangencia, frozenset()
        )
        if (
            tipo_abrangencia == TipoAbrangencia.UE_TURMAS_DISCIPLINAS
            and not escopo_de_contrato_externo
        ):
            vazios = vazios | {"idTurmas"}
        if tipo_abrangencia == TipoAbrangencia.DRE and not eh_perfil_manual:
            vazios = vazios | _NIVEIS_VAZIOS_DRE_NAO_MANUAL
        if not escopo_de_contrato_externo and self._e07_ue_mantem_nulo(
            tipo_abrangencia,
            eh_perfil_manual=eh_perfil_manual,
            grupo_codigo=grupo_codigo,
        ):
            vazios = vazios - {"idUes"}
        return vazios

    def _e07_ue_mantem_nulo(
        self,
        tipo_abrangencia: int | None,
        *,
        eh_perfil_manual: bool,
        grupo_codigo: int | None,
    ) -> bool:
        """Informa se `idUes` vazio sai `null` no tipo de abrangencia UE.

        Args:
            tipo_abrangencia: Abrangencia do perfil.
            eh_perfil_manual: Flag agregado do perfil.
            grupo_codigo: Grupo do perfil.

        Returns:
            Verdadeiro para tipo UE com perfil manual ou do grupo de
            comunicados da UE.
        """
        if tipo_abrangencia not in (
            TipoAbrangencia.UE,
            TipoAbrangencia.UE_TURMAS_DISCIPLINAS,
        ):
            return False
        return eh_perfil_manual or grupo_codigo == GRUPO_COMUNICADOS_UE

    def _limitar_dre_unica(
        self,
        codigos: dict[str, Codigos],
    ) -> dict[str, Codigos]:
        """Reduz `idDres` a uma unica DRE em `DETALHES`.

        Args:
            codigos: Codigos lidos da MV, por chave do payload.

        Returns:
            Os mesmos codigos, com `idDres` reduzida a no maximo um.
        """
        return {**codigos, "idDres": codigos["idDres"][:1]}

    def _escopo_resolvido(
        self,
        login: str,
        perfil_guid: str,
        ano_letivo: int,
        tipo_resolucao: str,
    ) -> dict[str, Codigos]:
        """Agrupa as linhas de escopo da MV nas tres listas do payload.

        Args:
            login: RF ou CPF do usuario.
            perfil_guid: GUID do perfil consultado.
            ano_letivo: Ano letivo do escopo.
            tipo_resolucao: `COMPACTA` ou `DETALHES`.

        Returns:
            `idDres`, `idUes` e `idTurmas`, cada uma ordenada e sem
            repeticao. Nivel sem linha na MV sai `[]`.
        """
        linhas = AbrangenciaResolvida.objects.filter(
            login=login,
            perfil_guid=perfil_guid,
            ano_letivo=ano_letivo,
            tipo_resolucao=tipo_resolucao,
        ).values_list("dre_codigo", "ue_codigo", "turma_codigo", "origem")

        acumulado: dict[str, set[str | None]] = {
            "idDres": set(),
            "idUes": set(),
            "idTurmas": set(),
        }
        for dre, ue, turma, origem in linhas:
            if turma:
                acumulado["idTurmas"].add(str(turma))
            elif ue:
                acumulado["idUes"].add(str(ue))
            elif dre:
                acumulado["idDres"].add(str(dre))
            elif origem in ORIGENS_UE_POR_EXERCICIO:
                acumulado["idUes"].add(None)

        return {
            chave: self._ordenar_codigos(valor)
            for chave, valor in acumulado.items()
        }

    def _ordenar_codigos(self, codigos: set[str | None]) -> Codigos:
        """Ordena os codigos de um nivel, com o nulo a frente.

        Args:
            codigos: Codigos do nivel, possivelmente com um nulo.

        Returns:
            Os codigos ordenados, com o nulo a frente quando houver.
        """
        presentes = sorted(codigo for codigo in codigos if codigo is not None)
        ordenados: Codigos = [*presentes]
        if None in codigos:
            ordenados.insert(0, None)
        return ordenados

    def _escopo_veio_de_contrato_externo(
        self,
        login: str,
        perfil_guid: str,
        ano_letivo: int,
    ) -> bool:
        """Informa se o escopo compacto veio do contrato externo.

        Args:
            login: RF ou CPF do usuario.
            perfil_guid: GUID do perfil consultado.
            ano_letivo: Ano letivo do escopo.

        Returns:
            Verdadeiro quando ha linha de contrato externo no escopo
            compacto do par.
        """
        return bool(
            AbrangenciaResolvida.objects.filter(
                login=login,
                perfil_guid=perfil_guid,
                ano_letivo=ano_letivo,
                tipo_resolucao=TIPO_RESOLUCAO_COMPACTA,
                origem=_ORIGEM_CONTRATO_EXTERNO,
            ).exists()
        )

    def _expandir_ues(self, id_ues: Codigos) -> list[dict]:
        """Monta a lista expandida de UEs.

        Args:
            id_ues: UEs do escopo; vazio traz a rede inteira.

        Returns:
            Uma entrada por UE da rede, ordenada por codigo. UE fora da rede
            fica so no identificador, como num LEFT JOIN.

        Raises:
            httpx.HTTPError: Um MS falhou.
            RedeSmeIncompletaError: A rede SME veio incompleta.
            ImproperlyConfigured: Sem `tipos_escola_exibidos` no ano.
        """
        pedidas = _sem_nulos(id_ues) or sorted(self._rede_sme.ues())
        ues = self._rede_sme.atributos_ues(pedidas)
        return [_ue_expandida(codigo, ues[codigo]) for codigo in sorted(ues)]

    def _expandir_ues_da_dre(
        self,
        id_dres: list[str],
        tipo_abrangencia: int | None,
    ) -> list[dict]:
        """Monta a lista de UEs dos tipos de abrangencia que resolvem DRE.

        Args:
            id_dres: DREs do escopo, usadas como filtro.
            tipo_abrangencia: Abrangencia do perfil.

        Returns:
            Uma entrada por UE da rede cujo pai esta em `id_dres`, ou a
            rede inteira no tipo de abrangencia SME.

        Raises:
            httpx.HTTPError: Um MS falhou.
            RedeSmeIncompletaError: A rede SME veio incompleta.
            ImproperlyConfigured: Sem `tipos_escola_exibidos` no ano.
        """
        ues = self._rede_sme.atributos_ues(sorted(self._rede_sme.ues()))
        dres = set(id_dres)
        return [
            _ue_expandida(codigo, ues[codigo])
            for codigo in sorted(ues)
            if tipo_abrangencia == TipoAbrangencia.SME
            or ues[codigo]["dre_codigo"] in dres
        ]

    def _expandir_dres(
        self,
        id_dres: list[str],
        ues_expandidas: list[dict],
        tipo_abrangencia: int | None,
    ) -> list[dict]:
        """Monta a lista expandida de DREs.

        Args:
            id_dres: DREs do escopo.
            ues_expandidas: UEs ja expandidas, de que a lista deriva
                nos tipos de abrangencia 1 e 5.
            tipo_abrangencia: Abrangencia do perfil.

        Returns:
            Uma entrada por DRE encontrada no Institucional, ordenada por
            codigo.

        Raises:
            httpx.HTTPError: O Institucional falhou.
        """
        if tipo_abrangencia in _TIPOS_ABRANGENCIA_DRE_DERIVADA_DE_UE:
            codigos = sorted(
                {ue["codigoDRE"] for ue in ues_expandidas if ue["codigoDRE"]}
            )
        else:
            codigos = sorted(set(id_dres))

        dres = self._rede_sme.atributos_dres(codigos)
        return [
            {
                "codigoDRE": codigo,
                "nomeDRE": dres[codigo]["nome"],
                "siglaDRE": dres[codigo]["sigla"],
            }
            for codigo in sorted(dres)
        ]

    def _expandir_turmas(
        self,
        id_turmas: list[str],
        ano_letivo: int,
    ) -> list[dict]:
        """Monta a lista expandida de turmas, restrita a sondagem.

        Args:
            id_turmas: Turmas do escopo; vazio traz as turmas de sondagem
                da rede.
            ano_letivo: Ano letivo do escopo.

        Returns:
            Turmas elegiveis, ordenadas por codigo. Sem nenhuma
            elegivel, a lista vazia.

        Raises:
            httpx.HTTPError: Um MS falhou.
            RedeSmeIncompletaError: A rede SME veio incompleta.
            ImproperlyConfigured: Sem `tipos_escola_exibidos` no ano.
        """
        turmas = (
            self._rede_sme.turmas(id_turmas, ano_letivo, sondagem=True)
            if id_turmas
            else self._rede_sme.turmas_de_sondagem(ano_letivo)
        )
        return [
            {
                "codigo": codigo,
                "nome": turmas[codigo]["nome"],
                "codigoEscola": turmas[codigo]["ue_codigo"],
            }
            for codigo in sorted(turmas)
        ]

    def _perfil_com_vinculos(
        self,
        perfil_guid: str,
        *,
        funcao_exige_cargo: bool = True,
    ) -> dict | None:
        """Retorna o perfil com seus cargos e funcoes-atividade.

        Args:
            perfil_guid: GUID do perfil consultado.
            funcao_exige_cargo: Quando verdadeiro, perfil sem cargo sai
                sem funcao.

        Returns:
            Dados do perfil com cargos e funcoes ordenados, ou None
            quando o perfil nao existe. Perfil sem vinculo funcional
            devolve as duas listas vazias.
        """
        perfil = (
            Perfil.objects.filter(perfil_guid=perfil_guid)
            .values(
                "perfil_guid",
                "grupo_codigo",
                "abrangencia_id",
                "eh_perfil_manual",
                "eh_grupo_manual",
            )
            .first()
        )
        if perfil is None:
            return None

        vinculos = PerfilVinculoFuncional.objects.filter(
            perfil_guid=perfil_guid
        ).values_list("tipo", "codigo")

        cargos = sorted(
            {codigo for tipo, codigo in vinculos if tipo == _TIPO_CARGO}
        )
        funcoes = (
            sorted(
                {
                    codigo
                    for tipo, codigo in vinculos
                    if tipo == _TIPO_FUNCAO_ATIVIDADE
                }
            )
            if cargos or not funcao_exige_cargo
            else []
        )
        return {**perfil, "cargos": cargos, "funcoes": funcoes}

    def _manual_do_perfil(
        self,
        perfil: Mapping[str, Any],
        *,
        eh_grupo_manual: bool,
    ) -> bool:
        """Resolve `ehPerfilManual` pelo repositorio que o endpoint usa.

        Args:
            perfil: Linha de `public.perfil` ja lida.
            eh_grupo_manual: Verdadeiro para o caminho da linha.

        Returns:
            O valor de `ehPerfilManual` do caminho pedido.
        """
        coluna = "eh_grupo_manual" if eh_grupo_manual else "eh_perfil_manual"
        return bool(perfil[coluna])

    def _tipo_abrangencia_do_perfil(
        self, perfil_guid: str
    ) -> tuple[int | None, bool, int | None]:
        """Retorna tipo de abrangencia, flag manual e grupo.

        Args:
            perfil_guid: GUID do perfil consultado.

        Returns:
            `abrangencia_id`, `eh_perfil_manual` (o flag agregado) e
            `grupo_codigo`; `(None, False, None)` quando o perfil nao
            existe.
        """
        perfil = (
            Perfil.objects.filter(perfil_guid=perfil_guid)
            .values("abrangencia_id", "eh_perfil_manual", "grupo_codigo")
            .first()
        )
        if perfil is None:
            return None, False, None
        return (
            perfil["abrangencia_id"],
            bool(perfil["eh_perfil_manual"]),
            perfil["grupo_codigo"],
        )

    def _usuarios_por_perfil(
        self,
        ue: str,
        dre: str | None,
        perfis: list[str],
    ) -> list[dict]:
        """Seleciona usuarios pelo filtro e retorna todos os perfis deles.

        Args:
            ue: Codigo da UE em que o usuario precisa estar lotado.
            dre: Codigo da DRE; exige lotacao em alguma UE dela. None
                nao filtra.
            perfis: GUIDs dos perfis consultados na UE.

        Returns:
            Um registro por par `(login, perfil)`, com as UEs ordenadas.

        Raises:
            httpx.HTTPError: Com `dre`, o Institucional falhou.
        """
        base = UsuarioPorPerfil.objects.filter(ano_letivo=self._ano_letivo())
        selecao = base.filter(ue_codigo=ue, perfil_guid__in=perfis)
        if dre:
            ues_da_dre = sorted(self._rede_sme.unidades_da_dre(dre))
            selecao = selecao.filter(
                usuario_rf__in=base.filter(ue_codigo__in=ues_da_dre).values(
                    "usuario_rf"
                )
            )

        logins = set(selecao.values_list("usuario_rf", flat=True))
        if not logins:
            return []

        agrupado: dict[tuple[str, str], set[str]] = {}
        completa = base.filter(usuario_rf__in=logins)
        for login, perfil_guid, ue_codigo in completa.values_list(
            "usuario_rf", "perfil_guid", "ue_codigo"
        ):
            ues = agrupado.setdefault((login, str(perfil_guid)), set())
            if ue_codigo:
                ues.add(str(ue_codigo))

        return [
            {
                "usuario_rf": login,
                "perfil_guid": perfil_guid,
                "ues": sorted(ues),
            }
            for (login, perfil_guid), ues in sorted(agrupado.items())
        ]


def _ue_expandida(codigo: str, ue: Mapping[str, Any]) -> dict[str, Any]:
    """Monta a entrada de `ues[]` com as chaves do contrato.

    Args:
        codigo: Codigo EOL da UE.
        ue: Atributos da UE vindos da rede SME.

    Returns:
        `codigo`, `codigoDRE`, `nome` e `sigla`.
    """
    return {
        "codigo": codigo,
        "codigoDRE": ue["dre_codigo"],
        "nome": ue["nome"],
        "sigla": ue["sigla"],
    }
