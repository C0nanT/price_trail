# 10: Subir na VPS

> **Difficulty:** Heavy: **suggested model:** Opus (Claude Code) / Opus or the strongest reasoning model available (Cursor). Suggestion only, use whatever model you have to hand.

> **Gate:** human: criar o DNS na Cloudflare, preparar `/opt/apps/price_trail/` na VPS com compose e `.env`, copiar banco e PDFs para o volume, agendar o backup e decidir sobre o Cloudflare Access

**Spec:** ../SPEC.md

**What to build:** o site no ar em `https://compras.conantorres.dev`, com os dados atuais, seguindo o checklist do README.

**Seams:**
- None (ação humana na infraestrutura)

**Blocked by:** 09 (Verificação ponta a ponta e README de produção)

Status: ready-for-agent

- [ ] Cloudflare: registro `compras` apontando para a VPS, nuvem laranja
- [ ] VPS: `/opt/apps/price_trail/` com `docker-compose.yml` e `.env` (`SECRET_KEY`, usuário, hash entre aspas simples, `ALLOWED_HOSTS`)
- [ ] `docker network inspect proxy` → sub-rede em `FORWARDED_ALLOW_IPS`
- [ ] `docker login ghcr.io` com token `read:packages`, se ainda não feito
- [ ] Volume `price_trail_data` criado; `app.db` e `pdfs/` copiados; `chown -R 10001:10001`; `docker compose restart`
- [ ] Container `healthy`, login funcionando, links dos PDFs abrindo, logs aparecendo no Loki com `projeto=price_trail`
- [ ] Backup diário no cron da VPS, com uma execução manual conferida
- [ ] Decisão registrada sobre o Cloudflare Access
- [ ] Depois de alguns dias, `mem_limit` ajustado pelo uso medido com `docker stats`
