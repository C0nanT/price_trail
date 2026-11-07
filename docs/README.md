# Docs de features

| Documento | Status |
|-----------|--------|
| [plano-filtros-do-grafico.md](plano-filtros-do-grafico.md) | **Implementado** (intervalo de datas, ordenação, badge de variação) |
| [plano-normalizacao-de-produtos.md](plano-normalizacao-de-produtos.md) | **Implementado (manual)**: sugestões e grupos pelo servidor (`/groups`), gravados no banco |
| [handoff-codigo-de-barras.md](handoff-codigo-de-barras.md) | Pausado |

Já feito fora dos planos: página `/groups` (`pricetrail/web/group/`) para montar os grupos, página `/import`
(`pricetrail/web/import/`) para enviar PDFs de NFC-e pelo navegador, testes do parser (`tests/`), hook `pre-push`, aviso de
loja sem cadastro (agora cadastrada pela página `/groups`).

Estilo: as páginas usam um único `pricetrail/web/app.css`, gerado pelo Tailwind com `make css`
(ou `make css-watch` durante a edição). Detalhes e download da CLI estão na seção "Estilo (Tailwind)" do README.
