# 10: Remover scripts antigos e atualizar docs

> **Difficulty:** Standard: **suggested model:** Sonnet (Claude Code) / Sonnet (Cursor). Suggestion only, use whatever model you have to hand.

**Spec:** ../SPEC.md

**What to build:** O projeto passa a ter só o novo fluxo. Saem `chart.py`, `group_page.py`, `suggest_products.py`, `products.json`, `products.rejected.json`, `stores.json`, os artefatos gerados e suas entradas no `.gitignore`. Também sai o código que só servia aos scripts, como `Resolver` e a leitura dos JSONs fora da migração.

A carga inicial das migrações continua tolerando a ausência dos arquivos. Os testes que ainda usam os scripts são reescritos contra a API, mantendo os cenários. README e `docs/` passam a descrever `serve`, `export`, `restore`, as dependências e o novo jeito de recriar o banco.

**Seams:**
- API HTTP
- Parser

**Blocked by:** 09: Conferência no banco real e backup

Status: ready-for-human

- [x] Banco novo sem os JSONs é criado sem erro
- [x] Nenhum teste importa os scripts removidos, e a suíte passa
- [x] README não fala mais em gerar páginas, apagar o banco ou "sem dependências"
- [x] README não diz mais que só uma nota do Atacadão foi testada
- [x] `docs/README.md` e `docs/handoff-codigo-de-barras.md` não citam `chart.py` como atual
