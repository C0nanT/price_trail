"""Fábrica do app para o gunicorn: tudo vem do ambiente (DB_PATH, DATA_DIR, login, LOG_LEVEL).

    gunicorn -c python:pricetrail.gunicorn_conf 'pricetrail.wsgi:create()'
"""
import logging

from flask import Flask

from .auth import AuthConfigError
from .cli import PROJECT_DIR, env_paths
from .db import MigrationError
from .logs import configure_server_logging
from .server import create_app


def create() -> Flask:
    log = configure_server_logging()
    db, data = env_paths()
    try:
        return create_app(db, data, PROJECT_DIR)
    # Sem traceback: o gunicorn encerra ao ver o worker falhar na subida.
    except AuthConfigError as error:
        log.error("o servidor não subiu: %s", error)
        raise SystemExit(3) from None
    except MigrationError:
        # A mensagem da migração pode citar nomes de grupos da curadoria: não vai para o log.
        log.error("o servidor não subiu: a migração do banco falhou, nada foi alterado")
        raise SystemExit(3) from None
