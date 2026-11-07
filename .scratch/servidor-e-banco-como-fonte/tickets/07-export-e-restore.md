# 07: `export` e `restore` da curadoria

> **Difficulty:** Standard: **suggested model:** Sonnet (Claude Code) / Sonnet (Cursor). Suggestion only, use whatever model you have to hand.

**Spec:** ../SPEC.md

**What to build:** `python3 -m pricetrail export` grava grupos, pares rejeitados e lojas em um único JSON, pronto para commitar. `python3 -m pricetrail restore` substitui a curadoria do banco pelo conteúdo do arquivo, em uma transação. Recriar do zero passa a ser importar os PDFs e restaurar.

**Seams:**
- API HTTP

**Blocked by:** 04: Salvar grupos direto no banco; 05: Rejeição por par e "não juntar"; 06: Cadastro de lojas pela página

Status: ready-for-human

- [x] Exportar duas vezes sem mudanças gera arquivos idênticos, com chaves e listas ordenadas
- [x] O arquivo tem um campo de versão de formato
- [x] Exportar, restaurar num banco novo com as mesmas notas e obter as mesmas respostas de `/api/products` e `/api/catalog`
- [x] Arquivo inválido ou de formato desconhecido falha com mensagem clara e não altera o banco
- [x] Curadoria que referencia produto ainda sem nota é restaurada sem erro
