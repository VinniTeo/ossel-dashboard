# Revisão OSSEL Assistência - Versão visual dinâmica

## Foco da nova revisão
Esta versão reforça a persistência já implementada via GitHub e melhora profundamente a experiência visual do dashboard. O painel deixou de ser uma lista estática de cards e passou a ter navegação por abas, visão executiva, indicadores de prazo, cronograma e sala de riscos.

## Melhorias visuais e funcionais aplicadas

### 1. Navegação por abas
- Criada navegação lateral por abas:
  - Visão geral
  - Projetos
  - Cronograma
  - Riscos
- Cada aba possui contador dinâmico.
- A aba de riscos destaca automaticamente a quantidade de projetos críticos.
- O cabeçalho muda conforme a área selecionada.

### 2. Dashboards de análise
- Criada tela de visão executiva com:
  - Card principal de saúde do portfólio.
  - Progresso médio em gráfico circular.
  - Indicadores de total, críticos, no prazo e entregues.
  - Gráfico por categoria.
  - Gráfico por responsável.
  - Donut de distribuição por prazo/status.
  - Lista de próximos vencimentos.

### 3. Indicação de prazo
- Implementada classificação visual dos projetos:
  - Atrasado
  - Vence hoje
  - Perto de vencer
  - No prazo
  - Entregue
  - Sem prazo
- Os cards mudam cor e destaque conforme a situação.
- Projetos críticos ficam mais visíveis.

### 4. Diferenciação dos projetos
- Cards ganharam faixa lateral por categoria/situação.
- Cada card mostra categoria, prazo, status, responsável e unidade de forma mais clara.
- Cards de projetos vencidos, próximos do prazo, no prazo e entregues têm estilos diferentes.

### 5. Filtros rápidos e navegação melhorada
- Criadas abas rápidas dentro da área de projetos:
  - Todos
  - Críticos
  - Perto de vencer
  - No prazo
  - Entregues
- Adicionados filtros detalhados por:
  - Status
  - Categoria
  - Responsável
  - Prazo
  - Ordenação
- A busca continua funcionando por projeto, unidade, setor, responsável e observações.

### 6. Cronograma
- Criada aba específica de cronograma com agrupamento por vencimento:
  - Atrasados
  - Vence hoje ou em até 7 dias
  - No prazo
  - Sem prazo definido
  - Entregues

### 7. Sala de riscos
- Criada aba específica para projetos que exigem atenção.
- A lista inclui projetos vencidos, perto do prazo e projetos com progresso baixo para o prazo.
- Cada risco exibe motivo, responsável, prazo e progresso.

### 8. Persistência após deploy
- Mantida a lógica de persistência via GitHub usando:
  - GITHUB_REPO
  - GITHUB_TOKEN
  - GITHUB_DATA_PATH
- O progresso continua sendo salvo pelo backend e sincronizado com o GitHub quando configurado.
- O sistema continua bloqueando sucesso falso quando o GitHub está configurado e o backup falha.

## Arquivos alterados
- `templates/index.html`
- `static/css/styles.css`
- `static/js/dashboard.js`
- `REVISAO_OSSEL.md`

## Validações realizadas
- `python -m py_compile app.py`
- `node --check static/js/dashboard.js`
- Teste local de login.
- Teste local de criação de projeto.
- Teste local de atualização de progresso.
- Teste local de carregamento das APIs principais.

