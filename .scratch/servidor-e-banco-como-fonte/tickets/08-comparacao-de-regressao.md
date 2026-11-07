# 08: Comparação de regressão

> **Difficulty:** Standard: **suggested model:** Sonnet (Claude Code) / Sonnet (Cursor). Suggestion only, use whatever model you have to hand.

**Spec:** ../SPEC.md

**What to build:** Prova de que a API entrega os mesmos dados dos scripts antigos. Regenerar `chart.html` e `group_page/data.js` com os scripts atuais e os JSONs, extrair o JSON embutido e comparar com `/api/products` e `/api/catalog`, usando uma cópia do banco. O resultado é um relatório das diferenças. Qualquer diferença inesperada vira correção aqui mesmo.

**Seams:**
- API HTTP

**Blocked by:** 07: `export` e `restore` da curadoria

Status: ready-for-human

- [x] `/api/products` é igual aos dados do gráfico, exceto pela ordem
- [x] `/api/catalog` é igual a `data.js`, exceto por ordem, `href` e sugestões que voltam com a rejeição por par
- [x] Cada sugestão que voltou é listada no relatório
- [x] Todas as rotas respondem com o servidor no ar
- [x] Relatório gravado junto dos tickets, para a conferência do ticket 09
