# Servidor local e banco SQLite como fonte única

Status: ready-for-agent

## Problem Statement

O projeto cresceu de forma orgânica e ficou trabalhoso de usar e de mudar:

- Depois de importar notas ou mudar um grupo, preciso regerar `chart.html` e a página de agrupamento à mão.
- Agrupar produtos exige exportar um JSON, substituí-lo na pasta do projeto e regerar as páginas.
- Grupos, rejeições e lojas ficam em arquivos JSON, separados do banco. Rejeitar uma sugestão e cadastrar uma loja são edições manuais desses arquivos.
- O HTML, o CSS e o JS do gráfico estão dentro de uma string em Python.
- Consultas e leitura de configuração estão duplicadas entre scripts, e o schema mora no parser de notas.
- Gerar a página de agrupamento roda `pdftotext` em todos os PDFs, só para achar o link de cada nota.
- O gráfico identifica o produto pelo CNPJ inteiro, e os grupos pela raiz de 8 dígitos. A mesma loja com duas filiais vira dois produtos.
- Rejeitar uma referência a tira de todas as sugestões, mesmo as válidas com outros produtos.

## Solution

Um servidor Python local lê tudo direto do SQLite. Abro uma URL e vejo sempre os dados atuais, sem etapa de geração. O gráfico e a página de agrupamento viram páginas estáticas que consomem uma API.

Grupos, rejeições e lojas passam a viver no banco e são editados pelas páginas, com efeito imediato. Como o banco não é versionado, a curadoria ganha um comando de exportação (commitável) e um de restauração. O schema passa a evoluir por migrações, e apagar o banco deixa de ser o caminho normal.

O código vira um pacote com um único comando e subcomandos para importar, servir, exportar e restaurar.

## User Stories

### Consultar preços

1. Como usuário, quero iniciar um servidor com um comando, para abrir o histórico no navegador sem gerar arquivos.
2. Como usuário, quero ver notas recém-importadas ao recarregar a página, para não rodar nenhum passo extra.
3. Como usuário, quero que o gráfico mantenha filtros de categoria, loja, busca, datas e ordenação, para não perder nada do que uso hoje.
4. Como usuário, quero manter a média, o campo de preço atual e o veredito Barato/Caro, para decidir uma compra.
5. Como usuário, quero ver um grupo refletido no gráfico ao recarregar, para confirmar o resultado do agrupamento.
6. Como usuário, quero que a mesma mercadoria em duas filiais da mesma rede seja um produto só, para ver um histórico contínuo.
7. Como usuário, quero uma mensagem clara na página se a API falhar, para não confundir erro com "sem produtos".

### Agrupar produtos

8. Como usuário, quero criar um grupo na página e vê-lo salvo no banco na hora, para não exportar nem substituir arquivos.
9. Como usuário, quero renomear um grupo, para usar um nome legível.
10. Como usuário, quero tirar produtos de um grupo, para corrigir um erro.
11. Como usuário, quero excluir um grupo, para desfazer um agrupamento.
12. Como usuário, quero ver um erro claro se a mesma referência estiver em dois grupos ou se um nome repetir, para corrigir sem corromper os dados.
13. Como usuário, quero que um salvamento com erro não aplique nada, para nunca ficar com grupos pela metade.
14. Como usuário, quero marcar uma sugestão como "não juntar", para ela sair da lista sem editar arquivos.
15. Como usuário, quero que "não juntar" valha só para aqueles produtos entre si, para eles ainda aparecerem em sugestões com outros produtos.
16. Como usuário, quero desfazer um "não juntar", para corrigir uma decisão errada.
17. Como usuário, quero abrir o PDF de uma nota a partir do produto, para conferir o item.
18. Como usuário, quero que o link do PDF continue funcionando depois de renomear ou mover o arquivo e reimportar, para não perder o acesso.
19. Como usuário, quero que a página de agrupamento abra rápido, para não esperar a leitura de todos os PDFs.

### Cadastrar lojas

