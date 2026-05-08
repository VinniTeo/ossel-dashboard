# OSSEL Dashboard - V15

## Login
As senhas dos usuários são lidas pelas variáveis de ambiente do Render:

- ADM_PASSWORD
- THIAGO_PASSWORD
- DENIS_PASSWORD
- FILIPE_PASSWORD
- EDUARDO_PASSWORD

Usuários ADM: ADM, Thiago e Denis.
Usuários operacionais: Filipe e Eduardo.

## Como manter os dados mesmo sem Persistent Disk

No Render Free, o SQLite local pode ser recriado em novos deploys. Para não perder progresso, observações e responsáveis, esta versão pode salvar automaticamente os dados em um arquivo JSON dentro do próprio GitHub.

Configure no Render:

- GITHUB_REPO = VinniTeo/ossel-dashboard
- GITHUB_TOKEN = token do GitHub com permissão de escrita no repositório
- GITHUB_DATA_PATH = data/runtime_projects.json  (opcional)

Com isso, a cada alteração de projeto o sistema atualiza o arquivo `data/runtime_projects.json` no GitHub. Quando o Render fizer um novo deploy e o banco local estiver vazio, o sistema restaura os dados a partir desse arquivo.

Se você não configurar GITHUB_TOKEN e GITHUB_REPO, o sistema continua funcionando, mas os dados alterados podem ser perdidos em deploys, porque o banco local do Render Free não é persistente.
