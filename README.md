# OSSEL Dashboard TI - Versão 11

## Alterações principais

- Login separado em duas abas:
  - **Entrar**: para usuários que já criaram senha.
  - **Primeiro acesso**: para ativar usuário e criar senha.
- Evita o erro visual de "senhas não conferem" para usuário já cadastrado.
- Mantém usuários padrão:
  - ADM: administrador
  - Thiago: administrador
  - Denis: administrador
  - Filipe: operação de Troca de Máquinas
  - Eduardo: operação de Troca de Máquinas
- Senhas criptografadas no SQLite.
- Mantém múltiplos responsáveis por projeto.
- Mantém barra única de percentual, sem botões rápidos.

## Persistência de senhas no Render

Para as senhas continuarem salvas após novos deploys, configure no Render:

1. **Disk / Persistent Disk**
   - Mount path: `/var/data`

2. **Environment Variable**
   - Key: `DATA_DIR`
   - Value: `/var/data`

Sem Persistent Disk, o Render pode recriar o banco SQLite a cada deploy e as senhas precisarão ser cadastradas novamente.

## Deploy

Build Command:

```bash
pip install -r requirements.txt
```

Start Command:

```bash
gunicorn app:app
```
