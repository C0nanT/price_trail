# Docker e produção em compras.conantorres.dev

Status: ready-for-agent

## Problem Statement

O Price Trail só roda na minha máquina: `python -m pricetrail serve` sobe o servidor de desenvolvimento do Flask em `127.0.0.1:8000`, com o banco e os PDFs na pasta do projeto. Quero acessar o histórico de preços e a lista de compras de qualquer lugar, em `compras.conantorres.dev`, na VPS que já tem a borda (Traefik + Loki + Alloy) atrás da Cloudflare. Hoje isso não é possível nem seguro:

- Não há imagem Docker, compose de produção nem CI publicando imagem no GHCR. O deploy da VPS (cron com `pull` + `up -d`) não tem o que puxar.
- O banco e os PDFs ficam em caminhos fixos derivados da pasta do projeto. Dentro de um container sem volume, cada deploy apagaria tudo.
- Não existe login. Qualquer pessoa com a URL veria e alteraria meus dados de compras.
- O servidor recusa qualquer `Host` que não seja localhost (proteção contra DNS rebinding), então atrás do Traefik tudo vira 403.
- A checagem de `Origin` do upload compara com `request.host_url`. Atrás do proxy o app enxerga `http://` e o navegador manda `https://`, então todo upload seria recusado.
- O log vai para um arquivo (`pricetrail.log`), em texto livre, e inclui nome de loja, nome de arquivo e texto de erro do parser. O Alloy só lê stdout/stderr dos containers, e dados de compras não podem ir para o Loki.
- Não há endpoint de saúde para o healthcheck do Docker.
- Não há backup do banco.

## Solution

O projeto ganha um `Dockerfile`, um `docker-compose.yml` de produção, `.dockerignore`, `.env.example`, um workflow do GitHub Actions e um script de backup. Abro `https://compras.conantorres.dev`, vejo uma tela de login, entro com o usuário e a senha definidos no `.env` da VPS, e uso o gráfico, `/groups`, `/import` e `/lista` como uso hoje em localhost.

O banco (`/data/app.db`) e os PDFs (`/data/pdfs/`) ficam num volume nomeado, que sobrevive a deploy, `down`/`up` e troca de imagem. A cada push na `main`, o CI publica `ghcr.io/c0nant/price_trail:<sha>` e `:latest`, e o cron da VPS faz o resto. Para voltar uma versão, fixo `IMAGE_TAG` no `.env`.

Os logs saem em JSON no stdout/stderr, uma linha por evento, sem dados de compras. Eventos de login (sucesso, falha, bloqueio) trazem IP real e usuário. O IP real é escolhido do `X-Forwarded-For` ignorando as faixas da Cloudflare, e o login bloqueia o IP por 20 min após 3 erros, com um teto global de falhas em 24h. Os contadores ficam no SQLite e sobrevivem a restart.

Localmente, `make serve` continua funcionando, também com login: as variáveis de autenticação vão num `.env` local. Ver "Implementation Decisions > Configuração".

## User Stories

### Acesso e login

1. Como dono do site, quero que toda página e toda API exijam login, para que ninguém com a URL veja meus dados de compras.
2. Como dono do site, quero uma tela de login com usuário e senha, para entrar pelo navegador do celular ou do computador.
3. Como dono do site, quero definir usuário e hash da senha só no `.env` da VPS, para não ter segredo no repositório nem na imagem.
4. Como dono do site, quero um subcomando que gere o hash argon2 de uma senha digitada no terminal, para preencher o `.env` sem escrever a senha em arquivo nem no histórico do shell.
5. Como dono do site, quero que a mensagem de erro seja a mesma para usuário errado e senha errada, para não revelar qual dos dois existe.
6. Como dono do site, quero que o tempo de resposta não denuncie usuário errado (o hash é verificado mesmo quando o usuário não confere), para não vazar a informação por tempo.
7. Como dono do site, quero que o cookie de sessão seja `HttpOnly; Secure; SameSite=Lax`, para que script de página e site de terceiro não o usem.
8. Como dono do site, quero que o segredo de assinatura da sessão venha do `.env`, para que trocar o segredo derrube todas as sessões.
9. Como dono do site, quero um botão de sair, para encerrar a sessão num aparelho emprestado.
10. Como dono do site, quero que a sessão dure um tempo razoável (ex.: 30 dias) sem eu precisar entrar toda vez no celular, para o uso no mercado ser rápido.
11. Como dono do site, quero ser levado à tela de login quando a sessão expirar no meio do uso (a API responde 401 e a página redireciona), para não ver um erro genérico de "não foi possível carregar".
12. Como dono do site, quero voltar à página em que estava depois de entrar, para não navegar de novo até `/lista`.
13. Como dono do site, quero que o formulário de login tenha proteção CSRF, para que outro site não me faça entrar numa sessão de terceiro.
14. Como dono do site, quero que as APIs que alteram dados continuem protegidas contra envio de outro site (JSON obrigatório, cabeçalho próprio no upload, `Origin` conferido), para não regredir o que já existe.

