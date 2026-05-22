# OSSEL Dashboard - Centro de Tecnologia / Governança de Projetos

Painel Flask para governança de projetos da OSSEL Assistência, com dashboard executivo, abas de análise, cronograma, riscos, edição de progresso, conclusão de projetos e persistência externa via GitHub.

## Login

As senhas dos usuários são lidas pelas variáveis de ambiente do Render:

- `ADM_PASSWORD`
- `THIAGO_PASSWORD`
- `DENIS_PASSWORD`
- `FILIPE_PASSWORD`
- `EDUARDO_PASSWORD`

Usuários administradores: ADM, Thiago e Denis.
Usuários operacionais: Filipe e Eduardo.

Configure também uma `SECRET_KEY` fixa no Render. Sem ela, sessões podem ser invalidadas quando o serviço reiniciar.

## Persistência após login, reinício e deploy

No Render Free, o SQLite local pode ser recriado ou ficar diferente do backup após reinício. Por isso, esta versão trata o GitHub como fonte de verdade quando as variáveis abaixo estão configuradas:

- `GITHUB_REPO = usuario/repositorio`
- `GITHUB_TOKEN = token com permissão de escrita em contents`
- `GITHUB_DATA_PATH = data/runtime_projects.json`

A cada alteração de projeto, o sistema:

1. Atualiza o SQLite dentro de uma transação.
2. Gera o JSON completo dos projetos.
3. Salva no GitHub.
4. Lê o GitHub novamente.
5. Compara o conteúdo enviado com o conteúdo remoto.
6. Só confirma a transação local se o GitHub estiver salvo e verificado.

Se o GitHub falhar ou continuar com dados diferentes, a alteração é cancelada para evitar que a tela mostre sucesso e depois o projeto volte após login ou deploy.

## Sincronização automática

Ao fazer login e ao carregar `/api/projects`, o painel compara o SQLite local com `data/runtime_projects.json`. Se encontrar diferença, restaura o SQLite a partir do GitHub. Isso evita o problema de excluir um projeto, sair, entrar novamente e ele aparecer de volta por causa de banco local desatualizado.

Administradores também têm o botão **Sincronizar GitHub** no menu lateral para forçar a conferência manual.

## Funcionalidades visuais

- Cabeçalho institucional: Centro de Tecnologia / Governança de Projetos.
- Logo em PNG transparente para sidebar, login e cabeçalho.
- Dashboard executivo com saúde do portfólio.
- Abas: Visão geral, Projetos, Cronograma e Riscos.
- Indicadores de projetos atrasados, perto de vencer, no prazo, sem prazo e entregues.
- Botão **Concluir** em cada projeto editável.
- Botão **Salvar progresso** junto ao slider.
- Toasts informando se a alteração foi salva e verificada no GitHub.

## Deploy no Render

Use o `render.yaml` incluído no projeto. Confirme as variáveis no Render antes de liberar para a equipe.
