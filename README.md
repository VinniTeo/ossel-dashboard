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


## Versão v5 - Diretoria e Governança

Melhorias adicionadas:
- Usuário Denis criado com perfil ADM e senha definida no primeiro acesso.
- Destaque visual automático para projetos com prazo vencido ou próximo.
- Correção das unidades/localidades para nomes completos, como São Roque, Sorocaba Central e SA - ADM.
- Radar executivo no topo com vencidos, próximos 21 dias, baixo avanço e próxima entrega.
- Cards, linha cronológica, operação e mapa com alertas visuais por prazo.
- Migração automática do banco já publicado para corrigir unidades antigas abreviadas.
