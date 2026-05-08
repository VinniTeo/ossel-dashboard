# OSSEL Dashboard Profissional V16

Versão com upgrades executivos e operacionais:

- Timeline / Gantt dos projetos por prazo.
- Filtros avançados por categoria, status, responsável e risco.
- Dashboard executivo por unidade.
- Ranking de produtividade por responsável.
- Evidências por projeto com upload de imagens leves.
- Histórico de alterações.
- SLA visual por projeto.
- Exportação CSV e impressão/salvar em PDF pelo navegador.
- Modo TV/monitor.
- Kanban operacional.
- Layout mobile melhorado.
- Backup persistente no GitHub via runtime_projects.json.
- Login por Environment Variables do Render.

## Variáveis obrigatórias no Render

Senhas:
- ADM_PASSWORD
- THIAGO_PASSWORD
- DENIS_PASSWORD
- FILIPE_PASSWORD
- EDUARDO_PASSWORD

Persistência gratuita via GitHub:
- GITHUB_REPO = usuario/repositorio
- GITHUB_TOKEN = token classic com permissão repo
- GITHUB_DATA_PATH = data/runtime_projects.json

Opcional para notificação no Teams:
- TEAMS_WEBHOOK_URL

## Deploy

1. Extraia este ZIP.
2. Suba os arquivos na raiz do repositório GitHub.
3. No Render, use:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
4. Manual Deploy -> Deploy latest commit.

## Observação sobre evidências

As evidências são salvas no backup do GitHub em base64. Use imagens leves para não deixar o arquivo runtime_projects.json muito grande.


## V17 - ajustes solicitados
- Ranking visível somente para usuários ADM.
- Timeline/Gantt reformulado: o marcador azul indica a data de entrega dentro do período da carteira; a barra fina inferior indica o percentual de andamento.
- Visual geral atualizado com paleta corporativa azul escuro OSSEL Assistência.
- Cards e controles mais compactos para melhor leitura executiva.


## V18
Reforma visual completa: menu lateral, timeline clara, cards compactos, paleta OSSEL em azul escuro e controles de progresso revisados. Mantém login por variáveis de ambiente e backup GitHub.
