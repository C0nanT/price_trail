# Verificação de entrega (ticket 09)

Feita em 2026-11-07, Docker 29.9.2, branch worktree-agent-a4791cfbeecae9314 (base feat/docker-e-producao a925110).
Projeto `pt09`, imagem `pt09-test:local`, volume `pt09_data`, rede `pt09_proxy` (172.31.0.0/16), porta 127.0.0.1:18009.
Override local (fora do git): image pt09-test:local, `labels: !reset []`, `ports`, `networks.proxy.name: pt09_proxy`.
Usuário `teste` / senha sintética; dados: 1 PDF real de data/ importado por /api/import + grupo sintético.
Tudo removido no fim (container, volume, rede, imagem). Nada do usuário foi tocado (a rede `proxy` real só foi lida por `compose config -q`).

1. docker build passou.
2. compose config -q: OK com override; OK sem override contra o `proxy` real (leitura).
3. `pt09-web-1 Up 25 seconds (healthy)`. GET /health 200 {"status":"ok"}. GET / sem sessão 302 /login?next=%2F.
4. Logs: 33 linhas, 0 não-JSON (gunicorn.error 11, gunicorn.access 17, pricetrail.auth 5). Acesso com method,path,status,duration_ms,bytes,ip (ip do X-Forwarded-For). Senha não aparece nos logs.
5. Bloqueio por IP (X-Forwarded-For 203.0.113.9): 401, 401, 401 (lockMinutesIfWrong 20), 4a: 429 minutesLeft 20; senha certa do mesmo IP: 429; IP 203.0.113.10 com senha certa: 200. Eventos login_falhou/login_bloqueado/login_ok com ip e user.
   Obs.: a sessão é rotacionada no login (token CSRF antigo dá 403 depois de logar); esperado.
6. Nota importada (summary new:1; 9 produtos; PDF da nota 200) + grupo "Grupo teste 09" (PUT /api/groups); `down && up -d`; depois: mesmo grupo, 9 produtos, PDF 200, healthy.
7. Backup: `python -m pricetrail backup` -> {"msg":"backup","file":"app-20261107-201149.db","bytes":77824,"deleted":0,...}; arquivo em /data/backups.
   Restauração: grupo apagado após o backup; stop; `run --rm --no-deps --user root --entrypoint sh web -c '...'` do README (texto literal, aspas simples e `\`), exit 0; up -d; healthy; grupo de volta; /data/app.db dono 10001:10001; -wal/-shm antigos removidos.
8. Migração (comando novo do README, `-v migracao:/origem:ro`): VACUUM INTO do pricetrail.sqlite local (35 notas) + data/ -> volume; exit 0; healthy; 401 produtos, 17 grupos; 36 PDFs em /data/pdfs (35 + o importado); dono 10001.
9. `docker compose cp web:/data/backups ./cp_out` copia os backups (README tinha `docker cp` de volume, que não existe; corrigido).
10. make test: Ran 240 tests, OK (skipped=1).

Não verificado: pull/login no ghcr.io, Traefik/Cloudflare/certificado, FORWARDED_ALLOW_IPS real da VPS, cron da VPS, o workflow no GitHub, bloqueio persistir após restart no container (há teste unitário), mem_limit sob carga.
