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

Com o servidor ligado (veja abaixo), também dá para importar pela página
<http://127.0.0.1:8000/import>: escolha ou arraste um ou vários PDFs. Cada nota nova é
guardada em `data/` como `AAAA-MM-DD_<chave>.pdf`; arquivo com erro não é guardado.
O envio tem limite de 20 MB; o servidor loga em JSON (stdout até INFO, stderr de WARNING em diante, nível em `LOG_LEVEL`), sem nomes de arquivo, lojas nem textos de notas.

## Ver o gráfico

O login é obrigatório, também no servidor local. Uma vez: copie `.env.example` para `.env`,
troque `AUTH_USERNAME`, `AUTH_PASSWORD_HASH` (gere com `python3 -m pricetrail hash-password`) e
`SECRET_KEY`, e ponha `SESSION_COOKIE_SECURE=0` (local é HTTP); deixe `DB_PATH` e `DATA_DIR`
comentados. O `make` carrega o `.env`. Sem essas variáveis o servidor recusa subir.

Inicie o servidor local e abra <http://127.0.0.1:8000/> no navegador:

```bash
make serve
```

(`python3 -m pricetrail serve` também funciona, se o ambiente já tiver as variáveis.)

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

O banco fica em `pricetrail.sqlite` (em produção, `/data/app.db`):

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

Os PDFs não entram no repositório; guarde-os à parte. Em produção, o backup do banco é outro (veja "Produção (Docker)").

## Produção (Docker)

A imagem (gunicorn, 1 worker) é publicada pelo CI em `ghcr.io/c0nant/price_trail` e roda atrás do
Traefik da VPS, em `compras.conantorres.dev`. O `docker-compose.yml` não publica porta: todo o
tráfego entra pela Cloudflare e pelo Traefik, pela rede externa `proxy`. A VPS nunca compila.
O fluxo local continua sendo `make serve`.

**Réplica única, disco local.** O SQLite tem um escritor por vez e o app foi feito para um só
container: nunca escale o serviço (`--scale`, réplicas) e mantenha o volume `price_trail_data` em
disco local, nunca em NFS (o WAL não funciona direito em rede).

### Variáveis (`.env`)

Copie `.env.example` para `.env` (nunca versionado; na VPS fica ao lado do `docker-compose.yml`).
O login é sempre ligado: sem `AUTH_USERNAME`, `AUTH_PASSWORD_HASH` e `SECRET_KEY` o servidor
recusa subir.

| Variável | Para quê |
| --- | --- |
| `AUTH_USERNAME` | Usuário único do login. |
| `AUTH_PASSWORD_HASH` | Hash argon2 da senha, **entre aspas simples** (o `$` seria interpolado pelo Compose). |
| `SECRET_KEY` | Assina o cookie de sessão; trocar derruba as sessões. |
| `SESSION_COOKIE_SECURE` | `1` em produção; `0` só para testar por HTTP. |
| `ALLOWED_HOSTS` | Hosts aceitos, separados por vírgula; mantenha `127.0.0.1` (healthcheck). |
| `FORWARDED_ALLOW_IPS` | Sub-rede da rede `proxy` (`docker network inspect proxy`, campo `Subnet`): só ela pode mandar `X-Forwarded-*`. É dela que vem o IP real do cliente no bloqueio de login. |
| `LOG_LEVEL` | `DEBUG`, `INFO` (padrão), `WARNING` ou `ERROR`. |
| `IMAGE_TAG` | Tag da imagem: `latest` (padrão) ou o SHA de um commit. |
| `BACKUP_KEEP` | Quantos backups manter em `/data/backups` (padrão 14). |

`DB_PATH` e `DATA_DIR` já vêm certos na imagem (`/data/app.db` e `/data/pdfs`).

