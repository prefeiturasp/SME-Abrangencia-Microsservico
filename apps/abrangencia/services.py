"""Servicos do dominio Abrangencia."""

from collections.abc import Mapping
from typing import Any

from django.conf import settings

from apps.abrangencia.constants import (
    GRUPO_COMUNICADOS_UE,
    ORIGENS_UE_POR_EXERCICIO,
    TIPO_ESCOPO_DRE,
    TIPO_ESCOPO_TURMA,
    TIPO_ESCOPO_UE,
    TIPO_RESOLUCAO_COMPACTA,
    TIPO_RESOLUCAO_DETALHES,
    TipoAbrangencia,
)
from apps.abrangencia.models import (
    AbrangenciaResolvida,
    Perfil,
    PerfilVinculoFuncional,
    Unidade,
    UsuarioPorPerfil,
)

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


_ESCOPO_POR_TIPO: dict[str, tuple[str, int]] = {
    TIPO_ESCOPO_DRE: ("idDres", 0),
    TIPO_ESCOPO_UE: ("idUes", 1),
    TIPO_ESCOPO_TURMA: ("idTurmas", 2),
}

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
                sem funcao  ver `_perfil_com_vinculos`.
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
            "abrangencia": perfil["tipo_abrangencia"],
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
            dres_da_rede: Codigos = list(self._dres_da_rede(ano))
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
            ues_expandidas = self._expandir_ues(codigos["idUes"], ano)
            payload["ues"] = ues_expandidas
        elif (
            expandir_ues
            and tipo_abrangencia in _TIPOS_ABRANGENCIA_DRE_DE_ID_DRES
        ):
            ues_expandidas = self._expandir_ues_da_dre(
                _sem_nulos(codigos["idDres"]), tipo_abrangencia, ano
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
                ano,
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
            Um registro por usuario. A chave `perfils` (sem o "i") segue
            a grafia do contrato consumido pelos sistemas integrados.
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
            `ABRANGENCIA_ANO_LETIVO`, com fallback para o ano corrente.
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
        mapa = (
            _NIVEIS_VAZIOS_DETALHES
            if algoritmo_alternativo
            else _NIVEIS_VAZIOS_POR_TIPO_ABRANGENCIA
        )
        vazios: frozenset[str] = (
            frozenset()
            if tipo_abrangencia is None
            else mapa.get(tipo_abrangencia, frozenset())
        )
        if (
            not algoritmo_alternativo
            and tipo_abrangencia == TipoAbrangencia.UE_TURMAS_DISCIPLINAS
            and not escopo_de_contrato_externo
        ):
            vazios = vazios | {"idTurmas"}
        if (
            not algoritmo_alternativo
            and tipo_abrangencia == TipoAbrangencia.DRE
            and not eh_perfil_manual
        ):
            vazios = vazios | _NIVEIS_VAZIOS_DRE_NAO_MANUAL
        if (
            not algoritmo_alternativo
            and not escopo_de_contrato_externo
            and self._e07_ue_mantem_nulo(
                tipo_abrangencia,
                eh_perfil_manual=eh_perfil_manual,
                grupo_codigo=grupo_codigo,
            )
        ):
            vazios = vazios - {"idUes"}

        if algoritmo_alternativo and tipo_abrangencia is not None:
            return {
                chave: (valor or []) if chave in vazios else None
                for chave, valor in codigos.items()
            }

        return {
            chave: valor if valor else ([] if chave in vazios else None)
            for chave, valor in codigos.items()
        }

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
            grupo_codigo: Grupo do perfil, que a guarda de 241 cita.

        Returns:
            Verdadeiro quando o tipo de abrangencia e o grupo mantem
            o `null` de 233.
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
        ).values_list(
            "tipo_escopo",
            "dre_codigo",
            "ue_codigo",
            "turma_codigo",
            "origem",
        )

        acumulado: dict[str, set[str | None]] = {
            chave: set() for chave, _ in _ESCOPO_POR_TIPO.values()
        }
        for tipo_escopo, *valores, origem in linhas:
            destino = _ESCOPO_POR_TIPO.get(tipo_escopo)
            if destino is None:
                continue
            chave, posicao = destino
            codigo = valores[posicao]
            if codigo:
                acumulado[chave].add(str(codigo))
            elif (
                chave == "idUes"
                and codigo is None
                and origem in ORIGENS_UE_POR_EXERCICIO
            ):
                acumulado[chave].add(None)

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

    def _dres_da_rede(self, ano_letivo: int) -> list[str]:
        """Lista as DREs da rede para o tipo SME sem linha na MV.

        Args:
            ano_letivo: Ano letivo do escopo.

        Returns:
            Codigos das DREs da rede, ordenados.
        """
        return sorted(self._unidades(TIPO_ESCOPO_DRE, None, ano_letivo))

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

    def _unidades(
        self,
        tipo_escopo: str,
        codigos: list[str] | None,
        ano_letivo: int,
        *,
        somente_sondagem: bool = False,
    ) -> dict[str, Mapping[str, Any]]:
        """Le nome, sigla e pai das unidades da rede, filtradas ou nao.

        Args:
            tipo_escopo: `DRE`, `UE` ou `TURMA`.
            codigos: Codigos a resolver. `None` nao filtra (rede inteira);
                lista vazia devolve mapa vazio.
            ano_letivo: Ano letivo do escopo.
            somente_sondagem: Restringe a unidades elegiveis a sondagem.

        Returns:
            Mapa `codigo -> atributos`. Codigo sem par na MV simplesmente
            nao aparece, e e o que faz a expansao se comportar como um
            LEFT JOIN.
        """
        if codigos is not None and not codigos:
            return {}

        consulta = Unidade.objects.filter(
            ano_letivo=ano_letivo,
            tipo_escopo=tipo_escopo,
        )
        if codigos is not None:
            consulta = consulta.filter(codigo__in=codigos)
        if somente_sondagem:
            consulta = consulta.filter(elegivel_sondagem=True)

        return {
            str(linha["codigo"]): linha
            for linha in consulta.values(
                "codigo", "nome", "sigla", "dre_codigo_pai", "ue_codigo_pai"
            )
        }

    def _expandir_ues(
        self,
        id_ues: Codigos,
        ano_letivo: int,
    ) -> list[dict]:
        """Monta a lista expandida de UEs.

        Args:
            id_ues: UEs do escopo; vazio traz a rede inteira.
            ano_letivo: Ano letivo do escopo.

        Returns:
            Uma entrada por UE com par na MV de unidade, ordenada por
            codigo.
        """
        codigos = _sem_nulos(id_ues)
        unidades = self._unidades(TIPO_ESCOPO_UE, codigos or None, ano_letivo)
        return [
            {
                "codigo": codigo,
                "codigoDRE": unidades[codigo]["dre_codigo_pai"],
                "nome": unidades[codigo]["nome"],
                "sigla": unidades[codigo]["sigla"],
            }
            for codigo in sorted(unidades)
        ]

    def _expandir_ues_da_dre(
        self,
        id_dres: list[str],
        tipo_abrangencia: int | None,
        ano_letivo: int,
    ) -> list[dict]:
        """Monta a lista de UEs dos tipos de abrangencia que resolvem DRE.

        Args:
            id_dres: DREs do escopo, usadas como filtro.
            tipo_abrangencia: Abrangencia do perfil.
            ano_letivo: Ano letivo do escopo.

        Returns:
            Uma entrada por UE da rede cujo pai esta em `id_dres`, ou a
            rede inteira no tipo de abrangencia SME.
        """
        unidades = self._unidades(TIPO_ESCOPO_UE, None, ano_letivo)
        dres = set(id_dres or ())
        return [
            {
                "codigo": codigo,
                "codigoDRE": unidades[codigo]["dre_codigo_pai"],
                "nome": unidades[codigo]["nome"],
                "sigla": unidades[codigo]["sigla"],
            }
            for codigo in sorted(unidades)
            if tipo_abrangencia == TipoAbrangencia.SME
            or unidades[codigo]["dre_codigo_pai"] in dres
        ]

    def _expandir_dres(
        self,
        id_dres: list[str],
        ues_expandidas: list[dict],
        tipo_abrangencia: int | None,
        ano_letivo: int,
    ) -> list[dict]:
        """Monta a lista expandida de DREs.

        Args:
            id_dres: DREs do escopo.
            ues_expandidas: UEs ja expandidas, de que a lista deriva
                nos tipos de abrangencia 1 e 5.
            tipo_abrangencia: Abrangencia do perfil.
            ano_letivo: Ano letivo do escopo.

        Returns:
            Uma entrada por DRE com par na MV de unidade, ordenada por
            codigo.
        """
        if tipo_abrangencia in _TIPOS_ABRANGENCIA_DRE_DERIVADA_DE_UE:
            codigos = sorted(
                {ue["codigoDRE"] for ue in ues_expandidas if ue["codigoDRE"]}
            )
        else:
            codigos = sorted(set(id_dres))

        unidades = self._unidades(TIPO_ESCOPO_DRE, codigos, ano_letivo)
        return [
            {
                "codigoDRE": codigo,
                "nomeDRE": unidades[codigo]["nome"],
                "siglaDRE": unidades[codigo]["sigla"],
            }
            for codigo in sorted(unidades)
        ]

    def _expandir_turmas(
        self,
        id_turmas: list[str],
        ano_letivo: int,
    ) -> list[dict]:
        """Monta a lista expandida de turmas, restrita a sondagem.

        Args:
            id_turmas: Turmas do escopo; vazio traz a rede inteira.
            ano_letivo: Ano letivo do escopo.

        Returns:
            Turmas elegiveis, ordenadas por codigo. Sem nenhuma
            elegivel, a lista vazia.
        """
        unidades = self._unidades(
            TIPO_ESCOPO_TURMA,
            id_turmas or None,
            ano_letivo,
            somente_sondagem=True,
        )
        turmas = [
            {
                "codigo": codigo,
                "nome": unidades[codigo]["nome"],
                "codigoEscola": unidades[codigo]["ue_codigo_pai"],
            }
            for codigo in sorted(unidades)
        ]
        return turmas

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
                "tipo_abrangencia",
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
            `tipo_abrangencia`  None quando o perfil nao existe,
            `eh_perfil_manual`, o flag agregado e `grupo_codigo`.
        """
        perfil = (
            Perfil.objects.filter(perfil_guid=perfil_guid)
            .values("tipo_abrangencia", "eh_perfil_manual", "grupo_codigo")
            .first()
        )
        if perfil is None:
            return None, False, None
        return (
            perfil["tipo_abrangencia"],
            bool(perfil["eh_perfil_manual"]),
            perfil["grupo_codigo"],
        )

    def _usuarios_por_perfil(
        self,
        ue: str,
        dre: str | None,
        perfis: list[str],
    ) -> list[dict]:
        """Seleciona usuarios pelo filtro e projeta todos os perfis possuidos.

        Returns:
            Um registro por par `(login, perfil)`, com as UEs ordenadas.
        """
        base = UsuarioPorPerfil.objects.filter(ano_letivo=self._ano_letivo())
        selecao = base.filter(ue_codigo=ue, perfil_guid__in=perfis)
        if dre:
            selecao = selecao.filter(
                usuario_rf__in=base.filter(dre_codigo=dre).values("usuario_rf")
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
