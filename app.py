import csv
import io
import json
import os
import sqlite3
import base64
import urllib.error
import urllib.request
from functools import wraps
import hashlib
import hmac
import secrets
from datetime import datetime
from pathlib import Path
from flask import Flask, jsonify, redirect, render_template, request, Response, session, url_for

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR_ENV = os.environ.get("DATA_DIR")
if DATA_DIR_ENV:
    DB_DIR = Path(DATA_DIR_ENV)
elif Path("/var/data").exists():
    DB_DIR = Path("/var/data")
else:
    DB_DIR = BASE_DIR / "instance"
DB_PATH = DB_DIR / "ossel_dashboard.db"
SEED_PATH = BASE_DIR / "data" / "seed.json"

DEFAULT_USERS = [
    ("ADM", "Administrador", "admin"),
    ("Thiago", "Thiago", "admin"),
    ("Denis", "Denis", "admin"),
    ("Filipe", "Filipe", "troca"),
    ("Eduardo", "Eduardo", "troca"),
]


# Login sem banco persistente: as senhas ficam nas variaveis de ambiente do Render.
# Configure no Render, em Environment Variables:
# ADM_PASSWORD, THIAGO_PASSWORD, DENIS_PASSWORD, FILIPE_PASSWORD, EDUARDO_PASSWORD
# Se nao configurar, o sistema usa senhas temporarias abaixo. Troque no Render antes de liberar para a equipe.
DEFAULT_ENV_PASSWORDS = {
    "ADM": "Ossel@Adm2026",
    "Thiago": "Ossel@Thiago2026",
    "Denis": "Ossel@Denis2026",
    "Filipe": "Ossel@Filipe2026",
    "Eduardo": "Ossel@Eduardo2026",
}


def env_key_for_user(username):
    return f"{str(username or '').strip().upper()}_PASSWORD".replace(" ", "_")


def get_login_user(username):
    normalized = (username or "").strip()
    for u, display_name, role in DEFAULT_USERS:
        if u.lower() == normalized.lower():
            return {"username": u, "display_name": display_name, "role": role}
    return None


def get_env_password(username):
    user = get_login_user(username)
    if not user:
        return None
    return os.environ.get(env_key_for_user(user["username"]), DEFAULT_ENV_PASSWORDS.get(user["username"]))


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "ossel-dashboard-secret-change-me")


def parse_date_br(value):
    if not value or "mediante" in str(value).lower():
        return None
    try:
        return datetime.strptime(value[:10], "%d/%m/%Y").date().isoformat()
    except Exception:
        return None


def date_to_br(value):
    if not value:
        return ""
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return value


def infer_unidade(nome):
    """Identifica a unidade com nome completo a partir do nome do projeto."""
    original = str(nome or "").strip()
    n = original.lower()
    known = [
        "Sorocaba Central", "Vila Assis", "Millenium", "Giullias SBA", "Salto", "Votorantim", "Araçoiaba", "São Roque",
        "SA - INOVA", "SA - ADM", "SA - PERI 179", "SA - PERI 75", "SA - COMFLORES", "SA - ABAVILLI JARDIM",
        "SA - ABAVILLI BOSQUE", "SA - QUADRO ADM", "SA - QUADRO", "SA - LEONI", "SA - MONT CRISTO",
        "SCS - FUNE", "SCS - VEL GOIÁS", "SCS - GIULLIAS", "MAUA I", "MAUA II",
        "SP - FUNE JARDIM AVELINO", "SP - OSSEL HELIOPOLIS", "SP - FLOR DO SOL", "SP - GIULLIAS"
    ]
    for unit in sorted(known, key=len, reverse=True):
        if unit.lower() in n:
            return unit
    cleaned = original.replace("Troca de maquinas -", "").replace("Troca das antenas -", "").strip()
    if " - " in cleaned:
        parts = cleaned.split(" - ")
        return " - ".join(parts[:2]).strip() if len(parts) >= 2 else parts[0].strip()
    return cleaned or "Sem unidade definida"


