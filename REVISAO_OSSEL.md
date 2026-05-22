# Revisão OSSEL - Versão Profissional V3

## Correção principal

O problema relatado foi que um projeto excluído reduzia o total temporariamente, mas voltava após novo login. Isso indica que a alteração não estava sendo confirmada de forma confiável no backup remoto usado para restaurar os dados.

A versão V3 corrige isso com persistência verificada:

- Após qualquer alteração, o backend grava no GitHub.
- Depois da gravação, o backend lê novamente o arquivo remoto.
- O conteúdo remoto é comparado com o conteúdo enviado.
- A transação local só é confirmada se a verificação passar.
- Se falhar, a API retorna erro e a alteração é cancelada.

## Melhorias de sincronização

- O GitHub passa a ser tratado como fonte de verdade quando `GITHUB_REPO` e `GITHUB_TOKEN` estão configurados.
- Login e listagem de projetos sincronizam o SQLite local com o JSON remoto.
- Adicionada tabela `app_state` para guardar checksum, data remota e total de projetos.
- Adicionado endpoint admin `/api/admin/sync-from-github`.
- Adicionado botão **Sincronizar GitHub** no menu lateral.

## Melhorias funcionais

- Botão **Concluir** em cada projeto editável.
- Botão **Salvar progresso** junto ao slider.
- Slider continua salvando ao alterar, mas agora o usuário tem uma ação explícita de salvamento.
- Exclusão recarrega a lista do backend depois do sucesso, evitando diferença entre tela e banco.
- Toasts agora indicam quando o GitHub foi salvo e verificado.

## Melhorias visuais

- Logo transparente criada para tela inicial, menu e cabeçalho.
- Sidebar mais limpa, sem bloco quadrado pesado para a marca.
- Cabeçalho com Centro de Tecnologia e Governança de Projetos.
- Cards e controles com acabamento mais profissional para governança de TI.
- Destaques visuais melhores para progresso, riscos e entregas.

## Arquivos principais alterados

- `app.py`
- `templates/index.html`
- `templates/login.html`
- `static/js/dashboard.js`
- `static/css/styles.css`
- `static/img/logo-ossel-white-transparent.png`
- `static/img/logo-ossel-blue-transparent.png`
- `README.md`
- `REVISAO_OSSEL.md`
