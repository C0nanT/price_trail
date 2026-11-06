# pricetrail

Guarda o histórico de preços das suas compras. O script lê os PDFs de NFC-e da
Consulta Pública da SEF/SC e salva produtos e preços em um banco SQLite.

## De onde vêm os preços

Os preços vêm das notas fiscais (NFC-e) consultadas no portal da SEF/SC:

<https://sat.sef.sc.gov.br/tax.net/Sat.Dfe.Web/Consultas/ConsultaNotaCidadao.aspx>

Salve a nota como PDF a partir dessa página e coloque o arquivo em `data/`.

## Requisitos

- Python 3.10 ou mais recente
- `pdftotext`, do pacote poppler-utils:

  ```bash
  sudo apt install poppler-utils
  ```

- As dependências Python, usadas pelo servidor local:

  ```bash
  pip install -r requirements.txt
  ```

## Como usar

1. Salve os PDFs das notas em `data/`. Subpastas também são lidas.
2. Ao salvar pelo Chrome, desligue a opção "Cabeçalhos e rodapés".
3. Rode o script:

   ```bash
   python3 -m pricetrail import
   ```

Para usar outra pasta ou outro banco:

```bash
python3 -m pricetrail import --data outra/pasta --db outro.sqlite
```

`--data` é a pasta de dados, a mesma que o `serve` usa para abrir os PDFs. Para ler só
uma subpasta dela, passe a subpasta: `python3 -m pricetrail import data/2026`.

Pode rodar quantas vezes quiser. A nota é identificada pela chave de acesso,
então PDF repetido não duplica dados, mesmo com outro nome de arquivo.

## Ver o gráfico

Inicie o servidor local e abra <http://127.0.0.1:8000/> no navegador:

```bash
python3 -m pricetrail serve
```

A página lê direto do banco: depois de importar notas, basta recarregar. Dá para
importar com o servidor ligado. O servidor só aceita conexões da sua máquina, porque
os PDFs contêm seu CPF. Use `--port` para outra porta, `--db` para outro banco e
`--data` para outra pasta de dados.

Filtre por categoria (Mercado, Farmácia…) e, dentro dela, por estabelecimento
(Atacadão, Farmácia Preço Popular…). Busque um produto, escolha na lista e veja o histórico de preços, com o menor e o
maior preço e a tabela de compras. Também dá para limitar por intervalo de datas,
ordenar a lista (mais compras, nome, maior alta, maior queda) e ver a variação
do último preço contra a compra anterior. A página não depende de internet, só do
servidor ligado.

As categorias e os nomes dos estabelecimentos vêm da tabela `stores`, indexada pelos 8
primeiros dígitos do CNPJ (iguais em todas as filiais). Ela é carregada de `stores.json`
na primeira vez que o banco é aberto e depois é editada na seção "Lojas" da página `/groups`. Loja sem cadastro aparece com o nome da nota e a
categoria "Outros".

A mesma mercadoria em duas filiais da mesma rede é um produto só: um produto é a raiz
do CNPJ, o código e a unidade.

## O que aparece na saída

| Saída    | Significado                                     |
| -------- | ----------------------------------------------- |
| `NOVA`   | Nota importada                                  |
| `JÁ TEM` | Nota já estava no banco e foi ignorada          |
| `ERRO`   | Nota não importada; o motivo aparece na mensagem |

Antes de gravar, o script confere a chave de acesso, a quantidade de itens e os
totais da nota. Se algo não bater, a nota inteira fica de fora e os demais
arquivos continuam sendo processados. Nesse caso, o script termina com código 1.

## Dados salvos

O banco fica em `pricetrail.sqlite`:

- `notes`: estabelecimento, endereço, data de emissão, totais e desconto
- `items`: produtos da nota, com quantidade, unidade e preços
- `price_history`: view que junta as duas tabelas, pronta para gráficos

Exemplo de consulta:

```bash
sqlite3 pricetrail.sqlite "
  SELECT purchase_date, seller_name, unit_price, price_per_kg
  FROM price_history
  WHERE description LIKE '%BANANA%'
  ORDER BY purchase_date;
"
```

