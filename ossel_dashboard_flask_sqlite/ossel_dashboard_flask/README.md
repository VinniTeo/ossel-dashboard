# OSSEL Dashboard TI - Flask + SQLite

Sistema web para controle de projetos e troca de máquinas com banco SQLite interno.

## Rodar localmente

```bash
pip install -r requirements.txt
python app.py
```

Acesse: http://127.0.0.1:5000

PIN padrão: `ossel2026`

Para alterar o PIN, configure a variável de ambiente `APP_PIN`.

## Subir no Render

1. Crie uma conta em https://render.com
2. Crie um novo repositório no GitHub com estes arquivos
3. No Render, clique em **New > Web Service**
4. Conecte o repositório
5. Build Command: `pip install -r requirements.txt`
6. Start Command: `gunicorn app:app`
7. Adicione um **Persistent Disk** montado em `/opt/render/project/src/instance`
8. Crie a variável de ambiente `APP_PIN` com um PIN de sua escolha

O banco SQLite ficará salvo no disco persistente.

## Funcionalidades

- Painel executivo com KPIs
- Ordem operacional por prazo
- Slider de andamento por item
- Botão concluir = 100% / Entregue
- Edição de prazo, unidade, setor e observação
- Todos veem os dados atualizados pelo banco online quando hospedado
- Atualização automática da tela a cada 10 segundos
- Exportação CSV