def normalize_unidade(value, nome="", projeto_pai=""):
    current = (value or "").strip()
    source = " ".join([str(nome or ""), str(projeto_pai or "")])
    inferred = infer_unidade(source)
    if not current or current in ["São", "SA", "SCS", "SP", "MAUA"]:
        return inferred
    if current == "Sao Roque":
        return "São Roque"
    return current


def status_from_progress(progress):
    progress = int(progress or 0)
    if progress >= 100:
        return "Entregue"
    if progress <= 0:
        return "Pendente"
    return "Em andamento"


def make_password_hash(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200000).hex()
    return f"pbkdf2_sha256$200000${salt}${digest}"


def verify_password(stored_hash, password):
    try:
        scheme, iterations, salt, digest = stored_hash.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        calc = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations)).hex()
        return hmac.compare_digest(calc, digest)
    except Exception:
        return False



# Persistência gratuita opcional via GitHub.
# Use quando o Render Free não puder ter Persistent Disk.
# Configure no Render:
#   GITHUB_TOKEN = token com permissão de escrita no repositório
#   GITHUB_REPO = usuario/repositorio  (ex.: VinniTeo/ossel-dashboard)
# Opcional:
#   GITHUB_DATA_PATH = data/runtime_projects.json
GITHUB_DATA_PATH = os.environ.get("GITHUB_DATA_PATH", "data/runtime_projects.json")


def github_repo():
    return (os.environ.get("GITHUB_REPO") or "").strip()


def github_token():
    return (os.environ.get("GITHUB_TOKEN") or "").strip()


def github_enabled():
    return bool(github_repo() and github_token())


# Notificações opcionais por Microsoft Teams / Webhook.
# Configure TEAMS_WEBHOOK_URL no Render se quiser receber alertas quando projetos forem atualizados.
def teams_webhook_url():
    return (os.environ.get("TEAMS_WEBHOOK_URL") or "").strip()


def send_teams_notification(title, message):
    if not teams_webhook_url():
        return False
    try:
        payload = {"text": f"**{title}**\n\n{message}"}
        req = urllib.request.Request(
            teams_webhook_url(),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10).read()
        return True
    except Exception as e:
        print("Teams notification error:", e)
        return False


def github_request(method, url, payload=None):
    data = None
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ossel-dashboard",
    }
    if github_token():
        headers["Authorization"] = f"Bearer {github_token()}"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def github_content_url():
    path = GITHUB_DATA_PATH.strip("/")
    return f"https://api.github.com/repos/{github_repo()}/contents/{path}"


LAST_GITHUB_HISTORY = []

def load_projects_from_github():
    global LAST_GITHUB_HISTORY
    LAST_GITHUB_HISTORY = []
    if not github_enabled():
        return None
    try:
        data = github_request("GET", github_content_url())
        content = base64.b64decode(data.get("content", "")).decode("utf-8")
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            LAST_GITHUB_HISTORY = parsed.get("history") or []
            return parsed.get("projects") or []
        if isinstance(parsed, list):
            return parsed
    except urllib.error.HTTPError as e:
        # 404 significa que ainda não existe backup; o seed local será usado.
        if getattr(e, "code", None) != 404:
            print("GitHub restore error:", e)
    except Exception as e:
        print("GitHub restore error:", e)
    return None


def serialize_projects_for_backup(conn):
    rows = conn.execute("SELECT * FROM projects ORDER BY COALESCE(prazo,'9999-12-31'), ordem, id").fetchall()
    return [dict(r) for r in rows]


