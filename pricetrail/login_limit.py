"""Bloqueio de tentativas de login, com estado no SQLite para sobreviver a restart.

Semântica de conan-torres/src/lib/reader/rate-limit-core.ts:
- por IP, MAX_FAILURES falhas bloqueiam o IP por LOCK_SECONDS; a entrada expira LOCK_SECONDS
  depois da última falha, ou no fim do bloqueio;
- somando todos os IPs, no máximo GLOBAL_MAX_FAILURES falhas em GLOBAL_WINDOW_SECONDS; ao
  atingir, toda tentativa é recusada (até a senha certa) até a falha mais antiga sair da janela;
- a tentativa conta como falha antes de a senha ser comparada; a senha certa apaga a contagem
  do IP e mantém a global;
- acima de MAX_TRACKED_IPS IPs rastreados, os menos ativos recentemente são descartados.

As constantes e o relógio são lidos a cada chamada: os testes os substituem.
"""
import math
import sqlite3
import time
from dataclasses import dataclass

MAX_FAILURES = 3
LOCK_SECONDS = 20 * 60
MAX_TRACKED_IPS = 10_000
GLOBAL_MAX_FAILURES = 10
GLOBAL_WINDOW_SECONDS = 24 * 60 * 60


def now() -> int:
    """Epoch em segundos."""
    return int(time.time())


@dataclass(frozen=True)
class Attempt:
    allowed: bool
    # Recusada: minutos até poder tentar de novo.
    minutes_left: int = 0
    # Aceita: minutos de bloqueio se esta tentativa errar; 0 quando não é a última.
    lock_minutes_if_wrong: int = 0
    # Esta tentativa levou ao teto global (acontece uma vez: as seguintes são recusadas antes de contar).
    cap_reached: bool = False


def _minutes(*seconds: int) -> int:
    """O bloqueio do IP e o teto global dão a mesma resposta: vale o mais longo."""
    return math.ceil(max(seconds) / 60)


def _prune(conn: sqlite3.Connection, at: int) -> None:
    conn.execute(
        "DELETE FROM login_attempts WHERE COALESCE(locked_until, last_failure_at + ?) <= ?",
        (LOCK_SECONDS, at),
    )
    conn.execute("DELETE FROM login_failures WHERE at + ? <= ?", (GLOBAL_WINDOW_SECONDS, at))


def _global_lock_seconds(conn: sqlite3.Connection, at: int) -> int:
    count, oldest = conn.execute("SELECT COUNT(*), MIN(at) FROM login_failures").fetchone()
    if count < GLOBAL_MAX_FAILURES:
        return 0
    return oldest + GLOBAL_WINDOW_SECONDS - at


def register_attempt(conn: sqlite3.Connection, ip: str) -> Attempt:
    """Confere o bloqueio e conta a tentativa como falha, numa transação só.

    BEGIN IMMEDIATE pega o lock de escrita antes da leitura: requisições paralelas, em threads
    ou workers, esperam a vez e não passam juntas pela checagem.
    """
    at = now()
    conn.execute("BEGIN IMMEDIATE")
    with conn:
        _prune(conn, at)
        row = conn.execute("SELECT failures, locked_until FROM login_attempts WHERE ip = ?", (ip,)).fetchone()
        ip_lock = row["locked_until"] - at if row and row["locked_until"] is not None else 0
        global_lock = _global_lock_seconds(conn, at)
        if ip_lock > 0 or global_lock > 0:
            return Attempt(allowed=False, minutes_left=_minutes(ip_lock, global_lock))
        failures = (row["failures"] if row else 0) + 1
        last_try = failures >= MAX_FAILURES
        conn.execute(
            "INSERT INTO login_attempts (ip, failures, last_failure_at, locked_until) VALUES (?, ?, ?, ?)"
            " ON CONFLICT (ip) DO UPDATE SET failures = excluded.failures,"
            " last_failure_at = excluded.last_failure_at, locked_until = excluded.locked_until",
            (ip, failures, at, at + LOCK_SECONDS if last_try else None),
        )
        # Descarta os menos ativos além do teto, nunca o IP que acabou de tentar.
        conn.execute(
            "DELETE FROM login_attempts WHERE ip IN (SELECT ip FROM login_attempts WHERE ip != ?"
            " ORDER BY last_failure_at, rowid LIMIT MAX(0, (SELECT COUNT(*) FROM login_attempts) - ?))",
            (ip, MAX_TRACKED_IPS),
        )
        conn.execute("INSERT INTO login_failures (at) VALUES (?)", (at,))
        cap_lock = _global_lock_seconds(conn, at)
    return Attempt(
        allowed=True,
        lock_minutes_if_wrong=_minutes(LOCK_SECONDS if last_try else 0, cap_lock),
        cap_reached=cap_lock > 0,
    )


def clear_failures(conn: sqlite3.Connection, ip: str) -> None:
    """Senha certa: some a contagem do IP; a global fica."""
    with conn:
        conn.execute("DELETE FROM login_attempts WHERE ip = ?", (ip,))