Gerar o `SECRET_KEY` e o hash da senha:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
docker compose run --rm web python -m pricetrail hash-password   # pede a senha duas vezes, sem eco
```

O segundo comando, local, é `python3 -m pricetrail hash-password`. Cole o resultado no `.env`
entre aspas simples.

O login erra 3 vezes seguidas por IP e bloqueia esse IP por 20 minutos; 10 falhas em 24h, somando
todos os IPs, bloqueiam tudo (inclusive a senha certa) até a falha mais antiga sair da janela.
Os eventos saem nos logs (`login_falhou`, `login_bloqueado`, `teto_global_atingido`).

### Subir local com volume de teste

Para conferir a imagem sem tocar na VPS, use um projeto, uma imagem e um volume descartáveis, com
um override só local (não faz parte do deploy). O `.env` de teste precisa de `SESSION_COOKIE_SECURE=0`
(HTTP) e de `FORWARDED_ALLOW_IPS` com a sub-rede da rede de teste.

```bash
docker build -t price_trail:teste .
docker network create proxy_teste
docker network inspect proxy_teste | grep Subnet     # vai em FORWARDED_ALLOW_IPS no .env
cat > docker-compose.teste.yml <<'EOF'
services:
  web:
    image: price_trail:teste
    labels: !reset []
    ports:
      - "127.0.0.1:8000:8000"
networks:
  proxy:
    name: proxy_teste
EOF
docker compose -p pt_teste -f docker-compose.yml -f docker-compose.teste.yml up -d
docker compose -p pt_teste ps          # espera o "healthy"
docker compose -p pt_teste logs web    # uma linha JSON por evento, inclusive o acesso do gunicorn
```

Abra <http://127.0.0.1:8000/>. Para limpar tudo: `docker compose -p pt_teste -f docker-compose.yml
-f docker-compose.teste.yml down -v && docker network rm proxy_teste`.

### Logs

Tudo sai em JSON, uma linha por evento: stdout até `INFO` (inclui o acesso do gunicorn, sem query
string nem corpo) e stderr de `WARNING` em diante. O driver é `json-file`, com rotação de 10 MB x 5
arquivos. Os logs não levam nomes de arquivo, lojas, CNPJ completo nem senhas.

### Backup e restauração

`python -m pricetrail backup` faz `VACUUM INTO` com o app rodando (nunca copia o arquivo, que tem
`-wal`/`-shm`) e grava `/data/backups/app-AAAAMMDD-HHMMSS.db`. Mantém os `BACKUP_KEEP` mais novos
(padrão 14, definido no `.env`) e loga uma linha JSON com nome, tamanho, quantos apagou e duração.
Roda como o usuário da imagem, com `read_only`: só `/data` é gravável.

Cron da VPS (`crontab -e`), todo dia às 03:15:

```
15 3 * * * cd /opt/apps/price_trail && docker compose exec -T web python -m pricetrail backup >> /var/log/price_trail-backup.log 2>&1
```

Para testar à mão, rode o mesmo comando sem o `>>` e confira o arquivo:
`docker compose exec -T web ls -l /data/backups`.

Restaurar um backup (o volume é `price_trail_data`; troque `app-AAAAMMDD-HHMMSS.db` pelo arquivo escolhido):

```bash
cd /opt/apps/price_trail
docker compose stop web
docker compose run --rm --no-deps --user root --entrypoint sh web -c \
  'cp /data/backups/app-AAAAMMDD-HHMMSS.db /data/app.db \
   && rm -f /data/app.db-wal /data/app.db-shm \
   && chown 10001:10001 /data/app.db'
