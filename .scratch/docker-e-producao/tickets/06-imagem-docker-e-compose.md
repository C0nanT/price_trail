# 06: Imagem Docker e compose de produção

> **Difficulty:** Heavy: **suggested model:** Opus (Claude Code) / Opus or the strongest reasoning model available (Cursor). Suggestion only, use whatever model you have to hand.

**Spec:** ../SPEC.md

**What to build:** o app roda num container pronto para a borda.
- **Servidor:** gunicorn (versão fixa) com 1 worker `gthread` e 4 threads, bind em `0.0.0.0:8000`, `--worker-tmp-dir /tmp`. Uma fábrica monta o app a partir do ambiente.
- **Proxy e logs do gunicorn:** `forwarded_allow_ips` vem de `FORWARDED_ALLOW_IPS`, e o `X-Forwarded-Proto` é respeitado, para que `Origin` e cookie `Secure` funcionem atrás do Traefik. Log de acesso em JSON no stdout, sem query string; log de erro no stderr.
- **Banco ocupado:** `database is locked` que estoura o `busy_timeout` vira 503 JSON com log de aviso.
- **`Dockerfile`:**
  - base `python:3.12.x-slim-bookworm` com tag fixa; `PYTHONUNBUFFERED=1` e `PYTHONDONTWRITEBYTECODE=1`
  - `poppler-utils`; dependências instaladas antes do código
  - copia só o pacote
  - usuário UID/GID 10001 e `/data` com esse dono
  - `EXPOSE 8000`; `HEALTHCHECK` no `/health` via `python -c "import urllib.request…"`
- **`docker-compose.yml`:** como na spec.
  - `name: price_trail`, serviço `web`, `image: ghcr.io/c0nant/price_trail:${IMAGE_TAG:-latest}`, sem `build:`
  - `restart: unless-stopped`, `env_file: .env`, `expose` sem `ports`
  - volume nomeado `data:/data`
  - `read_only`, `tmpfs: /tmp`, `no-new-privileges`, `mem_limit: 256m` com o comentário da regra de medição
  - healthcheck herdado, com comentário
  - rede externa `proxy` e as labels do Traefik com `price_trail` e porta 8000
  - `logging` json-file 10m × 5
- **`.dockerignore`:** a lista completa da spec.
- **`.env.example`:** cada variável comentada, com o hash entre aspas simples por causa do `$`.
- **`Makefile`:** carrega o `.env` local se existir.

**Seams:**
- Seam B: API HTTP pelo Flask test client (`ApiTestCase`), para o 503 em `database is locked`
- Fora das seams: verificação manual com Docker (critérios abaixo)

**Blocked by:** 01 (Configuração por ambiente, PRAGMAs e `/health`), 02 (Logs em JSON no stdout/stderr, sem dados de compras), 04 (Login de usuário único)

Status: ready-for-human

- [x] `docker build` passa e a imagem não contém `.db`, `.sqlite`, PDF, `.env` nem `tests/`
- [x] O container roda como UID 10001
- [x] `docker compose config -q` passa com um `.env` de teste e a rede `proxy` criada localmente
- [x] Com um override local (só porta publicada e volume de teste), o container fica `healthy`
- [x] `docker compose logs` mostra JSON, incluindo o acesso do gunicorn
- [x] Login funciona pelo override local (com `SESSION_COOKIE_SECURE=0`) e o upload pelo `/import` funciona
- [x] `database is locked` persistente → 503 JSON (teste)
- [x] Compose não tem `ports`, `build`, `tls.domains`, router `-www` nem outro driver de log
- [x] `make serve` local continua funcionando com o `.env` local