### Bloqueio de tentativas

15. Como dono do site, quero que um IP com 3 senhas erradas fique bloqueado por 20 minutos, para frear quem tenta adivinhar a senha.
16. Como dono do site, quero que, somando todos os IPs, um teto de falhas numa janela de 24h bloqueie qualquer tentativa (até a senha certa) até a falha mais antiga expirar, para que um ataque distribuído não teste senhas sem limite.
17. Como dono do site, quero ver quantos minutos faltam para tentar de novo, para saber quanto esperar.
18. Como dono do site, quero ser avisado na tentativa que é a última antes do bloqueio, para ter cuidado ao digitar.
19. Como dono do site, quero que os contadores fiquem no SQLite, para que um deploy ou restart não zere o bloqueio.
20. Como dono do site, quero que um flood de IPs forjados não faça a tabela de tentativas crescer sem limite, para o disco e o banco não sofrerem.
21. Como dono do site, quero que entradas expiradas sejam limpas, para a tabela ficar pequena.
22. Como dono do site, quero que um login certo zere a contagem do meu IP (mas não a global), para eu não ficar perto do bloqueio depois de errar uma vez.
23. Como dono do site, quero que requisições paralelas não escapem do bloqueio, para que um atacante não dispare 50 tentativas de uma vez antes do contador subir.

### IP real do cliente

24. Como dono do site, quero que o IP registrado seja o do visitante e não o do Traefik nem o da Cloudflare, para os logs e o bloqueio fazerem sentido.
25. Como dono do site, quero que um `X-Forwarded-For` forjado pelo cliente não troque o IP escolhido, para que ninguém fuja do bloqueio mudando um cabeçalho.
26. Como dono do site, quero que IPv6 funcione igual a IPv4, para visitantes em redes móveis.
27. Como dono do site, quero que as faixas da Cloudflare no código sejam as mesmas do `traefik.yml` da borda, com um comentário dizendo que mudam juntas, para não divergirem em silêncio.

### Deploy e operação

28. Como dono do site, quero que um push na `main` publique a imagem no GHCR com a tag do SHA e `latest`, para o cron da VPS pegar a versão nova sozinho.
29. Como dono do site, quero fixar `IMAGE_TAG` no `.env` para um SHA, para voltar uma versão quebrada sem compilar nada na VPS.
30. Como dono do site, quero que a VPS nunca compile a imagem (compose sem `build:`), para o deploy ser só `pull` + `up -d`.
31. Como dono do site, quero que o site entre pelo Traefik com as peças da borda (`so-cloudflare`, `limite-taxa`, `seguranca`, `compressao`) e o certificado curinga já emitido, para seguir o mesmo padrão dos outros projetos.
32. Como dono do site, quero que o container não publique porta no host, para todo tráfego passar pela Cloudflare e pelo Traefik.
33. Como dono do site, quero que o container reinicie sozinho se cair, para o site voltar sem eu entrar na VPS.
34. Como dono do site, quero um healthcheck que abra o SQLite e rode `SELECT 1`, para o Docker marcar o container como `unhealthy` quando o banco não abrir.
35. Como dono do site, quero que o container rode como usuário não-root com UID fixo, sem novos privilégios e com sistema de arquivos só de leitura (exceto `/data` e `/tmp`), para reduzir o estrago de uma falha.
36. Como dono do site, quero um limite de memória no container, para um vazamento não derrubar os outros sites da VPS.
37. Como dono do site, quero que o nome do projeto no compose seja fixo, para o nome do volume e o rótulo `projeto` no Loki não dependerem do nome da pasta na VPS.

### Dados