docker compose up -d
```

O `-wal`/`-shm` antigo precisa sumir: misturado com o `app.db` restaurado, corrompe o banco.
Os backups ficam no mesmo volume do banco; para proteção contra perda do disco, copie
`/data/backups` para fora da VPS (por exemplo `docker compose cp web:/data/backups ./backups` e depois `rsync`).
Os PDFs (`/data/pdfs`) não entram nesse backup, que cobre só o SQLite: guarde-os à parte.

### Atualizar e voltar uma versão (rollback)

O cron da VPS faz `docker compose pull && docker compose up -d`. Cada push na `main` publica
`:latest` e `:<sha do commit>`. Para voltar uma versão, fixe o SHA no `.env` e suba de novo:

```bash
# .env
IMAGE_TAG=<sha do commit bom>
docker compose pull && docker compose up -d
```

Volte a `IMAGE_TAG=latest` para seguir a versão mais nova. O banco só migra para frente: depois de
uma versão que migrou o banco, voltar a imagem não desfaz a migração (restaure um backup se precisar).

### Migrar os dados atuais para o volume

`pricetrail.sqlite` vira `app.db` e a pasta `data/` vira `pdfs/`, mantendo as subpastas (o caminho de
cada nota é relativo a ela). **Feche o servidor local antes**: o banco está em WAL e o que ainda está
no `-wal` se perderia numa cópia crua. Uma cópia consistente, mesmo com ele ligado, sai de:

```bash
mkdir -p migracao
python3 -c "import sqlite3; sqlite3.connect('pricetrail.sqlite').execute(\"VACUUM INTO 'migracao/app.db'\")"
cp -a data migracao/pdfs
```

Copie a pasta `migracao/` para a VPS e, com o serviço parado (ou recém-criado, veja o checklist),
leve tudo para o volume com um container temporário:

```bash
docker compose stop web
docker compose run --rm --no-deps --user root -v "$PWD/migracao:/origem:ro" --entrypoint sh web -c \
  'cp /origem/app.db /data/app.db \
   && rm -f /data/app.db-wal /data/app.db-shm \
   && mkdir -p /data/pdfs && cp -a /origem/pdfs/. /data/pdfs/ \
   && chown -R 10001:10001 /data/app.db /data/pdfs'
docker compose up -d
```

### Checklist fora do código

1. **Cloudflare:** registro DNS `compras` (A/AAAA para o IP da VPS), com a nuvem laranja.
2. **VPS:**
   - criar `/opt/apps/price_trail/` e copiar `docker-compose.yml` e o `.env` (gere `SECRET_KEY` e o hash como acima);
   - `docker network inspect proxy` e colocar a sub-rede em `FORWARDED_ALLOW_IPS`;
   - `docker login ghcr.io` com um token `read:packages`, se ainda não fez;
   - `docker compose up -d` uma vez, para criar o volume `price_trail_data`;
   - copiar o banco atual (como `app.db`) e a pasta `data/` (como `pdfs/`) para o volume, com o container temporário acima (que já faz o `chown -R 10001:10001`);
   - `docker compose restart`.
3. **Cron da VPS:** agendar o backup diário (linha acima).
4. Considerar o **Cloudflare Access** na frente de `compras.conantorres.dev`, já que são dados de compras: a autenticação da Cloudflare antes da do app.
5. Medir a memória estável com `docker stats` depois de uns dias e ajustar `mem_limit` (regra da casa: limite ≥ uso / 0,7).

## Estilo (Tailwind)

O visual vem de um único CSS, `pricetrail/web/app.css`, gerado pelo Tailwind e
commitado (rodar o servidor não precisa do Tailwind). Só quem muda classes nos
HTMLs/JS de `pricetrail/web/` precisa regerar (as classes também ficam em
strings dos JS, então editar classes no JS também exige `make css`). Usamos a CLI standalone do
Tailwind **v3.4.17** (sem Node). Baixe o binário para `bin/tailwindcss`
(ignorado pelo git):

```bash
mkdir -p bin
curl -sL -o bin/tailwindcss https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.17/tailwindcss-linux-x64
chmod +x bin/tailwindcss
make css          # gera pricetrail/web/app.css minificado
make css-watch    # regera a cada mudança
```

Entrada em `tailwind/input.css` (cores claro/escuro como variáveis CSS) e
configuração em `tailwind.config.js`. Commite o `app.css` junto com a mudança.

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
