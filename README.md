# OSSEL Dashboard - versão melhorada

Dashboard Flask para acompanhamento de projetos da OSSEL Assistência, com interface moderna, login por variáveis de ambiente e persistência dos projetos via GitHub para evitar perda de dados após deploy no Render.

## O que mudou nesta versão

- Interface redesenhada para login e dashboard.
- Logo oficial em `static/img/logo-ossel.jpeg`.
- Slider de progresso direto no card do projeto.
- Salvamento de observações no card ao sair do campo.
- Modal moderno para criar/editar projetos.
- Busca e filtros por status, categoria e responsável.
- Feedback visual de salvando, sucesso e erro.
- Proteção de rotas privadas e APIs.
- Sessão Flask com cookies `HttpOnly`, `SameSite` e `Secure` em produção.
- CSRF para login e rotas de alteração.
- Cabeçalhos de segurança.
- Persistência GitHub mais robusta.
- Se o backup remoto falhar, a alteração é cancelada para evitar falsa sensação de salvamento.

## Variáveis obrigatórias no Render

Configure em **Environment Variables**:

```text
SECRET_KEY=<gerar valor forte>
GITHUB_REPO=usuario/repositorio
GITHUB_TOKEN=<token com permissão de escrita no repositório>
GITHUB_DATA_PATH=data/runtime_projects.json
ADM_PASSWORD=<senha do ADM>
THIAGO_PASSWORD=<senha do Thiago>
DENIS_PASSWORD=<senha do Denis>
FILIPE_PASSWORD=<senha do Filipe>
EDUARDO_PASSWORD=<senha do Eduardo>
```

`GITHUB_DATA_PATH` é opcional; se não for informado, o sistema usa `data/runtime_projects.json`.

## Como a persistência após deploy funciona

O Render Free pode recriar o SQLite local em novos deploys. Por isso, o SQLite não deve ser a única fonte de verdade dos dados alterados pelos usuários.

Nesta versão:

1. O usuário altera progresso, observação, responsável, status ou outro dado do projeto.
2. O backend grava a alteração em uma transação SQLite local.
3. Antes de confirmar a transação, o backend monta um JSON validado com todos os projetos.
4. O backend salva esse JSON no GitHub usando `GITHUB_REPO`, `GITHUB_TOKEN` e `GITHUB_DATA_PATH`.
5. Se o GitHub salvar com sucesso, a transação local é confirmada e o usuário recebe sucesso.
6. Se o GitHub falhar, a transação local é desfeita e o usuário recebe erro claro.
7. Depois de um novo deploy, se o banco local estiver vazio, o sistema restaura os projetos a partir do JSON remoto no GitHub.

O arquivo remoto salvo possui esta estrutura:

```json
{
  "schema_version": 1,
  "app": "ossel-dashboard",
  "source": "render",
  "data_path": "data/runtime_projects.json",
  "updated_at": "2026-01-01T12:00:00Z",
  "updated_by": "Thiago",
  "action": "atualiza-projeto-1",
  "project_count": 1,
  "projects": []
}
```

## Como testar antes de subir

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export SECRET_KEY="dev-secret"
export ADM_PASSWORD="admin123"
export THIAGO_PASSWORD="thiago123"
export DENIS_PASSWORD="denis123"
export FILIPE_PASSWORD="filipe123"
export EDUARDO_PASSWORD="eduardo123"
python app.py
```

Acesse `http://localhost:5000/login`.

Para testar a persistência GitHub localmente, configure também:

```bash
export GITHUB_REPO="usuario/repositorio"
export GITHUB_TOKEN="seu_token"
export GITHUB_DATA_PATH="data/runtime_projects.json"
```

## Checklist para validar no Render

1. Fazer deploy.
2. Configurar todas as variáveis de ambiente.
3. Fazer login como ADM.
4. Criar ou editar um projeto.
5. Alterar o progresso pelo slider.
6. Confirmar a mensagem de sucesso.
7. Conferir se `data/runtime_projects.json` foi atualizado no GitHub.
8. Fazer novo deploy no Render.
9. Abrir novamente o dashboard.
10. Confirmar que progresso, observações e responsáveis continuam salvos.

## Observações importantes

- Não suba tokens ou senhas para o GitHub.
- `GITHUB_TOKEN` é usado somente no backend.
- O token nunca é enviado para HTML, JavaScript ou respostas de API.
- O arquivo `data/runtime_projects.json` é criado/atualizado automaticamente pela aplicação no GitHub.
- O ZIP não inclui `data/runtime_projects.json` para evitar sobrescrever dados reais já salvos.
