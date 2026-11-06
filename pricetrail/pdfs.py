"""PDFs de nota: extração do texto e caminhos relativos à pasta de dados."""
import subprocess
from pathlib import Path

from .nfce import NoteError


def extract_text(path: Path) -> str:
    """Extrai o texto na ordem visual.

    Não usar -raw: ele separa rótulos de valores nos totais e joga esses valores
    no meio dos itens, na quebra de página.
    """
    result = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise NoteError(f"pdftotext falhou: {result.stderr.strip()}")
    return result.stdout


def find_pdfs(folder: Path) -> list[Path]:
    return sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() == ".pdf")


def path_in_data(path: Path, data_dir: Path) -> str | None:
    """Caminho relativo à pasta de dados, como vai para o banco. None se estiver fora dela."""
    resolved, root = path.resolve(), data_dir.resolve()
    return resolved.relative_to(root).as_posix() if resolved.is_relative_to(root) else None


def resolve_in_data(source_path: str | None, data_dir: Path) -> Path | None:
    """Arquivo de um source_path. None se não existir ou se sair da pasta de dados."""
    if source_path is None:
        return None
    resolved = (data_dir / source_path).resolve()
    return resolved if resolved.is_relative_to(data_dir.resolve()) and resolved.is_file() else None
