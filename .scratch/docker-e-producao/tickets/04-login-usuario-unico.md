# 04: Login de usuário único

> **Difficulty:** Heavy: **suggested model:** Opus (Claude Code) / Opus or the strongest reasoning model available (Cursor). Suggestion only, use whatever model you have to hand.

**Spec:** ../SPEC.md

**What to build:** o site inteiro passa a exigir login.
- **Credenciais:** um único usuário definido no ambiente (`AUTH_USERNAME`, `AUTH_PASSWORD_HASH` em argon2 com `argon2-cffi` de versão fixa, `SECRET_KEY`). Sem essas três variáveis, o servidor recusa subir com mensagem clara. O subcomando `pricetrail hash-password` pede a senha duas vezes sem eco e imprime o hash.
- **Páginas e rotas:** página estática `/login`; `GET /api/session` devolve o token CSRF e o estado logado; `POST /api/login` recebe JSON `{username, password, next}` com o cabeçalho `X-CSRF-Token`; `POST /api/logout` também exige o token.
- **Erros iguais:** usuário errado e senha errada dão a mesma resposta 401. O hash é verificado sempre e o usuário é comparado em tempo constante.
- **Sessão:** sessão assinada do Flask, com cookie `HttpOnly`, `Secure` (desligável por `SESSION_COOKIE_SECURE=0`, só para uso local por HTTP), `SameSite=Lax` e vida de 30 dias.
- **Controle de acesso:** sem sessão, uma página HTML redireciona (302) para `/login?next=…`, e `/api/*` e `/notes/*` respondem 401. Ficam livres `/login`, `/api/session`, `/api/login`, `/health` e `/static/*`. O `next` é saneado: só caminho relativo do próprio site.
- **Frontend:** o helper de API comum e o upload do `/import` redirecionam para o login em 401. Cada página ganha "Sair".
- **CSRF nas APIs:** POST, PUT e DELETE com `Origin` de outro site → 403, generalizando a regra do upload.
- **Logs:** eventos `login_ok`, `login_falhou` e `logout` em JSON com `ip` e `user`. O `ip` usa o IP direto da conexão por enquanto; o ticket 05 troca por `pick_client_ip`. `user` é o `AUTH_USERNAME` quando o usuário digitado confere, senão `"desconhecido"`. A senha nunca é logada.
- **Testes:** `ApiTestCase` monta o app com credenciais de teste (argon2 barato) e `client()` devolve um cliente já logado, então os testes existentes passam sem mudança. Um `anon_client()` serve os testes de acesso.

**Seams:**
- Seam B: API HTTP pelo Flask test client (`ApiTestCase`)

**Blocked by:** 01 (Configuração por ambiente, PRAGMAs e `/health`), 02 (Logs em JSON no stdout/stderr, sem dados de compras)

Status: ready-for-human

- [x] Login certo grava a sessão e devolve o `next` saneado (`//evil.com` e URL absoluta viram `/`)
- [x] Usuário errado e senha errada → mesma resposta 401
- [x] CSRF ausente ou errado no login/logout → 403
- [x] `Set-Cookie` tem `HttpOnly`, `Secure` e `SameSite=Lax`
- [x] Página sem sessão → 302 para `/login?next=…`; API e `/notes` sem sessão → 401; rotas livres acessíveis
- [x] Logout encerra a sessão
- [x] POST/PUT/DELETE com `Origin` de outro site → 403
- [x] Servidor sem `AUTH_USERNAME`/`AUTH_PASSWORD_HASH`/`SECRET_KEY` não sobe e explica o porquê
- [x] `hash-password` gera um hash que o login aceita
- [x] Evento de login sai como JSON com `ip` e `user`, sem a senha
- [x] Na página, a sessão expirada leva ao login e volta à página depois de entrar (conferido no navegador)
- [x] Testes existentes passam sem alteração; `make test` passa