def serialize_history_for_backup(conn):
    try:
        rows = conn.execute("SELECT * FROM history ORDER BY id DESC LIMIT 500").fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def restore_history_from_github(history_items, cur):
    if not isinstance(history_items, list):
        return
    existing = cur.execute("SELECT COUNT(*) FROM history").fetchone()[0]
    if existing:
        return
    for h in history_items[:500]:
        cur.execute(
            """
            INSERT INTO history (project_id, action, field, old_value, new_value, user_name, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                h.get("project_id") or 0,
                h.get("action") or "importado",
                h.get("field") or "",
                h.get("old_value") or "",
                h.get("new_value") or "",
                h.get("user_name") or "",
                h.get("created_at") or datetime.now().isoformat(timespec="seconds"),
            ),
        )


def backup_projects_to_github():
    if not github_enabled():
        return False
    try:
        conn = connect()
        projects = serialize_projects_for_backup(conn)
        history = serialize_history_for_backup(conn)
        conn.close()
        payload_json = json.dumps({
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "projects": projects,
            "history": history,
        }, ensure_ascii=False, indent=2)
        content = base64.b64encode(payload_json.encode("utf-8")).decode("ascii")
        sha = None
        try:
            current = github_request("GET", github_content_url())
            sha = current.get("sha")
        except urllib.error.HTTPError as e:
            if getattr(e, "code", None) != 404:
                raise
        body = {
            "message": "Atualiza dados do painel OSSEL",
            "content": content,
        }
        if sha:
            body["sha"] = sha
        github_request("PUT", github_content_url(), body)
        return True
    except Exception as e:
        print("GitHub backup error:", e)
        return False


def insert_project_row(cur, item, ordem_fallback=999):
    cur.execute(
        """
        INSERT INTO projects
        (nome, projeto_pai, unidade, setor, categoria, progresso, status, prazo, obs, ordem, updated_at, updated_by, assigned_to, evidencias, sla_dias)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            item.get("nome") or "Novo item",
            item.get("projeto_pai") or "",
            item.get("unidade") or normalize_unidade("", item.get("nome", ""), item.get("projeto_pai", "")),
            item.get("setor") or "",
            item.get("categoria") or "Outros",
            int(item.get("progresso") or 0),
            item.get("status") or status_from_progress(item.get("progresso") or 0),
            item.get("prazo") or parse_date_br(item.get("prazo_br")),
            item.get("obs") or "",
            item.get("ordem") or ordem_fallback,
            item.get("updated_at") or datetime.now().isoformat(timespec="seconds"),
            item.get("updated_by") or "",
            item.get("assigned_to") or "",
            item.get("evidencias") or "[]",
            int(item.get("sla_dias") or 21),
        ),
    )

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            projeto_pai TEXT,
            unidade TEXT,
            setor TEXT,
            categoria TEXT NOT NULL,
            progresso INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'Pendente',
            prazo TEXT,
            obs TEXT,
            ordem INTEGER,
            updated_at TEXT,
            updated_by TEXT,
            assigned_to TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            role TEXT NOT NULL,
            password_hash TEXT,
            must_set_password INTEGER NOT NULL DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    # Migra bancos antigos sem apagar dados existentes.
    project_cols = [r[1] for r in cur.execute("PRAGMA table_info(projects)").fetchall()]
    if "assigned_to" not in project_cols:
        cur.execute("ALTER TABLE projects ADD COLUMN assigned_to TEXT")
    if "evidencias" not in project_cols:
        cur.execute("ALTER TABLE projects ADD COLUMN evidencias TEXT DEFAULT '[]'")
    if "sla_dias" not in project_cols:
        cur.execute("ALTER TABLE projects ADD COLUMN sla_dias INTEGER DEFAULT 21")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            field TEXT,
            old_value TEXT,
            new_value TEXT,
            user_name TEXT,
            created_at TEXT
        )
        """
    )

    for username, display_name, role in DEFAULT_USERS:
        now = datetime.now().isoformat(timespec="seconds")
        existing = cur.execute("SELECT * FROM users WHERE lower(username)=lower(?)", (username,)).fetchone()
        if existing:
            # Atualiza apenas nome/permissão. Mantém senha já cadastrada pelo usuário.
            cur.execute(
                "UPDATE users SET display_name=?, role=?, updated_at=? WHERE id=?",
                (display_name, role, now, existing["id"]),
            )
        else:
            cur.execute(
                """
                INSERT INTO users
                (username, display_name, role, password_hash, must_set_password, created_at, updated_at)
                VALUES (?, ?, ?, NULL, 1, ?, ?)
                """,
                (username, display_name, role, now, now),
            )
    count = cur.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    if count == 0:
        restored = load_projects_from_github()
        if restored:
            for idx, item in enumerate(restored, start=1):
                insert_project_row(cur, item, idx)
        elif SEED_PATH.exists():
            seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
            ordem = 1
            for p in seed:
                subs = p.get("subprojetos") or []
                # Grava também o projeto pai para manter a visão executiva completa.
                insert_project_row(cur, {
                    "nome": p.get("nome", ""),
                    "projeto_pai": "",
                    "unidade": infer_unidade(p.get("nome", "")) if p.get("categoria") in ["Troca de Máquinas", "Antenas"] else "",
                    "setor": "",
                    "categoria": p.get("categoria", "Outros"),
                    "progresso": int(p.get("progresso") or 0),
                    "status": status_from_progress(p.get("progresso") or 0),
                    "prazo": parse_date_br(p.get("prazo")),
                    "obs": p.get("obs") or "",
                    "ordem": ordem,
                }, ordem)
                ordem += 1
                for sp in subs:
                    insert_project_row(cur, {
                        "nome": sp.get("nome", ""),
                        "projeto_pai": p.get("nome", ""),
                        "unidade": infer_unidade(p.get("nome", "")),
                        "setor": sp.get("nome", ""),
                        "categoria": p.get("categoria", "Outros"),
                        "progresso": int(sp.get("progresso") or 0),
                        "status": status_from_progress(sp.get("progresso") or 0),
                        "prazo": parse_date_br(sp.get("prazo")),
                        "obs": sp.get("obs") or p.get("obs") or "",
                        "ordem": ordem,
                    }, ordem)
                    ordem += 1
    # Restaura histórico salvo no GitHub, quando disponível.
    try:
        restore_history_from_github(LAST_GITHUB_HISTORY, cur)
    except Exception as e:
        print("History restore error:", e)

    # Corrige nomes de unidades antigas ou abreviadas sem apagar dados existentes.
    for row in cur.execute("SELECT id, nome, projeto_pai, unidade FROM projects").fetchall():
        fixed = normalize_unidade(row["unidade"], row["nome"], row["projeto_pai"])
        if fixed != (row["unidade"] or ""):
            cur.execute("UPDATE projects SET unidade=? WHERE id=?", (fixed, row["id"]))
    conn.commit()
    conn.close()


def rows_to_dict(rows):
    out = []
    for r in rows:
        d = dict(r)
        d["prazo_br"] = date_to_br(d.get("prazo"))
        out.append(d)
    return out




def seed_projects(clear_existing=False):
    """Importa a base completa do seed.json. Use clear_existing=True para substituir tudo."""
    conn = connect()
    cur = conn.cursor()
    if clear_existing:
        cur.execute("DELETE FROM projects")
        cur.execute("DELETE FROM sqlite_sequence WHERE name='projects'")
    count = cur.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    if count == 0 and SEED_PATH.exists():
        seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
        ordem = 1
        for p in seed:
            subs = p.get("subprojetos") or []
            # Também grava o projeto pai para manter a visão executiva completa.
            cur.execute(
                """
                INSERT INTO projects
                (nome, projeto_pai, unidade, setor, categoria, progresso, status, prazo, obs, ordem, updated_at, assigned_to)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    p.get("nome", ""),
                    "",
                    infer_unidade(p.get("nome", "")) if p.get("categoria") in ["Troca de Máquinas", "Antenas"] else "",
                    "",
                    p.get("categoria", "Outros"),
                    int(p.get("progresso") or 0),
                    status_from_progress(p.get("progresso") or 0),
                    parse_date_br(p.get("prazo")),
                    p.get("obs") or "",
                    ordem,
                    datetime.now().isoformat(timespec="seconds"),
                    "",
                ),
            )
            ordem += 1
            for sp in subs:
                cur.execute(
                    """
                    INSERT INTO projects
                    (nome, projeto_pai, unidade, setor, categoria, progresso, status, prazo, obs, ordem, updated_at, assigned_to)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        sp.get("nome", ""),
                        p.get("nome", ""),
                        infer_unidade(p.get("nome", "")),
                        sp.get("nome", ""),
                        p.get("categoria", "Outros"),
                        int(sp.get("progresso") or 0),
                        status_from_progress(sp.get("progresso") or 0),
                        parse_date_br(sp.get("prazo")),
                        sp.get("obs") or p.get("obs") or "",
                        ordem,
                        datetime.now().isoformat(timespec="seconds"),
                            "",
                    ),
                )
                ordem += 1
    conn.commit()
    conn.close()

@app.before_request
def ensure_db():
    init_db()


def current_user():
    if not require_auth():
        return None
    return {
        "id": session.get("user_id"),
        "username": session.get("username"),
        "display_name": session.get("display_name"),
        "role": session.get("role"),
        "is_admin": session.get("role") == "admin",
    }


def require_auth():
    return bool(session.get("auth") and session.get("user_id") and session.get("role"))


def require_admin():
    return bool(session.get("auth") and session.get("role") == "admin")


def can_edit_project_row(row):
    if not require_auth() or row is None:
        return False
    if session.get("role") == "admin":
        return True
    if session.get("role") == "troca" and row["categoria"] == "Troca de Máquinas":
        return True
    return False


def get_user_by_username(username):
    conn = connect()
    row = conn.execute("SELECT * FROM users WHERE lower(username)=lower(?)", (username or "",)).fetchone()
    conn.close()
    return row


def log_history(conn, project_id, action, field="", old_value="", new_value=""):
    conn.execute(
        """
        INSERT INTO history (project_id, action, field, old_value, new_value, user_name, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            project_id,
            action,
            field,
            str(old_value or ""),
            str(new_value or ""),
            session.get("display_name") or session.get("username") or "Sistema",
            datetime.now().isoformat(timespec="seconds"),
        ),
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    """Autenticacao sem gravar senha no SQLite.
    Ideal para Render Free, pois as credenciais ficam em Environment Variables,
    que permanecem entre deploys sem Persistent Disk.
    """
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        login_user = get_login_user(username)
        expected_password = get_env_password(username)

        if not login_user or not expected_password:
            return render_template("login.html", erro="Usuário ou senha inválidos.", username=username)

        if not hmac.compare_digest(str(expected_password), str(password)):
            return render_template("login.html", erro="Usuário ou senha inválidos.", username=username)

        # Garante que o usuario exista no banco apenas para APIs/listas de responsaveis.
        db_user = get_user_by_username(login_user["username"])
        if not db_user:
            conn = connect()
            now = datetime.now().isoformat(timespec="seconds")
            conn.execute(
                """
                INSERT INTO users
                (username, display_name, role, password_hash, must_set_password, created_at, updated_at)
                VALUES (?, ?, ?, NULL, 0, ?, ?)
                """,
                (login_user["username"], login_user["display_name"], login_user["role"], now, now),
            )
            conn.commit()
            conn.close()
            db_user = get_user_by_username(login_user["username"])

        session.clear()
        session["auth"] = True
        session["user_id"] = db_user["id"] if db_user else 0
        session["username"] = login_user["username"]
        session["display_name"] = login_user["display_name"]
        session["role"] = login_user["role"]
        return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def index():
    if not require_auth():
        return redirect(url_for("login"))
    return render_template("index.html", user=current_user())


@app.route("/api/me")
def api_me():
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401
    return jsonify(current_user())



@app.route("/api/users")
def api_users():
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401
    conn = connect()
    rows = conn.execute("SELECT username, display_name, role FROM users ORDER BY display_name").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/projects")
def api_projects():
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401
    conn = connect()
    rows = conn.execute("SELECT * FROM projects ORDER BY COALESCE(prazo,'9999-12-31'), ordem, id").fetchall()
    conn.close()
    return jsonify(rows_to_dict(rows))


@app.route("/api/projects/<int:project_id>", methods=["PATCH"])
def api_update_project(project_id):
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401
    conn = connect()
    row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Projeto não encontrado"}), 404
    if not can_edit_project_row(row):
        conn.close()
        return jsonify({"error": "Sem permissão para alterar este projeto"}), 403

    data = request.get_json(force=True) or {}
    if session.get("role") == "admin":
        allowed = ["nome", "projeto_pai", "unidade", "setor", "categoria", "progresso", "status", "prazo", "obs", "ordem", "assigned_to", "sla_dias"]
    else:
        # Usuários operacionais podem atualizar somente andamento e observações das trocas de máquinas.
        allowed = ["progresso", "obs"]
    updates = {}
    for k in allowed:
        if k in data:
            updates[k] = data[k]
    if "progresso" in updates:
        progress = max(0, min(100, int(float(updates["progresso"] or 0))))
        updates["progresso"] = progress
        updates["status"] = status_from_progress(progress)
    if "prazo" in updates and updates["prazo"] and "/" in str(updates["prazo"]):
        updates["prazo"] = parse_date_br(updates["prazo"])
    updates["updated_at"] = datetime.now().isoformat(timespec="seconds")
    updates["updated_by"] = session.get("display_name") or session.get("username") or ""
    if not updates:
        conn.close()
        return jsonify({"ok": True})
    for field, new_value in updates.items():
        old_value = row[field] if field in row.keys() else ""
        if str(old_value or "") != str(new_value or ""):
            log_history(conn, project_id, "alteracao", field, old_value, new_value)
    cols = ", ".join([f"{k}=?" for k in updates])
    values = list(updates.values()) + [project_id]
    conn.execute(f"UPDATE projects SET {cols} WHERE id=?", values)
    conn.commit()
    row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    conn.close()
    backup_projects_to_github()
    return jsonify(rows_to_dict([row])[0])


@app.route("/api/projects", methods=["POST"])
def api_create_project():
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401
    if not require_admin():
        return jsonify({"error": "Apenas ADM pode criar projetos"}), 403
    data = request.get_json(force=True) or {}
    progresso = max(0, min(100, int(float(data.get("progresso") or 0))))
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO projects (nome, projeto_pai, unidade, setor, categoria, progresso, status, prazo, obs, ordem, updated_at, updated_by, assigned_to, evidencias, sla_dias)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data.get("nome") or "Novo item",
            data.get("projeto_pai") or "",
            data.get("unidade") or "",
            data.get("setor") or "",
            data.get("categoria") or "Troca de Máquinas",
            progresso,
            status_from_progress(progresso),
            parse_date_br(data.get("prazo")) if data.get("prazo") else data.get("prazo_iso"),
            data.get("obs") or "",
            data.get("ordem") or 999,
            datetime.now().isoformat(timespec="seconds"),
            session.get("display_name") or session.get("username") or "",
            data.get("assigned_to") or "",
            data.get("evidencias") or "[]",
            int(data.get("sla_dias") or 21),
        ),
    )
    log_history(conn, cur.lastrowid, "criacao", "projeto", "", data.get("nome") or "Novo item")
    conn.commit()
    row = conn.execute("SELECT * FROM projects WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    backup_projects_to_github()
    return jsonify(rows_to_dict([row])[0]), 201


@app.route("/api/projects/<int:project_id>", methods=["DELETE"])
def api_delete_project(project_id):
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401
    if not require_admin():
        return jsonify({"error": "Apenas ADM pode excluir projetos"}), 403
    conn = connect()
    old = conn.execute("SELECT nome FROM projects WHERE id=?", (project_id,)).fetchone()
    log_history(conn, project_id, "exclusao", "projeto", old["nome"] if old else "", "")
    conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
    conn.commit()
    conn.close()
    backup_projects_to_github()
    return jsonify({"ok": True})



@app.route("/api/admin/reseed", methods=["POST"])
def api_reseed():
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401
    if not require_admin():
        return jsonify({"error": "Apenas ADM pode importar a base"}), 403
    data = request.get_json(silent=True) or {}
    if data.get("confirm") != "IMPORTAR_BASE_COMPLETA":
        return jsonify({"error": "Confirmação inválida"}), 400
    seed_projects(clear_existing=True)
    backup_projects_to_github()
    conn = connect()
    total = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    conn.close()
    return jsonify({"ok": True, "total": total})


@app.route("/api/projects/<int:project_id>/evidence", methods=["POST"])
def api_add_evidence(project_id):
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401
    conn = connect()
    row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Projeto não encontrado"}), 404
    if not can_edit_project_row(row):
        conn.close()
        return jsonify({"error": "Sem permissão para adicionar evidência"}), 403
    data = request.get_json(force=True) or {}
    name = (data.get("name") or "evidencia").strip()[:120]
    content = data.get("content") or ""
    if not content.startswith("data:"):
        conn.close()
        return jsonify({"error": "Formato de evidência inválido"}), 400
    if len(content) > 900000:
        conn.close()
        return jsonify({"error": "Arquivo muito grande. Use imagem leve de até ~600 KB."}), 400
    try:
        evidencias = json.loads(row["evidencias"] or "[]")
        if not isinstance(evidencias, list):
            evidencias = []
    except Exception:
        evidencias = []
    item = {
        "name": name,
        "content": content,
        "uploaded_by": session.get("display_name") or session.get("username") or "",
        "uploaded_at": datetime.now().isoformat(timespec="seconds"),
    }
    evidencias.append(item)
    evidencias = evidencias[-6:]
    conn.execute("UPDATE projects SET evidencias=?, updated_at=?, updated_by=? WHERE id=?", (
        json.dumps(evidencias, ensure_ascii=False),
        datetime.now().isoformat(timespec="seconds"),
        session.get("display_name") or session.get("username") or "",
        project_id,
    ))
    log_history(conn, project_id, "evidencia", "evidencias", "", name)
    conn.commit()
    row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    conn.close()
    backup_projects_to_github()
    return jsonify(rows_to_dict([row])[0])


@app.route("/api/history")
def api_history():
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401
    conn = connect()
    rows = conn.execute(
        """
        SELECT h.*, p.nome AS project_name, p.categoria AS project_category
        FROM history h
        LEFT JOIN projects p ON p.id = h.project_id
        ORDER BY h.id DESC
        LIMIT 300
        """
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/tv")
def tv_mode():
    if not require_auth():
        return redirect(url_for("login"))
    return render_template("index.html", user=current_user(), tv_mode=True)


@app.route("/report")
def report_page():
    if not require_auth():
        return redirect(url_for("login"))
    return render_template("index.html", user=current_user(), report_mode=True)

@app.route("/export.csv")
def export_csv():
    if not require_auth():
        return redirect(url_for("login"))
    conn = connect()
    rows = rows_to_dict(conn.execute("SELECT * FROM projects ORDER BY COALESCE(prazo,'9999-12-31'), ordem, id").fetchall())
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["ID", "Projeto", "Projeto Pai", "Unidade", "Setor", "Categoria", "Responsavel", "Progresso", "Status", "Prazo", "Observacao", "Atualizado em", "Atualizado por"])
    for r in rows:
        writer.writerow([r["id"], r["nome"], r["projeto_pai"], r["unidade"], r["setor"], r["categoria"], r.get("assigned_to", ""), r["progresso"], r["status"], r["prazo_br"], r["obs"], r["updated_at"], r["updated_by"]])
    return Response(output.getvalue(), mimetype="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=ossel_projetos.csv"})


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
