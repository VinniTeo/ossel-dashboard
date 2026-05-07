# OSSEL Dashboard TI - Diretoria v3

Sistema web Flask + SQLite para controle executivo e operacional dos projetos.

## Usuários iniciais

- ADM: acesso completo.
- Thiago: altera apenas projetos da categoria Troca de Máquinas.
- Filipe: altera apenas projetos da categoria Troca de Máquinas.
- Eduardo: altera apenas projetos da categoria Troca de Máquinas.

No primeiro login, cada usuário escolhe sua própria senha. Não existe mais PIN visível na tela de login.

## Rodar localmente

```bash
pip install -r requirements.txt
python app.py
```

Acesse: http://127.0.0.1:5000

## Render

Build Command:
```bash
pip install -r requirements.txt
```

Start Command:
```bash
gunicorn app:app
```
