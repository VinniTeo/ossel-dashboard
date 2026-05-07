# OSSEL Dashboard Executivo - V5.1 Corrigido

Correções desta versão:

- Restaura automaticamente a base completa quando o banco estiver vazio.
- Corrige compatibilidade com bancos antigos já criados no Render.
- Mantém Denis como ADM.
- Mantém destaque visual para prazos vencidos e prazos próximos.
- Mantém correção dos nomes completos das unidades.

## Deploy no Render

Build Command:

```bash
pip install -r requirements.txt
```

Start Command:

```bash
gunicorn app:app
```

Root Directory: deixe vazio se os arquivos estiverem na raiz do GitHub.
