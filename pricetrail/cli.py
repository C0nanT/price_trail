"""Linha de comando: python3 -m pricetrail <subcomando>."""
import argparse
import sys
from pathlib import Path

from .db import MigrationError
from .importer import import_folder
from .server import create_app

PROJECT_DIR = Path(__file__).resolve().parent.parent
HOST = "127.0.0.1"


def serve(db: Path, port: int) -> int:
    app = create_app(db, PROJECT_DIR)
    print(f"gráfico em http://{HOST}:{port}/")
    app.run(host=HOST, port=port)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pricetrail", description="Histórico de preços de NFC-e.")
    commands = parser.add_subparsers(dest="command", required=True)

    importar = commands.add_parser("import", help="importa PDFs de NFC-e para o SQLite")
    importar.add_argument("folder", nargs="?", type=Path, default=PROJECT_DIR / "data")
    importar.add_argument("--db", type=Path, default=PROJECT_DIR / "pricetrail.sqlite")
    importar.add_argument("--stores", type=Path, default=PROJECT_DIR / "stores.json")
    importar.add_argument("--log", type=Path, default=PROJECT_DIR / "pricetrail.log")

    servir = commands.add_parser("serve", help="abre o gráfico em um servidor local")
    servir.add_argument("--db", type=Path, default=PROJECT_DIR / "pricetrail.sqlite")
    servir.add_argument("--port", type=int, default=8000)

    args = parser.parse_args(argv)
    try:
        if args.command == "import":
            return import_folder(args.folder, args.db, args.stores, args.log, PROJECT_DIR)
        if args.command == "serve":
            return serve(args.db, args.port)
    except MigrationError as error:
        print(f"migração do banco falhou, nada foi alterado: {error}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
