# 09: Verificação ponta a ponta e README de produção

> **Difficulty:** Standard: **suggested model:** Sonnet (Claude Code) / Sonnet (Cursor). Suggestion only, use whatever model you have to hand.

**Spec:** ../SPEC.md

**What to build:** a prova de que o conjunto funciona e o guia para operar.
- **Verificação:** sobe a imagem local com volume de teste e roda a verificação de entrega da spec:
  - build e `compose config -q`
  - `healthy`
  - logs em JSON
  - login e bloqueio por IP
  - nota importada e grupo criado sobrevivendo a `docker compose down && docker compose up -d`
  - backup e restauração
  - `make test`
- **README:** ganha a seção "Produção (Docker)":
  - variáveis
  - como gerar `SECRET_KEY` e o hash
  - subir local com volume de teste
  - backup e restauração
  - rollback por `IMAGE_TAG`
  - aviso de réplica única e disco local (não NFS)
  - migração dos dados atuais: `pricetrail.sqlite` vira `app.db` e `data/` vira `pdfs/`, mantendo as subpastas e fechando o servidor local antes, por causa do WAL
  - o checklist fora do código da spec
- **`docs/README.md`:** ganha a linha desta feature.

**Seams:**
- None (verificação manual com Docker e documentação)

**Blocked by:** 05 (Bloqueio de tentativas de login no SQLite), 07 (Backup do SQLite), 08 (CI que testa e publica no GHCR)

Status: ready-for-agent

- [ ] Todos os itens da verificação de entrega da spec conferidos, com a saída registrada no PR
- [x] Dados sobrevivem a `down && up`
- [x] README cobre variáveis, hash, backup/restauração, rollback, réplica única, migração dos dados e checklist
- [x] `docs/README.md` atualizado