20. Como usuário, quero ver as lojas sem cadastro, para saber o que falta categorizar.
21. Como usuário, quero definir nome e categoria de uma loja pela página, para não editar arquivos.
22. Como usuário, quero um aviso no import quando aparecer uma loja sem cadastro, para lembrar de categorizá-la.
23. Como usuário, quero que loja sem cadastro continue com o nome da nota e a categoria "Outros", para o gráfico funcionar antes do cadastro.

### Importar

24. Como usuário, quero importar a pasta de PDFs com um subcomando, para manter o fluxo atual.
25. Como usuário, quero reimportar sem duplicar notas, para rodar o comando quantas vezes quiser.
26. Como usuário, quero as mesmas saídas `NOVA`, `JÁ TEM` e `ERRO` e o mesmo código de saída, para continuar lendo o resultado do mesmo jeito.
27. Como usuário, quero importar com o servidor ligado, para não precisar pará-lo.

### Proteger os dados

28. Como usuário, quero que minhas notas, grupos, rejeições e lojas atuais entrem no banco na primeira execução, para não refazer nada.
29. Como usuário, quero que atualizar o projeto migre o banco sem perder dados, para nunca precisar apagá-lo.
30. Como usuário, quero exportar grupos, rejeições e lojas para um arquivo, para commitar um backup e manter histórico.
31. Como usuário, quero que o arquivo exportado tenha ordem estável, para o diff no git mostrar só o que mudou.
32. Como usuário, quero restaurar a curadoria a partir do arquivo exportado, para recriar o banco a partir dos PDFs sem perder trabalho.
33. Como usuário, quero que o servidor só aceite conexões da minha máquina, porque os PDFs contêm meu CPF.
34. Como usuário, quero que a rota de PDF só entregue arquivos da pasta de dados, para nenhum outro arquivo vazar.

### Manter o projeto

35. Como desenvolvedor, quero o parser sem dependência de banco, para testá-lo só com texto.
36. Como desenvolvedor, quero cada consulta em um único lugar, para uma mudança não exigir edições em vários scripts.
37. Como desenvolvedor, quero HTML, CSS e JS em arquivos próprios, para editá-los com suporte do editor.
38. Como desenvolvedor, quero um arquivo com as dependências Python, para instalar o projeto num clone novo.
39. Como desenvolvedor, quero README e docs refletindo o novo fluxo, para não seguir instruções antigas como apagar o banco.

## Implementation Decisions

### Módulos

O código vira o pacote `pricetrail`, e os scripts soltos saem:

- **nfce**: parser puro, de texto da nota para `Note`. Inclui validação da chave e dos totais. Não conhece o banco.
- **db**: conexão e migrações. Dono do schema.
- **importer**: encontra PDFs, extrai o texto, chama o parser e grava.
- **catalog**: todas as consultas e regras de produtos, grupos, rejeições, lojas, sugestões, exportação e restauração.
- **server**: rotas HTTP finas sobre `catalog`.
- **cli**: subcomandos `import`, `serve`, `export` e `restore`, usados como `python3 -m pricetrail <subcomando>`.
- **web**: arquivos estáticos das duas páginas, sem build e sem bibliotecas externas.

Saem `chart.py`, `group_page.py`, `suggest_products.py`, os artefatos gerados `chart.html`, `group_page/` e `products.suggested.json`, e suas entradas no `.gitignore`. O `Resolver` e a validação de `products.json` saem, substituídos por joins e constraints.

### Schema

As migrações usam `PRAGMA user_version`, são numeradas e rodam em ordem e em transação ao abrir o banco. A versão 0 corresponde a um banco inexistente ou ao banco atual, que já tem `notes`, `items` e a view. A migração precisa funcionar nos dois casos. A view `price_history` é mantida.

Tabelas novas:

- `stores(cnpj_root PK, store, category)`
- `product_groups(id PK, name UNIQUE)`
- `group_refs(group_id FK, cnpj_root, product_code, PK(cnpj_root, product_code))`. A chave primária garante que uma referência esteja em um grupo só. Apagar um grupo apaga suas referências.
- `rejected_pairs(cnpj_root_a, code_a, cnpj_root_b, code_b, PK de todas)`. O par é guardado em ordem canônica (a < b), para não existir em duplicidade.

