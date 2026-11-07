# 06: Cadastro de lojas pela página

> **Difficulty:** Standard: **suggested model:** Sonnet (Claude Code) / Sonnet (Cursor). Suggestion only, use whatever model you have to hand.

**Spec:** ../SPEC.md

**What to build:** Uma seção na página de agrupamento lista as lojas e as raízes de CNPJ sem cadastro, e permite definir nome e categoria com `GET /api/stores` e `PUT /api/stores/<raiz>`. O import deixa de ler `stores.json`: o aviso de loja sem cadastro consulta a tabela `stores` e orienta a usar a página. A opção `--stores` sai do subcomando.

**Seams:**
- API HTTP

**Blocked by:** 03: Página de agrupamento e PDFs no servidor

Status: ready-for-human

- [x] `/api/stores` separa lojas cadastradas e raízes presentes nas notas sem cadastro
- [x] `PUT` cria e atualiza; raiz que não tenha 8 dígitos ou nome vazio retorna 422
- [x] A loja cadastrada aparece com nome e categoria em `/api/products`
- [x] Loja sem cadastro continua com o nome da nota e a categoria "Outros"
- [x] Import avisa uma vez por raiz sem cadastro
