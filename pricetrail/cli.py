"""Linha de comando: python3 -m pricetrail <subcomando>."""
import argparse
import sys
from pathlib import Path

from .importer import import_folder

PROJECT_DIR = Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pricetrail", description="Histórico de preços de NFC-e.")
    commands = parser.add_subparsers(dest="command", required=True)

    importar = commands.add_parser("import", help="importa PDFs de NFC-e para o SQLite")
    importar.add_argument("folder", nargs="?", type=Path, default=PROJECT_DIR / "data")
    importar.add_argument("--db", type=Path, default=PROJECT_DIR / "pricetrail.sqlite")
    importar.add_argument("--stores", type=Path, default=PROJECT_DIR / "stores.json")
    importar.add_argument("--log", type=Path, default=PROJECT_DIR / "pricetrail.log")

    args = parser.parse_args(argv)
    if args.command == "import":
        return import_folder(args.folder, args.db, args.stores, args.log)
    return 2


if __name__ == "__main__":
    sys.exit(main())