38. Como dono do site, quero que banco e PDFs fiquem num volume persistente fora da imagem, para nenhum deploy apagar meus dados.
39. Como dono do site, quero que os caminhos do banco e da pasta de PDFs venham de variáveis de ambiente, para o mesmo código rodar local e no container.
40. Como dono do site, quero levar o banco e os PDFs atuais para o volume da VPS e ver tudo funcionando, inclusive os links dos PDFs nas notas.
41. Como dono do site, quero que as migrações rodem na subida de forma idempotente, para uma versão nova com schema novo funcionar sem passo manual.
42. Como dono do site, quero o banco em WAL, com `busy_timeout` e chaves estrangeiras ligadas em toda conexão, para leituras e escrita conviverem sem `database is locked`.
43. Como dono do site, quero um script de backup que use `VACUUM INTO` (nunca `cp` com o app rodando), grave em `/data/backups/` com data no nome e mantenha só os últimos N, para ter cópias consistentes.
44. Como dono do site, quero instruções de como agendar o backup no cron da VPS e como restaurar um backup, para agir rápido quando precisar.
45. Como dono do site, quero que `*.db`, `*.sqlite`, seus `-wal`/`-shm` e a pasta `data/` nunca entrem no git nem na imagem, para não vazar dados de compras.

### Logs

46. Como dono do site, quero logs só em stdout/stderr, em JSON de uma linha por evento (`ts`, `level`, `msg`, `logger`, `exc_info` quando houver), para o Alloy mandar ao Loki e eu filtrar por campo.
47. Como dono do site, quero erros e tracebacks no stderr, para separar falha de ruído.
48. Como dono do site, quero o nível de log por variável de ambiente (`LOG_LEVEL`, padrão `INFO`), para ligar `DEBUG` sem nova imagem.
49. Como dono do site, quero o log de acesso do gunicorn também no stdout, em JSON, para ver status e duração de cada request.
50. Como dono do site, quero que os logs nunca tenham valores, itens, nomes de loja, nomes de arquivo enviados, texto de nota, senhas, corpo de requisição nem SQL com parâmetros, para dados de compras não irem para o Loki.
51. Como dono do site, quero os eventos de login (sucesso, falha, bloqueio, teto global atingido) com IP e usuário, para investigar tentativas de invasão.
52. Como dono do site, quero que o upload logue só contagens e status (novas, já existentes, com erro) e IDs (chave de acesso), para saber o que aconteceu sem expor o conteúdo.
53. Como dono do site, quero que o compose use o driver `json-file` com rotação, para o Alloy ler e o disco não encher.

### Desenvolvimento local

54. Como desenvolvedor, quero continuar rodando `make serve`, `make import`, `make export`, `make restore` e `make test` localmente como hoje, para a mudança não atrapalhar o fluxo atual.
55. Como desenvolvedor, quero que a suíte de testes continue passando com o login ligado, com a base dos testes já entregando um cliente logado, para não reescrever cada teste.
56. Como desenvolvedor, quero testes de `pick_client_ip` e do bloqueio de login, para mudar esse código com segurança.

## Implementation Decisions

### Nomes e identificadores

- `<projeto>` = **`price_trail`** (nome do repositório em minúsculas). Vale para o `name:` do compose, o nome do router e do serviço no Traefik e a imagem `ghcr.io/c0nant/price_trail`.
- Volume nomeado `data`, que o compose cria como `price_trail_data`. Nome do serviço: `web` (vira o rótulo `servico` no Loki).
- Porta interna: **8000** (a mesma do `make serve`).

### Configuração (variáveis de ambiente)

Toda configuração do servidor vem do ambiente. Os padrões preservam o uso local de hoje, e o `.env.example` documenta cada variável:

| Variável | Uso | Padrão local | Produção |
|---|---|---|---|
| `DB_PATH` | arquivo SQLite | `pricetrail.sqlite` na raiz do projeto | `/data/app.db` |
| `DATA_DIR` | pasta dos PDFs (uploads e `/notes/...`) | `data/` na raiz | `/data/pdfs` |
| `ALLOWED_HOSTS` | hosts aceitos, separados por vírgula | `localhost,127.0.0.1` | `compras.conantorres.dev,localhost,127.0.0.1` |
| `AUTH_USERNAME` | usuário único | vazio | definido |
| `AUTH_PASSWORD_HASH` | hash argon2 da senha | vazio | definido (entre aspas simples no `.env`, porque o hash tem `$` e o Compose interpolaria) |
| `SECRET_KEY` | assina o cookie de sessão | vazio | aleatório, ≥ 32 bytes |
| `SESSION_COOKIE_SECURE` | flag `Secure` do cookie | `1` | `1` (dá para pôr `0` só para testar local por HTTP) |
| `FORWARDED_ALLOW_IPS` | quem pode mandar `X-Forwarded-*` | `127.0.0.1` | sub-rede da rede `proxy` (lida com `docker network inspect proxy`) |
| `LOG_LEVEL` | nível do log | `INFO` | `INFO` |
| `IMAGE_TAG` | tag da imagem no compose | — | `latest` ou um SHA |

