# 01: Pacote `pricetrail` e subcomando `import`

> **Difficulty:** Standard: **suggested model:** Sonnet (Claude Code) / Sonnet (Cursor). Suggestion only, use whatever model you have to hand.

**Spec:** ../SPEC.md

**What to build:** Prefactor sem mudança de comportamento. O script de importação vira o pacote `pricetrail`, com o parser puro (`nfce`), a conexão e o schema (`db`), a importação (`importer`) e o CLI (`cli`). Importar passa a ser `python3 -m pricetrail import`, com as mesmas opções e saídas de hoje. Os scripts antigos (`chart.py`, `group_page.py`, `suggest_products.py`) continuam funcionando, importando do pacote.

**Seams:**
- Parser

**Blocked by:** None (can start immediately)

Status: ready-for-human

- [x] `python3 -m pricetrail import` aceita pasta, `--db`, `--data` e `--log` (`--stores` saiu no ticket 06: lojas ficam no banco)
- [x] Saídas `NOVA`, `JÁ TEM`, `ERRO`, log e códigos de saída são os mesmos
- [x] `nfce` não depende de banco nem de subprocess
- [x] Gráfico e agrupamento servidos pela API com os mesmos dados de antes (comprovado no ticket 08; os scripts antigos saíram no ticket 10)
- [x] Todos os testes passam com `python3 -m unittest discover -s tests -t .`
- [x] README mostra o novo comando de importação
