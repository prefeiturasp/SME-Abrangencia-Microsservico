"""Monta em cache as DREs, UEs e turmas do dia."""

from typing import Any

import httpx
from django.core.management.base import BaseCommand, CommandError

from apps.abrangencia.rede_sme import RedeSmeIncompletaError, obter_rede_sme


class Command(BaseCommand):
    """Monta a rede do dia."""

    help = "Monta em cache as DREs, UEs e turmas do dia."

    def handle(self, *args: Any, **options: Any) -> None:
        rede = obter_rede_sme()
        try:
            rede.carregar()
        except httpx.HTTPError as exc:
            raise CommandError(f"Rede indisponivel: {exc}") from exc
        except RedeSmeIncompletaError as exc:
            raise CommandError(f"Rede SME incompleta: {exc}") from exc
        self.stdout.write(f"Rede montada: {len(rede.ues())} UEs.")