- Os argumentos de linha de comando (`--db`, `--data`, `--port`) continuam funcionando e têm precedência sobre o ambiente. Sem nenhum dos dois, valem os padrões acima.
- **Login sempre ligado.** Sem `AUTH_USERNAME`/`AUTH_PASSWORD_HASH`/`SECRET_KEY`, o servidor recusa subir com mensagem clara (nunca abre sem autenticação por esquecimento). Para desenvolvimento local, o README explica como gerar um `.env` local com o subcomando de hash. O `Makefile` carrega o `.env` se ele existir (`-include .env` + `export`), sem dependência nova como `python-dotenv`. Local por HTTP precisa de `SESSION_COOKIE_SECURE=0`.
- `/health` aceita o host `127.0.0.1` (o healthcheck roda dentro do container), por isso `127.0.0.1` fica em `ALLOWED_HOSTS` também em produção.

### Autenticação (usuário único)

- Um único usuário, definido no `.env`: `AUTH_USERNAME` + `AUTH_PASSWORD_HASH`. Não há tabela de usuários nem cadastro. Nos logs, o "id do usuário" é o `AUTH_USERNAME`.
- Novo subcomando `pricetrail hash-password`: pede a senha duas vezes sem eco (`getpass`) e imprime o hash argon2 pronto para colar no `.env`. Roda local ou com `docker compose run --rm web python -m pricetrail hash-password`.
- Nova dependência: `argon2-cffi` (versão fixa em `requirements.txt`, junto com `gunicorn`).
- Comparação: o hash é verificado **sempre**, mesmo quando o usuário não confere, e o usuário é comparado em tempo constante. A resposta de erro é idêntica nos dois casos.
- Sessão: a sessão assinada do próprio Flask (cookie), com `SECRET_KEY` do ambiente, `SESSION_COOKIE_HTTPONLY`, `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_SAMESITE=Lax` e vida de 30 dias (`PERMANENT_SESSION_LIFETIME`). A sessão guarda só a marca de logado e o token CSRF.
- Rotas novas:
  - `GET /login`: página estática (mesmo padrão das outras páginas, com Tailwind/`app.css`).
  - `GET /api/session`: devolve o token CSRF da sessão (cria um, se não houver) e se está logado. A página de login busca o token por aqui antes de enviar o formulário, já que as páginas são estáticas, sem template.
  - `POST /api/login`: corpo JSON `{username, password, next}` com o cabeçalho `X-CSRF-Token`. Respostas: 200 (logado, devolve `next` saneado: só caminhos relativos do próprio site), 401 (credenciais inválidas, com `lockMinutesIfWrong` quando a próxima falha bloqueia), 429 (bloqueado, com os minutos restantes), 403 (CSRF inválido).
  - `POST /api/logout`: limpa a sessão, exige o token CSRF.
- Controle de acesso: um `before_request` exige sessão em tudo, menos `/login`, `/api/session`, `/api/login`, `/health` e `/static/*` (a página de login precisa do CSS e do JS; os estáticos não têm dados). Sem sessão: página HTML redireciona (302) para `/login?next=<caminho>`, rota `/api/*` e `/notes/*` respondem 401 JSON.
- `fetchJson` (helper comum das páginas) e o upload do `/import` tratam 401 redirecionando para `/login?next=<página atual>`. Cada página ganha um link "Sair".
- CSRF:
  - Login e logout: token por sessão no cabeçalho `X-CSRF-Token` (comparação em tempo constante).
  - APIs que alteram dados: mantêm a defesa atual (corpo `application/json` obrigatório, que força preflight de CORS; cabeçalho `X-Pricetrail` no upload) mais `SameSite=Lax`. Além disso, toda requisição que altera dados (POST/PUT/DELETE) com `Origin` presente precisa de `Origin` igual ao próprio site, generalizando a regra que hoje só vale no upload.

### Bloqueio de tentativas de login

- Semântica copiada de `conan-torres/src/lib/reader/rate-limit-core.ts`:
  - Por IP: 3 falhas → bloqueio de 20 min. A entrada expira 20 min após a última falha (ou no fim do bloqueio).
  - Global: no máximo **10 falhas** em 24h somando todos os IPs (premissa herdada da referência: o pedido não deu o número). Ao atingir, toda tentativa é recusada, mesmo com a senha certa, até a falha mais antiga sair da janela. Ao bater o teto, um log de aviso único.
  - Bloqueio por IP e teto global dão a mesma resposta. Os minutos informados são o maior dos dois.
  - A tentativa é **contada como falha antes** de comparar a senha. Se a senha estiver certa, a contagem do IP é apagada, e a global fica.
  - Teto de **10.000 IPs** rastreados: passando disso, os menos ativos recentemente são descartados.