`notes` ganha `source_path`, relativo à pasta de dados, e pode ser nulo. `source_file` é mantido.

### Carga inicial

Na primeira migração:

- `stores.json` e `products.json` são carregados nas tabelas, se existirem.
- Cada grupo de `products.rejected.json` vira todos os pares entre suas referências. O nome do grupo é descartado.
- `source_path` é preenchido uma única vez lendo a chave de acesso de cada PDF da pasta de dados, com fallback pelo nome do arquivo.

Depois disso, os três JSONs saem do repositório e o arquivo exportado toma o lugar deles. A carga roda uma única vez, controlada pela versão do banco.

### Identidade do produto

- Um produto é `(cnpj_root, product_code, unit)`, ou `(grupo, unit)` quando agrupado. O CNPJ completo deixa de identificar produto.
- Unidades diferentes continuam sem juntar, mesmo dentro de um grupo.
- Referências por descrição exata deixam de existir. Nenhuma das refs atuais usa esse formato. Só restam referências `raiz:código`.
- A normalização de texto continua existindo, só para as sugestões.

### Sugestões

O algoritmo atual é mantido (mesma descrição e descrições parecidas, na mesma loja). Muda só o filtro:

- Um par rejeitado não some com os produtos: cada produto só sai da sugestão se todos os seus pares nela estiverem rejeitados.
- Sugestão com menos de 2 produtos some.
- Sugestões com as mesmas referências continuam unificadas, e os avisos são recalculados.
- "Não juntar" em uma sugestão rejeita todos os pares dela.

### API

JSON, sob `/api`:

- `GET /api/products`: mesmo formato dos dados embutidos hoje no gráfico, uma lista com todas as compras. Os filtros continuam no cliente, porque o volume é pequeno.
- `GET /api/catalog`: mesmo formato do `data.js` atual da página de agrupamento (`products`, `suggestions`, `groups`, `notes`). O `href` de cada nota aponta para a rota de PDF e é nulo se o arquivo não existir.
- `PUT /api/groups`: substitui todos os grupos em uma transação, a partir do mapa `nome -> referências` que a página já mantém. Violação de regra retorna 422 com mensagem legível e não altera nada.
- `POST /api/rejections` e `DELETE /api/rejections`: recebem uma lista de referências e criam ou removem todos os pares entre elas.
- `GET /api/stores`: lojas cadastradas e raízes de CNPJ presentes nas notas sem cadastro.
- `PUT /api/stores/<raiz>`: cria ou atualiza nome e categoria.
- `GET /notes/<chave de acesso>.pdf`: entrega o PDF da nota, ou 404.

### Servidor

- Flask, que entra como dependência declarada. O README deixa de prometer "sem dependências".
- Escuta só em `127.0.0.1` por padrão.
- Recusa requests com `Host` diferente de localhost ou `127.0.0.1`, contra DNS rebinding.
- Escritas exigem `Content-Type: application/json`, o que bloqueia formulários de outros sites.
- A rota de PDF valida a chave como 44 dígitos e garante que o caminho resolvido fique dentro da pasta de dados.
- Uma conexão SQLite por request. WAL ligado, para importar com o servidor no ar. O `.gitignore` passa a cobrir os arquivos `-wal` e `-shm`.

### Importação

- Mantém saída, log, códigos de saída e validações atuais.
- Ao encontrar uma nota já existente, atualiza `source_path` se o arquivo mudou de lugar.
- O aviso de loja sem cadastro passa a consultar `stores` e orienta a usar a página.

### Páginas

- O gráfico mantém o comportamento. Só muda a origem dos dados, de JSON embutido para `fetch`.
- A página de agrupamento perde baixar, copiar, salvar em arquivo e o rascunho em localStorage. Ganha salvar, "não juntar", lista de rejeições com desfazer e a seção de lojas.
- As duas páginas têm link entre si e mostram erro de API.

