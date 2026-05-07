# OSSEL Dashboard Executivo - V4

Sistema web Flask + SQLite para controle executivo de projetos.

## Login
- Usuarios cadastrados no banco: ADM, Thiago, Filipe e Eduardo.
- A tela nao exibe usuarios nem PIN.
- No primeiro acesso, o usuario define a propria senha.
- ADM tem acesso completo.
- Usuarios operacionais alteram apenas projetos da categoria Troca de Maquinas.

## Deploy Render
Build Command:
```bash
pip install -r requirements.txt
```
Start Command:
```bash
gunicorn app:app
```

## Novidades V4
- Login mais profissional e sem exposicao de usuarios.
- Logo OSSEL no login e no painel.
- Nova visao executiva com score, recomendacao e graficos.
- Aba Ordem Cronologica com todos os projetos.
- Observacoes editaveis por projeto.
- Dark mode.
- Mapa de unidades com nome completo.
- Melhorias visuais para apresentacao a diretoria.
