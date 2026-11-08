# 01: Configuração por ambiente, PRAGMAs e `/health`

> **Difficulty:** Standard: **suggested model:** Sonnet (Claude Code) / Sonnet (Cursor). Suggestion only, use whatever model you have to hand.

**Spec:** ../SPEC.md

**What to build:** o servidor passa a ler do ambiente onde estão o banco (`DB_PATH`), a pasta dos PDFs (`DATA_DIR`) e quais hosts aceita (`ALLOWED_HOSTS`, separados por vírgula). Sem variáveis, tudo funciona como hoje em localhost. Os argumentos `--db`, `--data` e `--port` do CLI continuam valendo e ganham do ambiente. Toda conexão SQLite liga `journal_mode=WAL`, `busy_timeout=5000` e `foreign_keys=ON`, e a pasta pai do banco é criada se faltar. Um `GET /health` abre uma conexão nova, roda `SELECT 1` e responde `200 {"status":"ok"}`, ou `503 {"status":"erro"}` sem detalhes no corpo. Ele não migra nada nem toca nos PDFs.

**Seams:**
- Seam B: API HTTP pelo Flask test client (`ApiTestCase`)

**Blocked by:** None (can start immediately)

Status: ready-for-human

- [x] `DB_PATH`, `DATA_DIR` e `ALLOWED_HOSTS` são lidos do ambiente, com os padrões locais atuais quando ausentes; argumento do CLI tem precedência
- [x] Host fora de `ALLOWED_HOSTS` continua recebendo 403; um host extra configurado passa
- [x] Toda conexão sai com WAL, `busy_timeout=5000` e chaves estrangeiras ligadas
- [x] `GET /health` → 200 com banco ok; 503 quando o banco não abre (teste com caminho inválido)
- [x] `/health` responde no host `127.0.0.1`
- [x] `.gitignore` ganha `*.db`, `*.db-wal`, `*.db-shm` e `.env`
- [x] `make test` passa
