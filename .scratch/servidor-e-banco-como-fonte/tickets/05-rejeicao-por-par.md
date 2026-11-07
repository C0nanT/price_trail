# 05: Rejeição por par e "não juntar"

> **Difficulty:** Standard: **suggested model:** Sonnet (Claude Code) / Sonnet (Cursor). Suggestion only, use whatever model you have to hand.

**Spec:** ../SPEC.md

**What to build:** Na página de agrupamento, "não juntar" tira uma sugestão da lista sem esconder aqueles produtos de sugestões com outros, e uma lista de rejeições permite desfazer. Uma migração cria `rejected_pairs` e carrega `products.rejected.json`: cada grupo do arquivo vira todos os pares entre suas referências. `POST` e `DELETE /api/rejections` recebem uma lista de referências e criam ou removem todos os pares entre elas.

**Seams:**
- API HTTP

**Blocked by:** 03: Página de agrupamento e PDFs no servidor

Status: ready-for-human

- [x] Par é guardado em ordem canônica, sem duplicidade
- [x] Um produto só sai da sugestão se todos os seus pares nela estiverem rejeitados
- [x] Sugestão com menos de 2 produtos some; sugestões iguais seguem unificadas e os avisos são recalculados
- [x] Par rejeitado não afeta sugestões com terceiros
- [x] Desfazer faz a sugestão voltar
- [x] Carga do arquivo roda uma única vez e `/api/catalog` deixa de ler o JSON
