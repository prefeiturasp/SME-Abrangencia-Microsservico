"""Serviços do domínio Abrangência."""

from typing import Any

from django.conf import settings

from apps.abrangencia.constants import (
    GRUPO_PROFESSOR_READAPTADO,
    ORIGENS_LOTACAO,
    PERFIS_POA,
    TipoAbrangencia,
)
from apps.abrangencia.models import (
    AbrangenciaCompacta,
    Perfil,
    PerfilVinculoFuncional,
    UsuarioAbrangencia,
)

# Nível fora do conjunto do ramo é zerado. `DRE_ESCOLAS_ATRIBUIDAS` fica
# de fora de propósito: sem entrada aqui, os três níveis saem zerados.
ESCOPO_POR_ABRANGENCIA: dict[int, frozenset[str]] = {
    TipoAbrangencia.UE: frozenset({"idUes"}),
    TipoAbrangencia.PROFESSOR: frozenset({"idTurmas"}),
    TipoAbrangencia.UE_TURMAS_DISCIPLINAS: frozenset({"idUes"}),
    TipoAbrangencia.DRE: frozenset({"idDres"}),
    TipoAbrangencia.SME: frozenset({"idDres", "idUes", "idTurmas"}),
}

# Difere de ESCOPO_POR_ABRANGENCIA só em UE_TURMAS_DISCIPLINAS: aqui o
# ramo preenche idTurmas em vez de idUes.
ESCOPO_POR_ABRANGENCIA_ALTERNATIVO: dict[int, frozenset[str]] = {
    **ESCOPO_POR_ABRANGENCIA,
    TipoAbrangencia.UE_TURMAS_DISCIPLINAS: frozenset({"idTurmas"}),
}

# Ramos cujo nível não resolvido vira `[]` em vez de `None`.
RAMOS_COM_ENTIDADE_VIGENTE: frozenset[int] = frozenset(
    {TipoAbrangencia.PROFESSOR, TipoAbrangencia.SME}
)

# Ramos em que a coleção expandida de DREs deriva das UEs detalhadas, e não
# diretamente de `id_dres`.
_RAMOS_DRE_DERIVADA_DE_UE = frozenset(
    {TipoAbrangencia.UE, TipoAbrangencia.UE_TURMAS_DISCIPLINAS}
)

# Traz as colunas dos dois algoritmos (padrão e `_alternativo`); qual
# delas é usada se decide em `_escopo_bruto`.
_CAMPOS_ESCOPO = (
    "id_dres",
    "id_ues",
    "id_turmas",
    "tipo_abrangencia",
    "id_ues_exercicio",
    "id_turmas_poa",
    "id_ues_alternativo",
    "id_turmas_alternativo",
    "grupo_codigo",
    "id_ues_readaptado",
    "id_ues_detalhaveis",
)

_TIPO_CARGO = "CARGO"
_TIPO_FUNCAO_ATIVIDADE = "FUNCAO_ATIVIDADE"


def _lista(valor: list[str] | None) -> list[str]:
    """Normaliza array da MV em lista, tratando NULL como vazio.

    Args:
        valor: Array lido da MV, ou None.

    Returns:
        A lista original, ou lista vazia quando `valor` é None.
    """
    return list(valor or [])