- Persistência no SQLite, nova **migração 5** com duas tabelas:
  - `login_attempts(ip TEXT PRIMARY KEY, failures INTEGER, last_failure_at INTEGER, locked_until INTEGER NULL)`, com índice em `last_failure_at` (limpeza e descarte dos menos ativos).
  - `login_failures(at INTEGER)`, com índice em `at` (janela global). Linhas fora da janela são apagadas a cada tentativa.
  - Tempos em epoch (segundos). O relógio vem de uma função do módulo, que os testes substituem.
- Toda a sequência (limpar expirados, conferir bloqueio, contar a tentativa, aplicar o teto de IPs) roda numa transação `BEGIN IMMEDIATE`, para que requisições paralelas, em threads ou workers, não passem juntas pela checagem.
- O limite geral de requisições (5 req/s por IP) é do Traefik (`limite-taxa@file`) e **não** é reimplementado.

### IP real do cliente

- Função pura `pick_client_ip(x_forwarded_for, x_real_ip) -> str` num módulo próprio, só com biblioteca padrão (`ipaddress`):
  - Percorre o `X-Forwarded-For` da direita para a esquerda, descarta itens que não são IP válido e itens dentro das faixas da Cloudflare, e devolve o primeiro que sobrar.
  - Sem item útil: o `X-Real-IP` (aparado), depois `"unknown"`.
- As faixas ficam numa constante, idênticas às de `trustedIPs: &ips_cloudflare` em `traefik-default/traefik/traefik.yml`, com comentário dizendo que as duas listas mudam juntas e a data da conferência.
- O app nunca usa `request.remote_addr` puro nem o primeiro item do `X-Forwarded-For` para identificar o cliente. O IP escolhido alimenta o bloqueio e os logs de login.

### Proxy e cabeçalhos encaminhados

- O gunicorn roda com `forwarded_allow_ips` = `FORWARDED_ALLOW_IPS` (a sub-rede da rede `proxy`) e trata `X-Forwarded-Proto: https`, para que `request.scheme`/`host_url` reflitam `https://compras.conantorres.dev`. É isso que conserta a checagem de `Origin` e o cookie `Secure`. Cabeçalho vindo de qualquer outro IP é ignorado.
- `ALLOWED_HOSTS` passa a vir do ambiente. A proteção contra DNS rebinding continua.

### Servidor de produção

- gunicorn com **1 worker** da classe `gthread` e 4 threads (o Flask atende uma conexão SQLite por request; 1 escritor por vez). Bind em `0.0.0.0:8000`, `--worker-tmp-dir /tmp` (tmpfs).
- O gunicorn importa uma fábrica que monta o app a partir do ambiente, reaproveitando `create_app`. A migração roda na subida, e com mais de um worker cada um tentaria migrar, o que é seguro (`BEGIN IMMEDIATE` mais nova checagem de `user_version`), mas fica 1 worker.
- `database is locked`: `busy_timeout=5000` em toda conexão. Se mesmo assim estourar, o erro vira 503 JSON ("banco ocupado, tente de novo") com log de aviso, em vez de 500 com traceback.

### Banco SQLite

- `connect()` passa a ligar em toda conexão: `PRAGMA journal_mode=WAL`, `PRAGMA busy_timeout=5000`, `PRAGMA foreign_keys=ON` (WAL hoje só é ligado dentro de `migrate`; fica gravado no arquivo, mas a intenção passa a ser explícita).
- O app nunca cria o arquivo fora de `DB_PATH` e cria a pasta pai se faltar (`/data` já existe pelo volume).
- Um único container acessa o banco. O compose não declara réplicas, e o README avisa: nunca escalar, volume em disco local (não NFS).
- Migrações seguem o mecanismo atual (`user_version`), com a migração 5 descrita acima.

### Logs

