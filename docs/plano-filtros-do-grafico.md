# Plano: filtros e destaques no gráfico

Status: **planejado, não implementado**. Tudo em `chart.py` (JS embutido), sem
mudar o banco. Pode ser feito antes da normalização de produtos.

## Itens

1. **Intervalo de datas**: dois `<input type="date">` que filtram a série, o
   menor/maior preço e a tabela de compras.
2. **Ordenar a lista de produtos** por nome, número de compras ou variação %.
3. **Badge de variação** ao lado do preço, por exemplo "↑ 12% vs última compra"
   (vermelho para alta, verde para queda; produto com uma só compra não mostra).

## Critérios de pronto

- Funciona offline, como o resto da página.
- Filtros se combinam com categoria, estabelecimento e busca atuais.
- Estado vazio claro quando o intervalo não tem compras.
