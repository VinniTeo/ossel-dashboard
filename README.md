# OSSEL Dashboard - Versao Profissional V10

## Deploy no Render

Build Command:
```bash
pip install -r requirements.txt
```

Start Command:
```bash
gunicorn app:app
```

## MUITO IMPORTANTE - senhas e dados persistentes

Para as senhas criadas no primeiro acesso continuarem salvas apos novos deploys, o Render precisa ter **Persistent Disk**.

Configure no Render:

- Disk mount path: `/var/data`
- Environment variable: `DATA_DIR=/var/data`

Sem Persistent Disk, o Render pode recriar o banco SQLite a cada novo deploy. Nesse caso, os usuarios voltam para primeiro acesso. Isso nao e erro do sistema: e comportamento da hospedagem quando nao existe disco persistente.

## Usuarios iniciais

- ADM: administrador
- Thiago: administrador
- Denis: administrador
- Filipe: operacao Troca de Maquinas
- Eduardo: operacao Troca de Maquinas

As senhas sao criadas no primeiro acesso e ficam criptografadas no banco.

## V10

- Removidos botoes rapidos 0/25/50/75/100.
- Mantida apenas a barra de percentual com exibicao visual do valor.
- Cards de projeto redesenhados com visual executivo.
- Alertas de prazo mais elegantes por borda, sombra e sinalizacao.
- Melhorias de UX na area operacional.
- Mantida selecao de multiplos responsaveis por projeto.
- Compatibilidade com banco antigo, sem apagar usuarios, senhas ou projetos existentes.