- Um módulo de configuração de log com um formatter JSON feito com `json.dumps` (sem dependência nova): campos `ts` (ISO 8601 UTC), `level`, `logger`, `msg`, `exc_info` (traceback formatado, quando houver) e campos extras explícitos passados por `extra=` (ex.: `event`, `ip`, `user`, `status`, `duration_ms`, `access_key`).
- Dois `StreamHandler`: stdout para `DEBUG`–`INFO`, stderr para `WARNING` em diante (inclui `logger.exception`). Nível de `LOG_LEVEL`.
- O servidor **deixa de chamar** `importer.configure_log` (que põe um `FileHandler` com `propagate=False` no logger `pricetrail` e engoliria o JSON). O subcomando `import` do CLI local pode manter o arquivo `pricetrail.log`, e o `serve` deixa de ter `--log`.
- Log de acesso do gunicorn em stdout (`--access-logfile -`) com `access_log_format` em JSON (método, caminho, status, duração, tamanho, IP do `X-Forwarded-For` já tratado pelo gunicorn). Sem query string, sem corpo. Error log do gunicorn em stderr.
- Higiene de dados no caminho do servidor (upload e erros):
  - Upload: só contagens por status e, por arquivo, a chave de acesso (quando lida) e o status. Nada de nome de arquivo enviado, nome de loja, CNPJ completo nem texto de erro do parser (que pode conter linhas de item).
  - Aviso de loja sem cadastro: loga só a raiz de CNPJ, sem o nome.
  - Erro inesperado: `logger.exception` com mensagem genérica. O traceback leva só a pilha, sem valores de variáveis locais.
- Eventos de login, logger `pricetrail.auth`: `login_ok`, `login_falhou`, `login_bloqueado`, `teto_global_atingido`, `logout`, cada um com `ip` e `user` (o usuário digitado é logado **só** quando igual a `AUTH_USERNAME`; caso contrário, `user` = `"desconhecido"`, para não logar senha digitada no campo errado).
- Compose: `logging.driver: json-file` com `max-size: "10m"` e `max-file: "5"`, sem outro driver.

### Endpoint `/health`

- `GET /health`, público, sem sessão: abre uma conexão nova com o SQLite, roda `SELECT 1` e responde `200 {"status":"ok"}`. Falha: `503 {"status":"erro"}` com log de erro (sem detalhes no corpo).
- Não roda migração nem toca nos PDFs.

### Dockerfile

- Base `python:3.12-slim` com tag de patch fixa (ex.: `3.12.x-slim-bookworm`, a mais recente na hora de implementar).
- `PYTHONUNBUFFERED=1`, `PYTHONDONTWRITEBYTECODE=1`.
- `apt-get install --no-install-recommends poppler-utils` (o importador chama `pdftotext`), com limpeza do cache do apt.
- Copia `requirements.txt` e instala as dependências antes de copiar o código.
- Copia só o pacote `pricetrail/` (com `web/` e o `app.css` já gerado e versionado) e o script de backup.
- Usuário `app` com UID/GID **10001**, criado na imagem. `/data` criado com dono 10001, para o volume nomeado herdar a permissão na primeira montagem. `USER 10001`.
- `EXPOSE 8000`. `CMD` com gunicorn conforme "Servidor de produção".
- `HEALTHCHECK` com `python -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"` (sem curl/wget), intervalo 30s, timeout 5s, 3 tentativas, `start_period` 15s.
- Nenhum `.db`, `.sqlite`, PDF, `.env` ou segredo na imagem.

### docker-compose.yml (produção)

- `name: price_trail`. Serviço `web` com `image: ghcr.io/c0nant/price_trail:${IMAGE_TAG:-latest}`, sem `build:`.
- `restart: unless-stopped`, `env_file: .env`, `expose: ["8000"]`, **sem `ports:`**.
- `volumes: - data:/data` (a pasta inteira, por causa dos `-wal`/`-shm`, dos PDFs e dos backups).
- `read_only: true`, `tmpfs: /tmp`, `security_opt: [no-new-privileges:true]`.
- `mem_limit: 256m`. Estimativa: gunicorn com 1 worker gthread mais Flask fica em uns 60–90 MB, e picos no upload de 20 MB de PDFs com `pdftotext`. Regra da casa: depois de medir o uso estável na VPS (`docker stats`), ajustar para ≥ uso/0,7. Fica um comentário dizendo isso.
- Healthcheck herdado do Dockerfile, com comentário no compose (padrão do `conan-torres`).
- Rede externa `proxy`. Labels exatamente como pedido, com `<projeto>` = `price_trail` e porta 8000. Sem `tls.domains`, sem router `-www`, sem redirect nem `tls=true`.
- `logging` json-file com rotação 10m × 5.
- Comentários no topo no mesmo estilo do `conan-torres/docker-compose.prod.yml`: onde o arquivo fica na VPS e que o `.env` não é versionado.

### `.dockerignore` e `.gitignore`

