# 02: Gráfico servido pelo servidor local

> **Difficulty:** Heavy: **suggested model:** Opus (Claude Code) / Opus or the strongest reasoning model available (Cursor). Suggestion only, use whatever model you have to hand.

**Spec:** ../SPEC.md

**What to build:** `python3 -m pricetrail serve` abre o gráfico numa URL local, sempre com os dados atuais do banco. Este ticket traz o caminho completo: migrações por `PRAGMA user_version`, tabelas `stores`, `product_groups` e `group_refs` com carga inicial de `stores.json` e `products.json`, consultas em `catalog`, `GET /api/products` e a página do gráfico como arquivos estáticos que usam `fetch`.

A identidade do produto passa a ser a raiz do CNPJ, e referências por descrição deixam de existir. O servidor já nasce restrito: escuta em `127.0.0.1`, recusa `Host` estranho, usa uma conexão por request e WAL. Flask entra como dependência declarada.

**Seams:**
- API HTTP

**Blocked by:** 01: Pacote `pricetrail` e subcomando `import`

Status: ready-for-human

- [x] Migração funciona em banco novo e no banco atual (versão 0 com `notes`, `items` e a view), preservando os dados
- [x] Carga inicial roda uma única vez; reabrir o banco não tem efeito
- [x] A chave primária de `group_refs` impede uma referência em dois grupos
- [x] `/api/products` tem o formato dos dados hoje embutidos no gráfico
- [x] Produtos agrupados juntam, unidades diferentes não juntam e duas filiais da mesma raiz viram um produto
- [x] O gráfico mantém filtros, média, preço atual e veredito, e mostra erro claro se a API falhar
- [x] Request com `Host` diferente de localhost ou `127.0.0.1` é recusado
- [x] Importar com o servidor ligado funciona
- [x] `.gitignore` cobre os arquivos `-wal` e `-shm`
- [x] Validação manual usa uma cópia do banco, não `pricetrail.sqlite`
