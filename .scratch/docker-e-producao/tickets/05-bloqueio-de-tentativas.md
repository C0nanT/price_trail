# 05: Bloqueio de tentativas de login no SQLite

> **Difficulty:** Heavy: **suggested model:** Opus (Claude Code) / Opus or the strongest reasoning model available (Cursor). Suggestion only, use whatever model you have to hand.

**Spec:** ../SPEC.md

**What to build:** o login passa a frear tentativas, com a semântica de `conan-torres/src/lib/reader/rate-limit-core.ts`.
- **Por IP:** 3 falhas → bloqueio de 20 min. A entrada expira 20 min após a última falha ou no fim do bloqueio.
- **Global:** no máximo 10 falhas em 24h somando todos os IPs. Ao atingir, recusa toda tentativa, até com a senha certa, até a falha mais antiga sair da janela, e loga um aviso único `teto_global_atingido`.
- **Contagem antecipada:** a tentativa conta como falha antes de comparar a senha. Login certo apaga a contagem do IP e mantém a global.
- **Teto de IPs:** acima de 10.000 IPs rastreados, os menos ativos são descartados.
- **Persistência:** a migração 5 cria `login_attempts` (por IP) e `login_failures` (instantes para a janela global), com índices nos tempos. Toda a sequência (limpar expirados, conferir bloqueio, contar, aplicar o teto) roda numa transação `BEGIN IMMEDIATE`. O relógio vem de uma função do módulo, substituível nos testes.
- **Respostas e logs:** o IP do cliente passa a vir de `pick_client_ip`. Bloqueado → 429 com os minutos restantes (o maior entre o bloqueio do IP e o do teto global). A última tentativa antes do bloqueio devolve um aviso (`lockMinutesIfWrong`), e a página de login mostra os dois casos. Log `login_bloqueado` com `ip` e `user`.

**Seams:**
- Seam B: API HTTP pelo Flask test client (`ApiTestCase`), com `X-Forwarded-For` e relógio substituído

**Blocked by:** 03 (`pick_client_ip`), 04 (Login de usuário único)

Status: ready-for-human

- [x] 3 falhas do mesmo IP → 429 com minutos restantes, mesmo com a senha certa
- [x] Outro IP continua podendo tentar
- [x] Após 20 min (relógio substituído) o IP volta a tentar
- [x] Login certo zera a contagem do IP
- [x] 10 falhas de IPs diferentes em 24h recusam todos até a mais antiga sair da janela
- [x] A tentativa que é a última avisa os minutos de bloqueio caso erre
- [x] O bloqueio persiste entre dois `create_app` sobre o mesmo banco (simula restart)
- [x] Com o teto de IPs reduzido no teste, o número de IPs rastreados não passa dele
- [x] `X-Forwarded-For` forjado à esquerda não troca o IP contado
- [x] Migração 5 roda num banco já em produção (versão 4) sem perda
- [x] `make test` passa
