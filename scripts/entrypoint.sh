#!/bin/sh
# Não há migrations neste serviço (todos os models são managed=False), mas
# mantém o mesmo padrão de entrypoint dos demais projetos Identidade: aplica
# migrate sem bloquear o boot caso o banco esteja momentaneamente indisponível.
set -e

python manage.py migrate --noinput || echo "AVISO: migrate falhou, subindo mesmo assim"

exec "$@"
