"""Modelos base do microsserviço do domínio Abrangência."""

from django.db import models


class ModeloBase(models.Model):
    """Base para modelos que não são gerenciados pelo Django.

    O schema pertence ao `sme-airflow`, que o versiona por Flyway. Herdar
    daqui é o que impede este serviço de gerar migration para um objeto do
    qual não é dono.
    """

    class Meta:
        abstract = True
        managed = False
