# 07: Backup do SQLite

> **Difficulty:** Standard: **suggested model:** Sonnet (Claude Code) / Sonnet (Cursor). Suggestion only, use whatever model you have to hand.

**Spec:** ../SPEC.md

**What to build:** um backup consistente do banco, com o app rodando, executado pelo Python do container (sem depender do binário `sqlite3`). Roda como subcomando `pricetrail backup`, chamado com `docker compose exec -T web python -m pricetrail backup`. Ele faz `VACUUM INTO` para `/data/backups/app-AAAAMMDD-HHMMSS.db`, ou seja, numa pasta `backups` ao lado de `DB_PATH`, e nunca copia o arquivo. Mantém os últimos `BACKUP_KEEP` (padrão 14) e apaga os mais antigos. Loga em JSON só o nome gerado, o tamanho, quantos apagou e a duração. Documenta a linha de cron da VPS e o passo a passo de restauração: parar o serviço, num container temporário com o volume copiar o backup sobre `app.db` e apagar `-wal`/`-shm`, depois subir.

**Seams:**
- Seam B: API HTTP pelo Flask test client (`ApiTestCase`): o backup restaurado num app novo devolve os mesmos dados pela API

**Blocked by:** 06 (Imagem Docker e compose de produção)

Status: ready-for-human

- [x] Backup gera um arquivo SQLite íntegro (`PRAGMA integrity_check` = ok) com os dados atuais, inclusive o que estava só no `-wal`
- [x] Com `BACKUP_KEEP=2` e 3 execuções, sobram os 2 mais novos
- [x] Um app criado sobre o backup devolve os mesmos produtos pela API (teste)
- [x] Funciona dentro do container com `read_only` (só `/data` gravável)
- [x] `.env.example` documenta `BACKUP_KEEP`
- [x] Cron e restauração documentados no README e testados localmente
