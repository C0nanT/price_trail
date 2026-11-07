"""Linha de comando: python3 -m pricetrail <subcomando>."""
import argparse
import getpass
import os
import sys
from contextlib import closing
from pathlib import Path

from .auth import AuthConfigError, hash_password
from .catalog import CurationFileError, export_curation, restore_curation
from .db import MigrationError, connect
from .importer import import_folder
from .logs import configure_server_logging
from .server import create_app

PROJECT_DIR = Path(__file__).resolve().parent.parent
HOST = "127.0.0.1"
CURATION_FILE = "curadoria.json"
DEFAULT_LOG = PROJECT_DIR / "pricetrail.log"


def env_paths() -> tuple[Path, Path]:
    """Banco e pasta dos PDFs: DB_PATH e DATA_DIR, senão os padrões na pasta do projeto."""
    return (Path(os.environ.get("DB_PATH") or PROJECT_DIR / "pricetrail.sqlite"),
            Path(os.environ.get("DATA_DIR") or PROJECT_DIR / "data"))


def serve(db: Path, data: Path, port: int) -> int:
    configure_server_logging()
    app = create_app(db, data, PROJECT_DIR)
    print(f"gráfico em http://{HOST}:{port}/, agrupamento em http://{HOST}:{port}/groups"
          f" e importação em http://{HOST}:{port}/import")
    app.run(host=HOST, port=port)
    return 0


def hash_password_command() -> int:
    """Pede a senha sem eco, duas vezes, e imprime o hash argon2 para o AUTH_PASSWORD_HASH do .env."""
    password = getpass.getpass("Senha: ")
    if not password:
        print("senha vazia: nada foi gerado", file=sys.stderr)
        return 2
    if getpass.getpass("Repita a senha: ") != password:
        print("as senhas não conferem: nada foi gerado", file=sys.stderr)
        return 2
    print(hash_password(password))
    return 0


def export(db: Path, data: Path, out: Path) -> int:
    with closing(connect(db, data, PROJECT_DIR)) as conn:
        text = export_curation(conn)
    out.write_text(text, encoding="utf-8")
    print(f"curadoria exportada para {out}")
    return 0


def restore(db: Path, data: Path, file: Path) -> int:
    try:
        text = file.read_text(encoding="utf-8")
    except OSError as error:
        print(f"não foi possível ler {file}: {error}", file=sys.stderr)
        return 2
    with closing(connect(db, data, PROJECT_DIR)) as conn:
        try:
            restore_curation(conn, text)
        except CurationFileError as error:
            print(f"arquivo de curadoria inválido, nada foi alterado: {error}", file=sys.stderr)
            return 2
    print(f"curadoria restaurada de {file}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pricetrail", description="Histórico de preços de NFC-e.")
    commands = parser.add_subparsers(dest="command", required=True)

    # Opções de todos os subcomandos: onde está o banco e a pasta dos PDFs.
    paths = argparse.ArgumentParser(add_help=False)
    default_db, default_data = env_paths()
    paths.add_argument("--db", type=Path, default=default_db)
    paths.add_argument("--data", type=Path, default=default_data, help="pasta de dados, com os PDFs")

    importar = commands.add_parser("import", parents=[paths], help="importa PDFs de NFC-e para o SQLite")
    importar.add_argument("folder", nargs="?", type=Path, help="pasta a ler (padrão: a pasta de dados)")
    importar.add_argument("--log", type=Path, default=DEFAULT_LOG)

    servir = commands.add_parser("serve", parents=[paths], help="abre o gráfico e o agrupamento em um servidor local")
    servir.add_argument("--port", type=int, default=8000)

    exportar = commands.add_parser("export", parents=[paths], help="grava grupos, pares rejeitados e lojas num JSON")
    exportar.add_argument("--out", type=Path, default=PROJECT_DIR / CURATION_FILE,
                          help=f"arquivo de saída (padrão: {CURATION_FILE})")

    restaurar = commands.add_parser("restore", parents=[paths],
                                    help="substitui a curadoria do banco pelo arquivo exportado")
    restaurar.add_argument("file", nargs="?", type=Path, default=PROJECT_DIR / CURATION_FILE,
                           help=f"arquivo a ler (padrão: {CURATION_FILE})")

    commands.add_parser("hash-password", help="pede uma senha e imprime o hash argon2 para AUTH_PASSWORD_HASH")

    args = parser.parse_args(argv)
    try:
        if args.command == "hash-password":
            return hash_password_command()
        if args.command == "import":
            return import_folder(args.folder or args.data, args.db, args.log, args.data, PROJECT_DIR)
        if args.command == "serve":
            return serve(args.db, args.data, args.port)
        if args.command == "export":
            return export(args.db, args.data, args.out)
        if args.command == "restore":
            return restore(args.db, args.data, args.file)
    except MigrationError as error:
        print(f"migração do banco falhou, nada foi alterado: {error}", file=sys.stderr)
        return 2
    except AuthConfigError as error:
        print(f"o servidor não subiu: {error}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
