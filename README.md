# pricetrail

Guarda o histórico de preços das suas compras. Importa os PDFs de NFC-e da
Consulta Pública da SEF/SC para um banco SQLite e mostra os preços em um servidor local.

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
3. Rode a importação:

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
primeiros dígitos do CNPJ (iguais em todas as filiais). Ela é editada na seção "Lojas" da página `/groups`. Loja sem cadastro aparece com o nome da nota e a
categoria "Outros".

A mesma mercadoria em duas filiais da mesma rede é um produto só: um produto é a raiz
do CNPJ, o código e a unidade.

## O que aparece na saída

| Saída    | Significado                                     |
| -------- | ----------------------------------------------- |
| `NOVA`   | Nota importada                                  |
| `JÁ TEM` | Nota já estava no banco e foi ignorada          |
| `ERRO`   | Nota não importada; o motivo aparece na mensagem |

Antes de gravar, a importação confere a chave de acesso, a quantidade de itens e os
totais da nota. Se algo não bater, a nota inteira fica de fora e os demais
arquivos continuam sendo processados. Nesse caso, o comando termina com código 1.

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

O leitor de notas foi feito para o layout das notas de supermercado e já foi usado também com notas de farmácia.
Uma nota de outra loja pode aparecer como `ERRO` se o layout for diferente; nesse caso, veja a seção Testes.

O banco é a fonte da curadoria (grupos, pares rejeitados e lojas): não o apague sem
antes exportá-la. Veja a seção seguinte.

## Juntar o mesmo produto

O mesmo produto pode aparecer com códigos diferentes. Nada é juntado sozinho,
porque a mesma descrição às vezes cobre tamanhos diferentes. Use a página de
agrupamento, em <http://127.0.0.1:8000/groups> com o servidor ligado. Ela lê os
produtos, as sugestões e os grupos direto do banco.

Cada produto tem "Ver nota (N)", com a lista das notas onde ele aparece e um link para
abrir o PDF. O caminho de cada PDF fica no banco: se você renomear ou mover o arquivo
dentro de `data/`, rode a importação de novo e o link volta a funcionar. Use Ctrl+F no
PDF para achar o item.

Nela você marca produtos (ou clica numa sugestão), dá um nome e cria o grupo. Dá para
renomear, tirar produtos e excluir grupos, e rejeitar pares que parecem iguais mas não
são (eles deixam de ser sugeridos). Cada alteração é salva direto no banco; se o
servidor recusar, a página mostra o motivo e mantém a edição na tela. O gráfico reflete
os grupos ao recarregar.

**Depois de editar grupos, rejeições ou lojas, atualize o backup.** O banco não vai para
o git; o `curadoria.json` vai:

```bash
python3 -m pricetrail export
git add curadoria.json
git commit -m "Atualiza curadoria"
```

Cada referência é um código de loja (`75315333:11757`, 8 dígitos do CNPJ + código).
Produtos com unidades diferentes não são juntados.

## Backup e recriação do banco

Grupos, pares rejeitados e lojas existem só no banco. O arquivo `curadoria.json`, versionado
no repositório, é a cópia de segurança deles:

```bash
python3 -m pricetrail export    # grava curadoria.json (use --out para outro caminho)
python3 -m pricetrail restore   # substitui a curadoria do banco pelo arquivo
```

Depois de mudar grupos, rejeições ou lojas, rode `export` de novo e faça commit do
`curadoria.json` atualizado.

Para recriar o banco do zero (outra máquina, ou banco perdido):

1. Coloque os PDFs em `data/` e rode `python3 -m pricetrail import`.
2. Rode `python3 -m pricetrail restore curadoria.json`.

Os PDFs não entram no repositório; guarde-os à parte.

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
