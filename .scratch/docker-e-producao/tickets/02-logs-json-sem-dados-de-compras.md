# 02: Logs em JSON no stdout/stderr, sem dados de compras

> **Difficulty:** Standard: **suggested model:** Sonnet (Claude Code) / Sonnet (Cursor). Suggestion only, use whatever model you have to hand.

**Spec:** ../SPEC.md

**What to build:** no servidor, todo log sai em JSON, uma linha por evento, com `ts` (ISO 8601 UTC), `level`, `logger`, `msg`, `exc_info` quando houver e os campos passados por `extra=`. Até `INFO` vai para o stdout, de `WARNING` em diante para o stderr. O nível vem de `LOG_LEVEL` (padrão `INFO`) e o formatter usa `json.dumps`, sem dependência nova. O `serve` deixa de configurar o `FileHandler` de `pricetrail.log` (que tem `propagate=False` e engoliria o JSON) e perde a opção `--log`. O `import` do CLI local pode manter o arquivo. No caminho do servidor, o upload loga só contagens por status e, por arquivo, a chave de acesso (quando lida) e o status. Nada de nome de arquivo enviado, nome de loja, CNPJ completo nem texto de erro do parser. O aviso de loja sem cadastro leva só a raiz do CNPJ. Erro inesperado usa `logger.exception` com mensagem genérica.

**Seams:**
- Seam B: API HTTP pelo Flask test client (`ApiTestCase`), com o handler de log capturado

**Blocked by:** 01 (Configuração por ambiente, PRAGMAs e `/health`)

Status: ready-for-human

- [x] Um upload pela API gera linhas JSON válidas com contagens e chaves, sem nome de arquivo, nome de loja nem texto de nota
- [x] `WARNING`+ e tracebacks vão para o stderr; `INFO` para o stdout
- [x] `LOG_LEVEL=DEBUG` liga debug; o padrão é `INFO`
- [x] O servidor não cria nem grava `pricetrail.log`
- [x] A resposta da API de upload para o navegador não muda (o usuário continua vendo nome de arquivo e mensagem de erro na página)
- [x] `make test` passa