- `.dockerignore`: `.git`, `.github`, `.env`, `.env.*` (menos o exemplo), `__pycache__`, `.venv`, `*.db*`, `*.sqlite*`, `*.log`, `data/`, `img/`, `bin/`, `tests/`, `docs/`, `.scratch/`, `.claude/`, `.githooks/`, `tailwind/`, `tailwind.config.js`, `curadoria.json`, `README.md`.
- `.gitignore` ganha `*.db`, `*.db-wal`, `*.db-shm` e `.env` (já tem `*.sqlite*`, `data/*`, `*.log`).

### Backup

- Script de backup em Python, só biblioteca padrão, dentro da imagem. Roda com `docker compose exec web python -m pricetrail.backup` (ou subcomando `pricetrail backup`, a decidir na implementação; o importante é rodar com o Python do container, sem depender do binário `sqlite3`).
- Usa `VACUUM INTO '/data/backups/app-AAAAMMDD-HHMMSS.db'`, consistente com o app rodando. Nunca copia o arquivo.
- Mantém os últimos N (`BACKUP_KEEP`, padrão 14), apagando os mais antigos. Loga em JSON só nome do arquivo gerado, tamanho, quantos foram apagados e duração.
- README: linha de cron da VPS (ex.: diário às 3h, `cd /opt/apps/price_trail && docker compose exec -T web python -m pricetrail backup`) e passo a passo de restauração (parar o serviço, copiar o backup sobre `/data/app.db` apagando `-wal`/`-shm`, com um container temporário montando o volume, e subir de novo).

### CI (GitHub Actions)

- Workflow disparado em push na `main`: checkout, `docker/login-action` em `ghcr.io` com `GITHUB_TOKEN` (`permissions: packages: write, contents: read`), `docker/build-push-action` com as tags `ghcr.io/c0nant/price_trail:${{ github.sha }}` e `:latest`. Ações com versão fixa.
- O workflow roda a suíte de testes antes do build (o `pdftotext` é simulado nos testes, então não precisa de poppler no runner) e não publica se ela falhar.
- O CI só publica a imagem. O deploy é o cron da VPS.

### Documentação

- README ganha a seção "Produção (Docker)": variáveis, como gerar o hash, como subir local com volume de teste, backup/restauração, rollback por `IMAGE_TAG`, o aviso de réplica única e o checklist fora do código.

## Testing Decisions

- Um bom teste exercita comportamento visível: o que a função pura devolve, ou o que a API HTTP responde (status, corpo, cookie). Nada de conferir chamadas internas, linhas das tabelas de tentativas ou estrutura de módulos. O relógio e o `pdftotext` são as únicas fronteiras simuladas, como já é feito hoje.
- Continua `unittest` (`make test` e hook `pre-push` sem mudança).
- **Seam A: `pick_client_ip` (função pura).** Testes unitários diretos:
  - cabeçalho forjado à esquerda (`forjado, cliente, cloudflare` → `cliente`)
  - cadeia `cliente, cloudflare` → `cliente`
  - cliente IPv6 com borda IPv6 da Cloudflare
  - item inválido no meio da cadeia (é pulado)
  - cabeçalho vazio/ausente → `x-real-ip` → `"unknown"`
  - todos os itens dentro da Cloudflare → `x-real-ip`
- **Seam B: a API HTTP pelo Flask test client (`ApiTestCase`).** Cobre:
  - Login: sucesso grava sessão e devolve `next` saneado; usuário errado e senha errada dão a mesma resposta; CSRF ausente ou errado → 403; logout encerra a sessão.
  - Controle de acesso: página sem sessão → 302 para `/login?next=...`; API sem sessão → 401; `/health`, `/login`, `/api/session` e `/static` sem sessão → acessíveis.
  - Cookie: `HttpOnly`, `Secure`, `SameSite=Lax` no `Set-Cookie`.
  - Bloqueio: 3 falhas do mesmo IP (via `X-Forwarded-For`, com o app de teste confiando no cliente local) → 429 com minutos restantes, inclusive com a senha certa; outro IP continua podendo tentar; depois de 20 min (relógio substituído, como `shopping.today` em `test_shopping`) volta a aceitar; login certo zera a contagem do IP; teto global de 10 falhas em IPs diferentes recusa todos até a falha mais antiga sair da janela de 24h; aviso de última tentativa; o bloqueio persiste entre dois `create_app` sobre o mesmo banco (simula restart); teto de IPs rastreados (com o teto reduzido no teste) não deixa a contagem crescer além dele.
  - `/health`: 200 com banco ok; 503 quando o banco não abre.
  - Host e Origin: host fora de `ALLOWED_HOSTS` → 403; POST com `Origin` de outro site → 403.
