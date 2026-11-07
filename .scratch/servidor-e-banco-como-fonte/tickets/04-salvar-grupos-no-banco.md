# 04: Salvar grupos direto no banco

> **Difficulty:** Standard: **suggested model:** Sonnet (Claude Code) / Sonnet (Cursor). Suggestion only, use whatever model you have to hand.

**Spec:** ../SPEC.md

**What to build:** Criar, renomear, editar e excluir grupos na página salva no banco, e o gráfico reflete isso ao recarregar. `PUT /api/groups` substitui todos os grupos em uma transação. Saem da página baixar, copiar, salvar em arquivo e o rascunho em localStorage.

**Seams:**
- API HTTP

**Blocked by:** 03: Página de agrupamento e PDFs no servidor

Status: ready-for-human

- [x] Grupo salvo aparece em `/api/products` e `/api/catalog`
- [x] Referência em dois grupos ou nome repetido retorna 422 com mensagem legível, sem alterar nada
- [x] Escrita sem `Content-Type: application/json` é recusada
- [x] A página mostra o erro de salvamento e mantém a edição em tela
- [x] Não sobra código de exportação nem de localStorage na página
