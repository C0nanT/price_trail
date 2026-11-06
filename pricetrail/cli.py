"""Linha de comando: python3 -m pricetrail <subcomando>."""
import argparse
import sys
from pathlib import Path

from .db import MigrationError
from .importer import import_folder
from .server import create_app

PROJECT_DIR = Path(__file__).resolve().parent.parent
HOST = "127.0.0.1"


def serve(db: Path, data: Path, port: int) -> int:
    app = create_app(db, data, PROJECT_DIR)
    print(f"gráfico em http://{HOST}:{port}/ e agrupamento em http://{HOST}:{port}/groups")
    app.run(host=HOST, port=port)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pricetrail", description="Histórico de preços de NFC-e.")
    commands = parser.add_subparsers(dest="command", required=True)

    importar = commands.add_parser("import", help="importa PDFs de NFC-e para o SQLite")
    importar.add_argument("folder", nargs="?", type=Path, help="pasta a ler (padrão: a pasta de dados)")
    importar.add_argument("--db", type=Path, default=PROJECT_DIR / "pricetrail.sqlite")
    importar.add_argument("--data", type=Path, default=PROJECT_DIR / "data", help="pasta de dados, com os PDFs")
    importar.add_argument("--log", type=Path, default=PROJECT_DIR / "pricetrail.log")

    servir = commands.add_parser("serve", help="abre o gráfico e o agrupamento em um servidor local")
    servir.add_argument("--db", type=Path, default=PROJECT_DIR / "pricetrail.sqlite")
    servir.add_argument("--data", type=Path, default=PROJECT_DIR / "data", help="pasta de dados, com os PDFs")
    servir.add_argument("--port", type=int, default=8000)

    args = parser.parse_args(argv)
    try:
        if args.command == "import":
            return import_folder(args.folder or args.data, args.db, args.log, args.data, PROJECT_DIR)
        if args.command == "serve":
            return serve(args.db, args.data, args.port)
    except MigrationError as error:
        print(f"migração do banco falhou, nada foi alterado: {error}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
