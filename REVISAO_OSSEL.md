# Revisão OSSEL Assistência - Correção de logo e progresso

## Plano executado por etapas
1. Analisei a tela apontada pelo usuário e a estrutura do projeto Flask.
2. Revisei o template principal `templates/index.html`, os assets em `static/` e a renderização dos cards de projetos.
3. Corrigi a marca lateral para usar o logo real da OSSEL Assistência com fundo removido, evitando o bloco quadrado azul dentro da sidebar.
4. Reforcei a barra de progresso dos cards para ficar visível, única e funcional.
5. Removi a duplicidade visual de status/concluído dentro do painel de andamento.
6. Reempacotei o projeto para entrega.

## O que foi revisado
- Sidebar e área de marca.
- Componente de card de projeto.
- Painel de andamento/progresso.
- Estados de status e prazo exibidos nos cards.
- Arquivos estáticos de logo.

## O que foi corrigido
- O logo quadrado foi substituído por uma versão PNG recortada, com transparência, usando a identidade visual real da OSSEL Assistência.
- A sidebar mantém “OSSEL Assistência” e “Governança de Projetos” abaixo da marca.
- A barra de progresso voltou a aparecer de forma clara no painel “ANDAMENTO”.
- A barra agora é única, mais grossa, legível e ligada ao percentual salvo do projeto.
- A duplicidade de “Concluído” no painel de progresso foi reduzida: projetos 100% exibem apenas um estado de conclusão no painel de andamento.

## O que foi melhorado
- Visual da marca na sidebar, sem bloco quadrado destoando do layout.
- Progresso com melhor contraste, altura maior, sombra interna e preenchimento mais evidente.
- Status de progresso mais limpo e menos repetitivo.
- Aparência mais profissional e coerente com a identidade OSSEL.

## Arquivos alterados
- `templates/index.html`
- `static/logo-ossel-assistencia.png`
- `REVISAO_OSSEL.md`

## Bugs encontrados
- Logo anterior era uma imagem quadrada com fundo azul, causando aparência de “bloco” e destoando da sidebar.
- O painel de andamento estava visualmente fraco, fazendo a barra parecer ausente.
- Em projetos concluídos, o painel podia mostrar estados repetidos de conclusão.

## Melhorias visuais aplicadas
- Logo tratado com transparência e drop-shadow leve.
- Área de marca mais limpa.
- Barra de progresso mais alta, moderna e visível.
- Chips de status menos redundantes.

## Melhorias funcionais aplicadas
- Uma única barra de progresso funcional por card.
- Percentual exibido no topo e preenchimento sincronizado pelo valor `progresso` do projeto.
- Estado “Concluído” simplificado quando o progresso está em 100%.