O comando `sqlite3` é instalado à parte, com `sudo apt install sqlite3`.

## Como interpretar os dados

- **`purchase_date`:** é o dia da compra, tirado da data de emissão da nota.
  `issued_at` traz a data com a hora.
- **`price_per_kg`:** usa o preço unitário de itens vendidos em KG. Nos demais,
  calcula pelo peso escrito na descrição, como `500G`. Sem peso, fica `NULL`.
- **`unit_price`:** é o preço impresso na nota. O desconto vem só no total, então
  fica em `notes.discount_cents` e não é dividido entre os itens.
- **`product_code`:** é o código interno de cada loja, não o código de barras.
  Para acompanhar um produto, agrupe por `seller_cnpj` e `product_code`.
- **CPF:** não é salvo no banco, mas continua nos PDFs.

## Limitações

Até agora, o script só foi testado com uma nota do Atacadão. Notas de outras
lojas podem aparecer como `ERRO` se o layout for diferente.

Mantenha os PDFs em `data/`. Se o formato do banco mudar, eles permitem recriá-lo:
apague `pricetrail.sqlite` e rode a importação de novo.

## Juntar o mesmo produto (products.json)

O mesmo produto pode aparecer com códigos diferentes. Nada é juntado sozinho,
porque a mesma descrição às vezes cobre tamanhos diferentes. Para revisar:

```bash
python3 suggest_products.py        # mostra candidatos e escreve products.suggested.json
```

Ou, mais fácil, use a página de agrupamento, em <http://127.0.0.1:8000/groups> com o
servidor ligado. Ela lê os produtos e os grupos direto do banco.

Cada produto tem "Ver nota (N)", com a lista das notas onde ele aparece e um link para
abrir o PDF. O caminho de cada PDF fica no banco: se você renomear ou mover o arquivo
dentro de `data/`, rode a importação de novo e o link volta a funcionar. Use Ctrl+F no
PDF para achar o item.

Nela você marca produtos (ou clica numa sugestão), dá um nome e cria o grupo. Dá para
renomear, tirar produtos e excluir grupos. Cada alteração é salva direto no banco
(`PUT /api/groups`); se o servidor recusar, a página mostra o motivo e mantém a edição
na tela. O gráfico reflete os grupos ao recarregar.

Manualmente: copie os grupos que são mesmo produto para `products.json` (grupos com `!!` costumam
ser tamanhos diferentes) e rode `python3 chart.py`. Cada referência é um código de
loja (`"75315333:11757"`, 8 dígitos do CNPJ + código) ou uma descrição exata:

```json
{"Detergente Ypê": ["75315333:11757", "75315333:13453", "75315333:22392"]}
```

Produtos que você já decidiu que são diferentes ficam em `products.rejected.json`
(mesmo formato) e deixam de aparecer nas sugestões.

Produtos com unidades diferentes não são juntados. Sem `products.json`, tudo fica como antes.

## Testes

Precisam das dependências de `requirements.txt`. Os testes usam notas sintéticas
(nenhum PDF real):

```bash
python3 -m unittest discover -s tests -t .
```

Quando uma nota nova der erro no importador, copie o trecho de texto que falhou
para `tests/fixtures.py` e adicione um teste antes de corrigir o parser.

Um hook `pre-push` roda os testes antes de cada push. Ele fica em `.githooks/` e
precisa ser ativado uma vez por clone:

```bash
git config core.hooksPath .githooks
```

Lojas sem cadastro geram um aviso (uma vez por raiz de CNPJ) no terminal e no log durante a importação; cadastre nome e categoria na seção "Lojas" da página `/groups`.

## Planejado

- [Normalização de produtos](docs/plano-normalizacao-de-produtos.md) (feito, manual)
- [Filtros e destaques no gráfico](docs/plano-filtros-do-grafico.md) (feito)
- [Busca por código de barras](docs/handoff-codigo-de-barras.md)
