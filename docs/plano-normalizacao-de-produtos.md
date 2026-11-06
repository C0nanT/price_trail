# Plano: normalização de produtos

Status: **planejado, não implementado**.

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