- **Ajuste da base:** `ApiTestCase` passa a montar o app com credenciais de teste (hash gerado uma vez por processo, com parâmetros argon2 baratos) e `client()` devolve um cliente **já logado**. Os testes existentes continuam passando sem alteração. Um `anon_client()` serve os testes de acesso.
- Logs: um teste confere que um evento de login sai como uma linha JSON com `ip` e `user` e sem a senha (captura do handler, não do formato exato do texto).
- Prior art: `tests/api_case.py` (base com banco temporário e `pdftotext` simulado), `tests/test_shopping.py` (relógio substituído com `mock.patch`), `tests/test_import_api.py` (cabeçalho `X-Pricetrail` e `Origin`).
- Verificação de entrega (não automatizada no CI, feita pelo agente antes de terminar e registrada no PR):
  1. `docker build` passa.
  2. `docker compose config -q` passa (com um `.env` de teste e a rede `proxy` criada localmente).
  3. Sobe local com um volume de teste (override sem labels, com `ports` só no override de teste) e o container fica `healthy`.
  4. `docker compose logs` mostra JSON, uma linha por evento, incluindo o acesso do gunicorn.
  5. Dados criados (uma nota importada pelo `/import`, um grupo) sobrevivem a `docker compose down && docker compose up -d`.
  6. O backup gera arquivo em `/data/backups/` e a restauração documentada funciona.
  7. `make test` passa.

## Out of Scope

- Vários usuários, tabela de usuários, cadastro, troca de senha pela web, recuperação de senha, 2FA.
- Reimplementar limite de requisições geral (é do Traefik).
- Cloudflare Access (fica como recomendação no checklist).
- Backup externo (fora da VPS) e backup dos PDFs: o script cobre só o SQLite. Ver Further Notes.
- Compose de desenvolvimento com `build:` (o fluxo local continua `make serve`). Um override só para a verificação local pode existir, mas não é entregável de produção.
- Mudar a interface das páginas além da tela de login, do link "Sair" e do redirecionamento em 401.
- Automatizar o deploy (o cron da VPS já existe).
- Postgres ou qualquer troca de banco.

## Further Notes

- **Backups no mesmo volume:** `/data/backups/` está no mesmo disco que o banco. Protege contra erro de uso e corrupção, não contra perda da VPS. Copiar para fora (ex.: `rclone` para um storage) fica para depois. Os PDFs (`/data/pdfs`) não entram no backup do SQLite: são a fonte das notas e devem ser copiados junto num backup externo futuro. Hoje são poucos (4,2 MB).
- **Migração dos dados atuais:** copiar `pricetrail.sqlite` para o volume como `app.db` e a pasta `data/` inteira para `/data/pdfs/`, mantendo a estrutura de subpastas (o `source_path` das notas é relativo a ela). O `.sqlite` local está em WAL: antes de copiar, fechar o servidor local (ou gerar a cópia com `VACUUM INTO`) para não perder o que está no `-wal`.
- **`legacy_dir`:** em banco novo, a migração 1 lê JSONs de curadoria antiga da raiz do projeto. Esses arquivos não existem na imagem, o que é correto (carga vazia). Com o banco atual copiado, já migrado, isso nem roda.
- **`$` no hash:** o Compose interpola `$` em valores do `env_file`. O `.env.example` mostra o hash entre aspas simples.
- **Sub-rede do `proxy`:** `FORWARDED_ALLOW_IPS` depende da sub-rede da rede Docker `proxy` na VPS, que não dá para saber daqui.
- **Checklist fora do código** (vai também no README):
  1. Cloudflare: registro DNS `compras` (A/AAAA para o IP da VPS), nuvem laranja.
  2. VPS:
     - criar `/opt/apps/price_trail/` e copiar `docker-compose.yml` e o `.env` (gerar `SECRET_KEY` com `python -c "import secrets; print(secrets.token_urlsafe(48))"` e o hash com `hash-password`)
     - `docker network inspect proxy` → sub-rede em `FORWARDED_ALLOW_IPS`
     - `docker login ghcr.io` com token `read:packages`, se ainda não fez
     - `docker compose up -d` uma vez para criar o volume `price_trail_data`
     - copiar o banco atual (como `app.db`) e a pasta `data/` (como `pdfs/`) para o volume com um container temporário, e `chown -R 10001:10001` nelas
     - `docker compose restart`
  3. Cron da VPS: agendar o backup diário.
  4. Considerar Cloudflare Access na frente de `compras.conantorres.dev`, já que são dados de compras: a autenticação da Cloudflare antes da do app.
  5. Medir a memória estável com `docker stats` depois de uns dias e ajustar `mem_limit`.
