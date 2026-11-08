# 08: CI que testa e publica no GHCR

> **Difficulty:** Heavy: **suggested model:** Opus (Claude Code) / Opus or the strongest reasoning model available (Cursor). Suggestion only, use whatever model you have to hand.

**Spec:** ../SPEC.md

**What to build:** a cada push na `main`, o GitHub Actions roda a suíte de testes e, se passar, builda a imagem e publica `ghcr.io/c0nant/price_trail:<sha>` e `:latest`. O login em `ghcr.io` usa `GITHUB_TOKEN`, com permissões `contents: read` e `packages: write`, e as ações têm versão fixa. O CI só publica: o deploy é o cron da VPS.

**Seams:**
- None (workflow de CI; verificado pela execução no GitHub)

**Blocked by:** 06 (Imagem Docker e compose de produção)

Status: ready-for-agent

- [x] Disparo só em push na `main`
- [x] Testes falhando impedem o build e o push
- [x] Imagem publicada com as tags do SHA completo e `latest`, nome em minúsculas
- [x] Nenhum segredo além do `GITHUB_TOKEN`
- [ ] Primeira execução verde no GitHub e a imagem visível nos packages do usuário
