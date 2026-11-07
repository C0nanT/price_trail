# 03: Página de agrupamento e PDFs no servidor

> **Difficulty:** Heavy: **suggested model:** Opus (Claude Code) / Opus or the strongest reasoning model available (Cursor). Suggestion only, use whatever model you have to hand.

**Spec:** ../SPEC.md

**What to build:** A página de agrupamento é servida pelo servidor e abre rápido, com dados de `GET /api/catalog`. O link de cada nota abre o PDF por `/notes/<chave>.pdf`, sem rodar `pdftotext` por request.

Uma migração adiciona `notes.source_path` e o preenche uma vez, lendo a chave de cada PDF, com fallback pelo nome. O import grava o caminho e o atualiza quando o arquivo muda de lugar. As rejeições ainda vêm de `products.rejected.json` até o ticket 05, e os botões de exportação continuam até o ticket 04. As duas páginas ganham link entre si.

**Seams:**
- API HTTP

**Blocked by:** 02: Gráfico servido pelo servidor local

Status: ready-for-human

- [x] `/api/catalog` tem o formato de `data.js`, com grupos vindos do banco
- [x] `href` aponta para a rota de PDF e é nulo se o arquivo não existir
- [x] Reimportar um PDF renomeado ou movido mantém o link funcionando
- [x] Rota de PDF retorna 404 para arquivo ausente e recusa chave que não tenha 44 dígitos
- [x] Caminho gravado no banco que aponte para fora da pasta de dados não é entregue
- [x] Nenhum request executa `pdftotext`
