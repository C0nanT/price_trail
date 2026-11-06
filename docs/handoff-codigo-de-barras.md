# Handoff: busca de produto por código de barras (EAN)

Status: **não implementado**. Pausado pelo usuário. Este documento tem o contexto para retomar.

## Objetivo

Facilitar a busca de um produto na página `chart.html` usando o código de barras
(EAN) da embalagem, em vez de digitar o nome.

## Descobertas

- O `pricetrail.py` lê PDFs de NFC-e da SEF/SC. A nota traz só o **código interno
  da loja**, não o EAN (comentário na linha 40 de `pricetrail.py`).
- No banco `pricetrail.sqlite`, os 303 produtos têm códigos curtos (ex.: `84323`).
  Nenhum tem 12 ou 13 dígitos. Não existe casamento automático EAN -> produto.
- O EAN sozinho não dá o nome do produto. O prefixo `789` é Brasil e os dígitos
  seguintes identificam a empresa. Nome e peso exatos exigem uma base externa
  (Cosmos, Open Food Facts) ou cadastro manual.
- A busca de `chart.html` filtra por descrição, código e loja
  (função `fillOptions` em `chart.py`).

## Exemplo concreto

Foto de um frasco de café solúvel Melitta (vidro): EAN `7891021007177`
(prefixo `7891021` = Melitta).

Itens Melitta no banco, todos do ATACADAO S.A.:

| Código | Descrição |
|--------|-----------|
| 84323 | CAFE MELITTA SOLUVEL |
| 94339 | CAFE MELITTA |
| 10759 | CAFE MELITTA PET |

**Pergunta em aberto:** qual deles é o frasco da foto? O mais provável é
`CAFE MELITTA SOLUVEL` (84323), mas o usuário não confirmou.

## Plano recomendado

1. **Tabela de apelidos** `ean_alias (ean TEXT PRIMARY KEY, seller_cnpj, product_code, unit)`
   no SQLite, preenchida à mão uma vez por produto. Um comando simples, por
   exemplo `python3 pricetrail.py --ean 7891021007177 --produto 84323`, ou um
   arquivo `data/eans.csv` lido na importação.
2. Em `chart.py`, `load_products` inclui o campo `eans` de cada produto no JSON.
   A busca de `fillOptions` passa a comparar também com os EANs.
3. Opcional: leitor de código de barras pela câmera do celular na página
   (API `BarcodeDetector`, ou biblioteca JS) que preenche o campo de busca.
   Só faz sentido depois do passo 1.
4. Opcional: consultar nome oficial por EAN numa base pública. Não resolve o
   casamento com os códigos da loja, só melhora o cadastro.

## Pontos de atenção

- O código interno é da loja. A mesma mercadoria em outra loja tem outro código.
  A tabela de apelidos deve permitir vários produtos por EAN (um por loja).
- `chart.html` é gerado por `chart.py` e funciona offline. Se a leitura por
  câmera usar biblioteca externa, ela precisa ser embutida na página.
- `BarcodeDetector` não existe em todos os navegadores (Firefox, por exemplo).
- Rodar `python3 chart.py` depois de mudar o banco ou o template.

## Estado atual da página (feito antes desta conversa)

Os cards "Último/Menor/Maior preço" e "Variação" foram removidos de `chart.py`.
No lugar: média dos preços, linha tracejada da média no gráfico, campo
"Preço atual" e veredito Barato/Caro/Na média (margem de 5%, `NEAR_AVERAGE`).