class AbrangenciaService:
    """Serviço responsável pelas operações do domínio Abrangência."""

    def grupo_cargos(self, perfil_guid: str) -> dict | None:
        """Monta o payload de perfil com seus cargos e funções.

        Ponto único de montagem, reaproveitado por `abrangencia_compacta`.

        Args:
            perfil_guid: GUID do perfil consultado.

        Returns:
            Payload do perfil, ou None quando ele não existe.
        """
        perfil = self._perfil_com_vinculos(perfil_guid)
        if perfil is None:
            return None
        return {
            "grupoID": str(perfil["perfil_guid"]),
            "cargosId": perfil["cargos"],
            "funcoesId": perfil["funcoes"],
            "grupo": perfil["grupo_codigo"],
            "abrangencia": perfil["tipo_abrangencia"],
            "ehPerfilManual": bool(perfil["eh_perfil_manual"]),
        }

    def projetar_escopo(
        self,
        tipo_abrangencia: int | None,
        perfil_guid: str,
        id_dres: list[str],
        id_ues: list[str],
        id_turmas: list[str],
        id_turmas_poa: list[str] | None = None,
        *,
        algoritmo_alternativo: bool = False,
    ) -> dict[str, list[str] | None]:
        """Projeta o escopo agregado da MV no ramo do perfil.

        Cada perfil só enxerga o subconjunto de níveis do seu
        `TipoAbrangencia`; servir o agregado bruto daria acesso a mais
        do que o perfil tem.

        Args:
            tipo_abrangencia: Ramo do perfil.
            perfil_guid: GUID do perfil, para a exceção dos perfis POA.
            id_dres: DREs agregadas na MV.
            id_ues: UEs agregadas na MV.
            id_turmas: Turmas agregadas na MV.
            id_turmas_poa: Turmas da origem POA, usadas só na exceção dos
                perfis POA no ramo UE.
            algoritmo_alternativo: Usa a projeção alternativa, em que o
                ramo `UE_TURMAS_DISCIPLINAS` resolve turma em vez de UE.

        Returns:
            `idDres`, `idUes` e `idTurmas` projetados. O nível não
            resolvido sai `[]` para Professor e SME, `None` nos demais.
        """
        mapa = (
            ESCOPO_POR_ABRANGENCIA_ALTERNATIVO
            if algoritmo_alternativo
            else ESCOPO_POR_ABRANGENCIA
        )
        preenchidos: frozenset[str] = (
            frozenset()
            if tipo_abrangencia is None
            else mapa.get(tipo_abrangencia, frozenset())
        )
        vazio: list[str] | None = (
            [] if tipo_abrangencia in RAMOS_COM_ENTIDADE_VIGENTE else None
        )

        disponiveis: dict[str, list[str]] = {
            "idDres": id_dres,
            "idUes": id_ues,
            "idTurmas": id_turmas,
        }
        escopo: dict[str, list[str] | None] = {
            campo: valor if campo in preenchidos else vazio
            for campo, valor in disponiveis.items()
        }

        # Perfis POA no ramo UE preenchem idTurmas só pela origem POA;
        # id_turmas agrega outras origens e traria turmas fora do
        # alcance do perfil. Vale só para o algoritmo padrão.
        if (
            not algoritmo_alternativo
            and tipo_abrangencia
            in (
                TipoAbrangencia.UE,
                TipoAbrangencia.UE_TURMAS_DISCIPLINAS,
            )
            and perfil_guid.lower() in PERFIS_POA
        ):
            escopo["idTurmas"] = list(id_turmas_poa or [])

        return escopo

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
        """Monta o payload de escopo compacto de um usuário em um perfil.

        Ponto único de montagem para os quatro endpoints de escopo
        compacto, que diferem só em quais coleções expandem e em qual
        algoritmo usam.

        Args:
            login: RF ou CPF do usuário.
            perfil_guid: GUID do perfil consultado.
            ano_letivo: Ano letivo; None usa `ABRANGENCIA_ANO_LETIVO`.
            expandir_dres: Preenche `dres`.
            expandir_ues: Preenche `ues`.
            expandir_turmas: Preenche `turmas`, restritas a sondagem.
            algoritmo_alternativo: Lê o escopo pelo algoritmo alternativo
                de agregação, em vez do padrão.

        Returns:
            Payload com as oito chaves do contrato, sempre presentes.
            Campo não expandido sai `None`, nunca `[]`.
        """
        ano = ano_letivo if ano_letivo is not None else self._ano_letivo()
        linha = self._escopo_compacto(login, perfil_guid, ano)

        escopo_bruto = self._escopo_bruto(
            linha, algoritmo_alternativo=algoritmo_alternativo
        )

        # Sem linha na MV o usuário não tem escopo, mas o tipo de
        # abrangência do perfil ainda decide se os campos saem `[]` ou
        # `None` — por isso vem do perfil quando a MV não o fornece.
        tipo_abrangencia = (
            linha["tipo_abrangencia"]
            if linha is not None
            else self._tipo_abrangencia_do_perfil(perfil_guid)
        )

        escopo = self.projetar_escopo(
            tipo_abrangencia,
            perfil_guid,
            escopo_bruto["id_dres"],
            escopo_bruto["id_ues"],
            escopo_bruto["id_turmas"],
            escopo_bruto["id_turmas_poa"],
            algoritmo_alternativo=algoritmo_alternativo,
        )

        payload: dict[str, Any] = {
            "login": login,
            "abrangencia": self.grupo_cargos(perfil_guid),
            "idDres": escopo["idDres"],
            "dres": None,
            "idUes": escopo["idUes"],
            "ues": None,
            "idTurmas": escopo["idTurmas"],
            "turmas": None,
        }

        # As coleções expandidas vêm do escopo bruto, não do já
        # projetado — por isso um identificador pode sair `null` e sua
        # coleção expandida vir preenchida no mesmo payload.
        id_ues_detalhaveis = escopo_bruto["id_ues_detalhaveis"]
        if expandir_ues:
            payload["ues"] = self._expandir_ues(id_ues_detalhaveis)
        if expandir_dres:
            payload["dres"] = self._expandir_dres(
                escopo_bruto["id_dres"],
                id_ues_detalhaveis,
                tipo_abrangencia,
                expandir_ues=expandir_ues,
            )
        if expandir_turmas:
            payload["turmas"] = self._expandir_turmas(login, perfil_guid, ano)

        return payload

    def usuarios_por_perfil(
        self,
        ue: str,
        dre: str | None,
        perfis: list[str],
    ) -> list[dict[str, Any]]:
        """Lista os usuários lotados na UE, agrupados por login.

        Args:
            ue: Código da unidade educacional.
            dre: Código da DRE; None não filtra.
            perfis: GUIDs dos perfis consultados.

        Returns:
            Um registro por usuário. A chave `perfils` (sem o "i") segue
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

    def _escopo_bruto(
        self,
        linha: dict | None,
        *,
        algoritmo_alternativo: bool,
    ) -> dict[str, list[str]]:
        """Seleciona as colunas de escopo do algoritmo pedido.

        Args:
            linha: Escopo bruto da MV, ou None quando o usuário não tem
                linha.
            algoritmo_alternativo: Lê as colunas `_alternativo`.

        Returns:
            As listas de escopo a projetar, mais as UEs detalháveis para
            expansão.
        """
        if linha is None:
            return {
                "id_dres": [],
                "id_ues": [],
                "id_turmas": [],
                "id_turmas_poa": [],
                "id_ues_detalhaveis": [],
            }

        id_ues = linha["id_ues"]
        id_turmas = linha["id_turmas"]

        if algoritmo_alternativo:
            id_ues = linha["id_ues_alternativo"]
            id_turmas = linha["id_turmas_alternativo"]

            # É o grupo, não o TipoAbrangencia, que decide este desvio.
            if linha["grupo_codigo"] == GRUPO_PROFESSOR_READAPTADO:
                id_ues = linha["id_ues_readaptado"]
                id_turmas = []

        return {
            "id_dres": linha["id_dres"],
            "id_ues": id_ues,
            "id_turmas": id_turmas,
            "id_turmas_poa": linha["id_turmas_poa"],
            "id_ues_detalhaveis": linha["id_ues_detalhaveis"],
        }

    def _expandir_ues(self, id_ues_detalhaveis: list[str]) -> list[dict]:
        """Monta a coleção expandida de UEs.

        Args:
            id_ues_detalhaveis: UEs elegíveis para detalhamento.

        Returns:
            Uma entrada por UE, com `nome`/`sigla`/`codigoDRE` sempre
            `None` — este serviço guarda só o código.
        """
        return [
            {
                "codigo": codigo,
                "codigoDRE": None,
                "nome": None,
                "sigla": None,
            }
            for codigo in sorted(id_ues_detalhaveis)
        ]

    def _expandir_dres(
        self,
        id_dres: list[str],
        id_ues_detalhaveis: list[str],
        tipo_abrangencia: int | None,
        *,
        expandir_ues: bool,
    ) -> list[dict]:
        """Monta a coleção expandida de DREs.

        Nos ramos de `_RAMOS_DRE_DERIVADA_DE_UE`, sem UE detalhável a
        coleção sai vazia mesmo havendo DRE em `id_dres`.

        Args:
            id_dres: DREs agregadas na MV.
            id_ues_detalhaveis: UEs elegíveis para detalhamento.
            tipo_abrangencia: Ramo do perfil.
            expandir_ues: Se a expansão de UEs também foi pedida.

        Returns:
            Uma entrada por DRE, com `nomeDRE`/`siglaDRE` sempre `None`.
        """
        if expandir_ues and tipo_abrangencia in _RAMOS_DRE_DERIVADA_DE_UE:
            codigos = sorted(id_dres) if id_ues_detalhaveis else []
        else:
            codigos = sorted(id_dres)
        return [
            {"codigoDRE": codigo, "nomeDRE": None, "siglaDRE": None}
            for codigo in codigos
        ]

    def _expandir_turmas(
        self,
        login: str,
        perfil_guid: str,
        ano_letivo: int,
    ) -> list[dict] | None:
        """Monta a coleção expandida de turmas, restrita a sondagem.

        Args:
            login: RF ou CPF do usuário.
            perfil_guid: GUID do perfil consultado.
            ano_letivo: Ano letivo do escopo.

        Returns:
            Turmas com `nome` sempre `None` (guardamos só o código), ou
            `None` (não `[]`) quando não há turma elegível.
        """
        turmas = [
            {
                "codigo": turma["turma_codigo"],
                "nome": None,
                "codigoEscola": turma["ue_codigo"],
            }
            for turma in self._turmas_sondagem(login, perfil_guid, ano_letivo)
        ]
        return turmas or None

    def _perfil_com_vinculos(self, perfil_guid: str) -> dict | None:
        """Retorna o perfil com seus cargos e funções-atividade.

        Args:
            perfil_guid: GUID do perfil consultado.

        Returns:
            Dados do perfil com cargos e funções ordenados, ou None
            quando o perfil não existe. Perfil sem vínculo funcional
            devolve as duas listas vazias.
        """
        perfil = (
            Perfil.objects.filter(perfil_guid=perfil_guid)
            .values(
                "perfil_guid",
                "grupo_codigo",
                "tipo_abrangencia",
                "eh_perfil_manual",
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
        funcoes = sorted(
            {
                codigo
                for tipo, codigo in vinculos
                if tipo == _TIPO_FUNCAO_ATIVIDADE
            }
        )
        return {**perfil, "cargos": cargos, "funcoes": funcoes}

    def _escopo_compacto(
        self,
        login: str,
        perfil_guid: str,
        ano_letivo: int,
    ) -> dict | None:
        """Retorna o escopo agregado do usuário no perfil.

        Filtra pelo trio `(login, perfil, ano letivo)` — as colunas do
        índice único da MV.

        Args:
            login: RF ou CPF do usuário.
            perfil_guid: GUID do perfil consultado.
            ano_letivo: Ano letivo do escopo.

        Returns:
            Escopo bruto com os arrays normalizados em lista, ou None
            quando o usuário não tem linha na MV.
        """
        linha = (
            AbrangenciaCompacta.objects.filter(
                login=login,
                perfil_guid=perfil_guid,
                ano_letivo=ano_letivo,
            )
            .values(*_CAMPOS_ESCOPO)
            .first()
        )
        if linha is None:
            return None
        return {
            campo: _lista(valor) if campo.startswith("id_") else valor
            for campo, valor in linha.items()
        }

    def _tipo_abrangencia_do_perfil(self, perfil_guid: str) -> int | None:
        """Retorna o ramo de abrangência de um perfil.

        Usada como fallback em `abrangencia_compacta` quando o usuário
        não tem linha na MV.

        Args:
            perfil_guid: GUID do perfil consultado.

        Returns:
            Valor de `tipo_abrangencia`, ou None quando o perfil não
            existe.
        """
        return (
            Perfil.objects.filter(perfil_guid=perfil_guid)
            .values_list("tipo_abrangencia", flat=True)
            .first()
        )

    def _turmas_sondagem(
        self,
        login: str,
        perfil_guid: str,
        ano_letivo: int,
    ) -> list[dict]:
        """Lista as turmas distintas do usuário elegíveis a sondagem.

        Args:
            login: RF ou CPF do usuário.
            perfil_guid: GUID do perfil consultado.
            ano_letivo: Ano letivo do escopo.

        Returns:
            Turmas com seu código e o da escola, ordenadas por código
            de turma.
        """
        linhas = (
            UsuarioAbrangencia.objects.filter(
                login=login,
                perfil_guid=perfil_guid,
                ano_letivo=ano_letivo,
                vigente=True,
                elegivel_sondagem=True,
                turma_codigo__isnull=False,
            )
            .values_list("turma_codigo", "ue_codigo")
            .distinct()
        )
        return [
            {"turma_codigo": turma, "ue_codigo": ue}
            for turma, ue in sorted(set(linhas))
        ]

    def _usuarios_por_perfil(
        self,
        ue: str,
        dre: str | None,
        perfis: list[str],
    ) -> list[dict]:
        """Lista os usuários lotados na UE em cada perfil informado.

        Lê a tabela de fato, não a materialized view agregada por
        perfil, para poder restringir por `origem` (lotação, não
        atribuição de aula).

        Args:
            ue: Código da unidade educacional.
            dre: Código da DRE; None não filtra.
            perfis: GUIDs dos perfis consultados.

        Returns:
            Um registro por par `(login, perfil)`, com as UEs ordenadas.
        """
        consulta = UsuarioAbrangencia.objects.filter(
            ue_codigo=ue,
            perfil_guid__in=perfis,
            vigente=True,
            origem__in=ORIGENS_LOTACAO,
        )
        if dre is not None:
            consulta = consulta.filter(dre_codigo=dre)

        agrupado: dict[tuple[str, str], set[str]] = {}
        for login, perfil_guid, ue_codigo in consulta.values_list(
            "login", "perfil_guid", "ue_codigo"
        ):
            # O filtro `ue_codigo=ue` já garante que a coluna não é nula.
            chave = (login, str(perfil_guid))
            agrupado.setdefault(chave, set()).add(str(ue_codigo))

        return [
            {
                "usuario_rf": login,
                "perfil_guid": perfil_guid,
                "ues": sorted(ues),
            }
            for (login, perfil_guid), ues in sorted(agrupado.items())
        ]
