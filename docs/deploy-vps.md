# Deploy na VPS (compras.conantorres.dev)

Passo a passo na ordem. Detalhes de cada item estão na seção "Produção (Docker)" do [README](../README.md).
A imagem já é publicada pelo CI a cada push na `main` (`ghcr.io/c0nant/price_trail:latest` e `:<sha>`).

## 0. No seu computador

1. Gere o hash da senha (pede a senha duas vezes, sem eco):
   ```bash
   python3 -m pricetrail hash-password
   ```
2. Gere o `SECRET_KEY`:
   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(48))"
   ```
3. Feche o servidor local (`make serve`) e gere a cópia consistente dos dados atuais:
   ```bash
   mkdir -p migracao
   python3 -c "import sqlite3; sqlite3.connect('pricetrail.sqlite').execute(\"VACUUM INTO 'migracao/app.db'\")"
   cp -a data migracao/pdfs
   ```

## 1. Cloudflare

- DNS: registro `compras` (A/AAAA) para o IP da VPS, **com a nuvem laranja**.

## 2. VPS: preparar a pasta

```bash
sudo mkdir -p /opt/apps/price_trail && cd /opt/apps/price_trail
# copie para cá: docker-compose.yml, .env (a partir de .env.example) e a pasta migracao/
```

No `.env`:

| Variável | Valor |
|---|---|
| `AUTH_USERNAME` | seu usuário |
| `AUTH_PASSWORD_HASH` | o hash do passo 0, **entre aspas simples** |
| `SECRET_KEY` | o valor do passo 0 |
| `SESSION_COOKIE_SECURE` | `1` |
| `ALLOWED_HOSTS` | `compras.conantorres.dev,localhost,127.0.0.1` |
| `FORWARDED_ALLOW_IPS` | sub-rede da rede `proxy` (abaixo) |
| `IMAGE_TAG` | `latest` |
| `BACKUP_KEEP` | `14` |

Sub-rede (campo `Subnet`; o `172.18.0.0/16` do exemplo é só um chute — se estiver errado, `X-Forwarded-Proto`
é ignorado e upload e cookie Secure quebram):

```bash
docker network inspect proxy
```

## 3. VPS: subir

```bash
docker login ghcr.io          # usuário do GitHub + token com read:packages (se ainda não fez)
cd /opt/apps/price_trail
docker compose pull
docker compose up -d          # cria o volume price_trail_data
docker compose stop web
```

Leve os dados para o volume (container temporário; já faz o `chown` para 10001):

```bash
docker compose run --rm --no-deps --user root -v "$PWD/migracao:/origem:ro" --entrypoint sh web -c \
  'cp /origem/app.db /data/app.db \
   && rm -f /data/app.db-wal /data/app.db-shm \
   && mkdir -p /data/pdfs && cp -a /origem/pdfs/. /data/pdfs/ \
   && chown -R 10001:10001 /data/app.db /data/pdfs'
docker compose up -d
```

## 4. Conferir

- [ ] `docker compose ps` → `web` com `healthy`
- [ ] `https://compras.conantorres.dev` abre a tela de login; entra com seu usuário e senha
- [ ] Gráfico, `/groups`, `/lista` mostram os dados antigos; os links dos PDFs abrem
- [ ] Upload de uma nota em `/import` funciona
- [ ] `docker compose logs web` mostra JSON (inclusive o acesso do gunicorn), com o IP real nos eventos de login
- [ ] Logs no Loki com `projeto=price_trail`

## 5. Backup diário (cron da VPS)

`crontab -e`:

```
15 3 * * * cd /opt/apps/price_trail && docker compose exec -T web python -m pricetrail backup >> /var/log/price_trail-backup.log 2>&1
```

Rode uma vez à mão e confira: `docker compose exec -T web ls -l /data/backups`.
Os backups ficam no mesmo volume: copie `/data/backups` para fora da VPS de vez em quando.
Os PDFs não entram nesse backup.

## 6. Atualizar automaticamente (cron de deploy)

Cada push na `main` publica a imagem nova. Para a VPS acompanhar, agende (ou use o cron que você já tem para outros apps):

```
*/10 * * * * cd /opt/apps/price_trail && docker compose pull -q && docker compose up -d
```

Rollback: fixe `IMAGE_TAG=<sha do commit bom>` no `.env` e rode `docker compose pull && docker compose up -d`.

## 7. Decisões e ajustes

- **Cloudflare Access** na frente do site? São dados de compras: a autenticação da Cloudflare antes da do app. Registre a decisão.
- Depois de alguns dias, meça com `docker stats` e ajuste `mem_limit` no compose (limite ≥ uso / 0,7).
- Uma réplica só, disco local (nunca NFS): o bloqueio de login e o SQLite dependem disso.
- O bloqueio de login tem teto global: 10 tentativas (certas ou erradas) em 24 h trancam todo mundo até a mais antiga sair da janela.