### Exportação e restauração

- `export` grava grupos, pares rejeitados e lojas em um único JSON, com chaves e listas ordenadas e versionado por um campo de formato. O arquivo fica no repositório.
- `restore` substitui a curadoria do banco pelo conteúdo do arquivo, em uma transação.
- Recriar do zero passa a ser: importar os PDFs e restaurar a curadoria.

## Testing Decisions

Um bom teste exercita o comportamento externo: prepara o estado pela mesma entrada do usuário e verifica a resposta. Não chama helpers internos nem verifica SQL.

Seams acordados:

- **API HTTP**: cliente de teste do Flask sobre um banco temporário, preenchido com notas sintéticas pelo importador. Cobre produtos, identidade por raiz, grupos, rejeições, sugestões, lojas, PDFs, migração, exportação e restauração.
- **Parser**: `parse_note`, de texto para `Note`, como hoje.

Cobertura esperada na API:

- Produtos agrupados e separados, unidades diferentes sem juntar e duas filiais virando um produto.
- `PUT /api/groups` com ref duplicada e com nome repetido: 422 e nada alterado.
- Par rejeitado sai da sugestão sem afetar sugestões com terceiros.
- PDF: arquivo existente, ausente, chave inválida e tentativa de sair da pasta de dados.
- Host estranho e escrita sem JSON recusados.
- Migração a partir de um banco na versão atual, com os JSONs presentes: dados preservados, carga feita uma só vez e abertura repetida sem efeito.
- Exportar, restaurar num banco novo e obter as mesmas respostas da API.

Módulos testados: `nfce` diretamente; `importer`, `catalog`, `db` e `server` pela API. O CLI não tem testes próprios, além de um uso manual.

Prior art:

- Testes do parser e `make_text`, nas fixtures de notas sintéticas, continuam valendo.
- Os testes de `load_products` e `build_data` são reescritos contra a API, mantendo os cenários. O cenário de unidades diferentes passa a usar referências por código.
- Testes seguem em `unittest`, que é o que o hook `pre-push` roda.

Verificação de regressão, antes de apagar os scripts antigos: extrair o JSON do `chart.html` e do `group_page/data.js`, gerados a partir do banco e dos JSONs atuais, e comparar com `/api/products` e `/api/catalog`. Devem ser iguais, exceto por ordem, pelo `href` e pelas sugestões que voltam com a rejeição por par. Depois, abrir as duas páginas e exercitar as rotas com o servidor no ar.

## Out of Scope

- Upload de PDF e botão de importar pela página.
- Tabela `ean_alias` e busca por código de barras.
- Acesso pela rede local, HTTPS e autenticação.
- ORM, framework de frontend e etapa de build.
- Mudança no parsing de notas ou suporte a novos layouts.
- Redesenho visual das páginas.
- Conversão de valores `REAL` para centavos.

## Further Notes

Decisões tomadas ao escrever a spec, sem discussão prévia. Vale revisar:

- `PUT /api/groups` substitui todos os grupos em vez de ter um CRUD por grupo. É a menor mudança no JS da página e valida tudo atomicamente.
- `restore` foi acrescentado ao `export`, porque um backup sem restauração não permite recriar o banco.
- A edição de lojas pela página foi acrescentada, porque sem `stores.json` não haveria outro jeito de cadastrar.
- A regra exata do filtro de sugestões por par.

Outros pontos:

- O gráfico deixa de abrir como arquivo isolado: agora exige o servidor rodando. Continua sem depender de internet.
- Hoje o banco não tem códigos em mais de um CNPJ da mesma raiz, então a mudança de identidade não altera os dados atuais.
- A rejeição por par vai reintroduzir algumas sugestões que hoje estão escondidas. Isso é esperado.
- O README tem informação desatualizada sobre os testes de layout ("só uma nota do Atacadão"), que pode ser corrigida junto.
- `docs/handoff-codigo-de-barras.md` cita `chart.py` e deve ser atualizado.
