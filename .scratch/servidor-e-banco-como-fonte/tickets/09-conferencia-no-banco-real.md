# 09: Conferência no banco real e backup

> **Difficulty:** Light: **suggested model:** Haiku (Claude Code) / claude-4.5-haiku-thinking (Cursor). Suggestion only, use whatever model you have to hand.

> **Gate:** human: copiar `pricetrail.sqlite` para um backup, subir o servidor no banco real, conferir as duas páginas, rodar `export` e commitar o arquivo gerado.

**Spec:** ../SPEC.md

**What to build:** Antes de apagar os JSONs e os scripts antigos, você confirma que o banco real migrou bem e que a curadoria está no arquivo exportado. Esse é o último ponto em que os JSONs versionados ainda existem como referência.

**Seams:** None

**Blocked by:** 08: Comparação de regressão

Status: ready-for-human

- [x] Backup do banco feito antes da primeira execução no banco real
- [x] Relatório do ticket 08 revisado
- [x] Gráfico e página de agrupamento conferidos no navegador, incluindo salvar um grupo e abrir um PDF
- [x] Arquivo do `export` commitado, com os 13 grupos, as rejeições e as 2 lojas
