# 03: `pick_client_ip`

> **Difficulty:** Light: **suggested model:** Haiku (Claude Code) / claude-4.5-haiku-thinking (Cursor). Suggestion only, use whatever model you have to hand.

**Spec:** ../SPEC.md

**What to build:** uma função pura `pick_client_ip(x_forwarded_for, x_real_ip) -> str`, num módulo próprio, só com biblioteca padrão (`ipaddress`). Ela percorre o `X-Forwarded-For` da direita para a esquerda, descarta itens inválidos e itens dentro das faixas da Cloudflare e devolve o primeiro que sobrar. Sem item útil, devolve o `X-Real-IP` aparado e, por último, `"unknown"`. As faixas ficam numa constante idêntica a `trustedIPs: &ips_cloudflare` do `traefik-default/traefik/traefik.yml`, com comentário dizendo que as duas listas mudam juntas e a data da conferência. A referência é `conan-torres/src/lib/reader/client-ip.ts`.

**Seams:**
- Seam A: `pick_client_ip` (função pura)

**Blocked by:** None (can start immediately)

Status: ready-for-human

- [x] `forjado, cliente, <ip cloudflare>` → `cliente`
- [x] `cliente, <ip cloudflare>` → `cliente`
- [x] Cliente IPv6 com borda IPv6 da Cloudflare → o IPv6 do cliente
- [x] Item inválido no meio é pulado
- [x] Cabeçalho vazio ou ausente → `x-real-ip`; sem ele, `"unknown"`
- [x] Todos os itens dentro da Cloudflare → `x-real-ip`
- [x] Lista de faixas confere com o `traefik.yml` da borda e tem o comentário de sincronia
