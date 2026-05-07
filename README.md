# OSSEL Dashboard - Versão profissional V7

Sistema Flask + SQLite para acompanhamento executivo e operacional de projetos.

## Deploy no Render

Build Command:
```bash
pip install -r requirements.txt
```

Start Command:
```bash
gunicorn app:app
```

## Importante: manter senhas e dados após atualizações

Para que usuários, senhas e alterações fiquem salvos mesmo após novos deploys, configure um **Persistent Disk** no Render e monte em:

```text
/var/data
```

Opcionalmente, adicione a variável de ambiente:

```text
DATA_DIR=/var/data
```

O sistema usará automaticamente esse caminho para o banco SQLite. Sem disco persistente, o Render pode recriar o banco em alguns deploys.

## Usuários iniciais

- ADM: administrador
- Thiago: administrador
- Denis: administrador
- Filipe: operação Troca de Máquinas
- Eduardo: operação Troca de Máquinas

As senhas são criadas no primeiro acesso e salvas criptografadas.
