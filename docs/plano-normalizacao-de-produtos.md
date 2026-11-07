# Plano: normalização de produtos

Status: **implementado na variante manual (B)**. Nada é agrupado automaticamente:
o servidor sugere candidatos, você aprova na página `/groups` e os grupos ficam no banco
(tabelas de grupos e de pares rejeitados). Os antigos `suggest_products.py`, `chart.py` e
`products.json` foram removidos; o texto abaixo é o plano original. Junção automática
(com faixa de preço/unidade) e código de barras seguem como evolução possível.

Plano original:

## Problema

O mesmo produto aparece separado no gráfico:

- Mesma descrição com códigos diferentes na mesma loja (`AGUA M.CRYSTAL`,
  `BARRA CEREAIS NUTRY`, `BATATA PALHA YOKI`: 2 a 3 códigos cada).
- Mesmo item com nomes diferentes entre lojas (Atacadão x farmácia).
- Nenhum código de produto tem descrições diferentes: o código é estável por loja.

## Proposta

1. Tabelas novas:
   - `products(id, name)`
   - `product_aliases(seller_prefix, product_code, product_id)`, onde
     `seller_prefix` são os 8 primeiros dígitos do CNPJ.
2. **Agrupamento automático** por (CNPJ8, descrição normalizada: maiúscula, sem
   acento nem pontuação). Junta os casos de código duplicado na mesma loja.
3. **Agrupamento manual** em `products.json`, no estilo de `stores.json`:

   ```json
   {"Leite Condensado Tirol": ["L.COND.TIROL SEMI.TP", "LEITE COND TIROL 395G"]}
   ```

4. `chart.py` passa a buscar e agrupar pelo nome canônico; a tabela de compras
   mostra a descrição original da nota.
5. Com código de barras (ver `handoff-codigo-de-barras.md`) o passo 3 vira
   automático.

## Critérios de pronto

- Reimportar não duplica aliases.
- Produto sem regra continua aparecendo pela descrição original.
- Testes: normalização de texto, junção por código duplicado, `products.json`
  ausente/inválido.

## Achados nos dados reais (revisão antes de implementar)

Agrupar por (CNPJ8, descrição normalizada) gera 28 grupos com 2+ códigos entre
354 produtos. Eles **não são todos o mesmo produto**:

- Mesmo produto, preço igual: `DET.LIQ.YPE` (3 códigos, sempre 2,79),
  `REFR.PO CLIGHT` (6 códigos, sempre 1,79: provavelmente sabores).
- Variantes com preços bem diferentes: `AGUA SANIT.Q.BOA` (4,59 x 6,98, tamanhos),
  `MOLHO TOM.POMAROLA` (2,99 / 4,99 / 5,29 / 18,90).
- Unidades diferentes no mesmo grupo: `PULLMAN RAP 10` (EMB x UND).

Conclusão: junção automática só pela descrição pode misturar tamanhos e esconder
variação real de preço. A decisão de como juntar está pendente.
