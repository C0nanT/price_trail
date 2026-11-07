# Relatório de regressão (ticket 08)

Base: ramo `feat/servidor-e-banco-como-fonte` (4b13943). Banco: cópias de `pricetrail.sqlite` (uma para os scripts antigos, outra para o servidor), PDFs de `/home/conan/projects/price_trail/data` só para leitura. Saídas geradas fora do repo (`--out`). O original não foi alterado. O script de comparação ficou fora do repo, em `/tmp/regr.cmp/`.

Os scripts antigos leram `products.json`, `products.rejected.json` e `stores.json` da raiz do projeto (idênticos aos do checkout principal). O servidor migrou a cópia dele (versão 0, esquema antigo) a partir dos mesmos JSONs.

## Resultado

Nenhuma diferença inesperada. Nenhuma correção foi necessária, então não há commits. Testes: 156 passam (`python3 -m unittest discover -s tests -t .`).

## `/api/products` contra o JSON do `chart.html`

- 329 produtos nos dois lados.
- Iguais campo a campo (`categories`, `code`, `description`, `purchases`, `seller`, `stores`, `unit`).
- A ordem também é idêntica, não só o conjunto.

## `/api/catalog` contra `group_page/data.js`

| Chave | Resultado |
| --- | --- |
| `products` (354) | Igual |
| `groups` (13) | Igual |
| `notes` (354 refs) | Igual, exceto `href` (esperado) |
| `suggestions` | 17 iguais; diferem 1 antiga e 2 novas (abaixo) |
| `rejections` | Chave nova, só existe na API: 17 pares |

Diferenças:

1. **`href` das notas (esperada).** Antes era caminho relativo ao arquivo (`../../../home/.../data/13-10-2026.pdf`); agora é `/notes/<chave de acesso>.pdf`. São 22 hrefs distintos nos dois lados, e todos os 22 respondem 200 `application/pdf`. A ordem e os demais campos das compras (`date`, `number`, `file`, `quantity`, `price`) são iguais.
2. **Chave `rejections` (esperada).** Os 17 pares da API são exatamente os pares derivados dos 14 grupos de `products.rejected.json` (combinações dois a dois de cada grupo).
3. **Sugestões que voltaram com a rejeição por par (esperadas pela spec).** Duas referências estavam em `products.rejected.json` como grupos de uma referência só. O script antigo tirava a referência de todas as sugestões. Pela regra por par, a referência só sai de uma sugestão se rejeitada contra todos os outros membros. Como grupo de uma referência não gera par, a migração não leva nada para `rejected_pairs`:
   - `GELATINA APTI` (motivo "mesma descrição"): antes `81901, 81904, 81905`; agora `63064, 81901, 81904, 81905`, com o aviso "preços muito diferentes (1.59 a 6.49)". Referência que voltou: `75315333:63064` (rejeitada como "GELATINA APTI (sachê de 6,49)").
   - `MIST.BOLO C.DR.OETK.` (motivo "descrições parecidas"): sugestão nova `11821, 53330, 53331, 53371`, sem avisos. Referência que voltou: `75315333:11821` (rejeitada como "MIST.BOLO DR.OETKER (3,79)"). A sugestão de 3 referências ("mesma descrição") já existia e continua igual; antes a nova colapsava nela. Agora há duas sugestões que se sobrepõem, o que é o comportamento de `suggest_groups` sem a poda.

   Ponto para o ticket 09: essas duas rejeições de uma referência só (intenção "este produto é diferente de tudo") não são representáveis como pares e se perdem na migração. Se a intenção valer, é preciso rejeitar os pares explicitamente na página `/groups`.

## Rotas, com o servidor no ar (porta alta livre, cópia do banco)

- `GET /` e `GET /groups`: 200 `text/html`. `GET /static/chart/app.js` e `/static/group/app.js`: 200.
- `GET /api/products`, `/api/catalog`, `/api/stores`: 200 JSON.
- `GET /notes/<chave>.pdf`: 200 para as 22 notas; 404 para chave malformada e para chave desconhecida.
- Host estranho (`Host: evil.com`): 403.
- `POST /api/rejections` (lista plana de refs): 200, 17 para 18 pares; `DELETE` desfaz (volta a 17). Corpo inválido: 422; sem JSON: 415.
- `PUT /api/stores/75315333`: 200 ao renomear e ao voltar o nome; nome vazio: 422.
- `PUT /api/groups`: o mesmo conjunto de grupos devolve igual e `/api/products` fica igual byte a byte. Um grupo novo muda a listagem (353 produtos) e a volta ao original restaura os 329. Erros: lista no lugar de objeto 422, JSON quebrado 422, sem content-type 415, ref em dois grupos 422, nome repetido 422.
- `pricetrail export` e `restore` na cópia do servidor: `/api/catalog` idêntico antes e depois do ciclo.
- Servidor parado ao final; o banco original não mudou.
