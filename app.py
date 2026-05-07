import csv
import io
import json
import os
import sqlite3
from functools import wraps
import hashlib
import hmac
import secrets
from datetime import datetime
from pathlib import Path
from flask import Flask, jsonify, redirect, render_template, request, Response, session, url_for

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "instance" / "ossel_dashboard.db"
SEED_PATH = BASE_DIR / "data" / "seed.json"

DEFAULT_USERS = [
    ("ADM", "Administrador", "admin"),
    ("Denis", "Denis", "admin"),
    ("Thiago", "Thiago", "troca"),
    ("Filipe", "Filipe", "troca"),
    ("Eduardo", "Eduardo", "troca"),
]

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
    """Extrai a unidade/localidade completa a partir do nome do projeto.
    Exemplos:
    - Troca de maquinas - SA - ADM -> SA - ADM
    - Troca das antenas - São Roque -> São Roque
    - Troca de maquinas - Sorocaba Central -> Sorocaba Central
    """
    raw = (nome or "").strip()
    for prefix in ["Troca de maquinas -", "Troca das antenas -"]:
        if raw.lower().startswith(prefix.lower()):
            return raw[len(prefix):].strip()
    return ""

def unidade_referencia(row):
    return infer_unidade(row["projeto_pai"] or row["nome"] or "")

def reparar_unidades_completas(conn):
    """Corrige bancos já publicados que tinham unidade abreviada, como 'São' em vez de 'São Roque'."""
    rows = conn.execute(
        "SELECT id, nome, projeto_pai, unidade, categoria FROM projects WHERE categoria IN ('Troca de Máquinas','Antenas')"
    ).fetchall()
    for row in rows:
        unidade = unidade_referencia(row)
        if unidade and row["unidade"] != unidade:
            conn.execute("UPDATE projects SET unidade=? WHERE id=?", (unidade, row["id"]))

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


def connect():
    DB_PATH.parent.mkdir(exist_ok=True)
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
            updated_by TEXT
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
    for username, display_name, role in DEFAULT_USERS:
        cur.execute(
            """
            INSERT OR IGNORE INTO users
            (username, display_name, role, password_hash, must_set_password, created_at, updated_at)
            VALUES (?, ?, ?, NULL, 1, ?, ?)
            """,
            (username, display_name, role, datetime.now().isoformat(timespec="seconds"), datetime.now().isoformat(timespec="seconds")),
        )
    count = cur.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    if count == 0 and SEED_PATH.exists():
        seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
        ordem = 1
        for p in seed:
            subs = p.get("subprojetos") or []
            if subs:
                for sp in subs:
                    cur.execute(
                        """
                        INSERT INTO projects
                        (nome, projeto_pai, unidade, setor, categoria, progresso, status, prazo, obs, ordem, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        ),
                    )
                    ordem += 1
            else:
                cur.execute(
                    """
                    INSERT INTO projects
                    (nome, projeto_pai, unidade, setor, categoria, progresso, status, prazo, obs, ordem, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    ),
                )
                ordem += 1
    reparar_unidades_completas(conn)
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
                (nome, projeto_pai, unidade, setor, categoria, progresso, status, prazo, obs, ordem, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                ),
            )
            ordem += 1
            for sp in subs:
                cur.execute(
                    """
                    INSERT INTO projects
                    (nome, projeto_pai, unidade, setor, categoria, progresso, status, prazo, obs, ordem, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    ),
                )
                ordem += 1
    reparar_unidades_completas(conn)
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


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""
        user = get_user_by_username(username)
        if not user:
            return render_template("login.html", erro="Usuário não encontrado.")

        if not user["password_hash"] or int(user["must_set_password"] or 0) == 1:
            if len(password) < 6:
                return render_template("login.html", erro="No primeiro acesso, crie uma senha com pelo menos 6 caracteres.", username=username)
            if password != confirm:
                return render_template("login.html", erro="As senhas não conferem.", username=username)
            conn = connect()
            conn.execute(
                "UPDATE users SET password_hash=?, must_set_password=0, updated_at=? WHERE id=?",
                (make_password_hash(password), datetime.now().isoformat(timespec="seconds"), user["id"]),
            )
            conn.commit()
            conn.close()
            user = get_user_by_username(username)
        elif not verify_password(user["password_hash"], password):
            return render_template("login.html", erro="Senha inválida.", username=username)

        session.clear()
        session["auth"] = True
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["display_name"] = user["display_name"]
        session["role"] = user["role"]
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
        allowed = ["nome", "projeto_pai", "unidade", "setor", "categoria", "progresso", "status", "prazo", "obs", "ordem"]
    else:
        # Usuários operacionais podem atualizar somente andamento e observações das trocas de máquinas.
        allowed = ["progresso", "obs"]
    updates = {}
    for k in allowed:
        if k in data:
            updates[k] = data[k]
    if "progresso" in updates:
        progress = max(0, min(100, int(updates["progresso"] or 0)))
        updates["progresso"] = progress
        updates["status"] = status_from_progress(progress)
    if "prazo" in updates and updates["prazo"] and "/" in str(updates["prazo"]):
        updates["prazo"] = parse_date_br(updates["prazo"])
    updates["updated_at"] = datetime.now().isoformat(timespec="seconds")
    updates["updated_by"] = session.get("display_name") or session.get("username") or ""
    if not updates:
        conn.close()
        return jsonify({"ok": True})
    cols = ", ".join([f"{k}=?" for k in updates])
    values = list(updates.values()) + [project_id]
    conn.execute(f"UPDATE projects SET {cols} WHERE id=?", values)
    conn.commit()
    row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    conn.close()
    return jsonify(rows_to_dict([row])[0])


@app.route("/api/projects", methods=["POST"])
def api_create_project():
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401
    if not require_admin():
        return jsonify({"error": "Apenas ADM pode criar projetos"}), 403
    data = request.get_json(force=True) or {}
    progresso = max(0, min(100, int(data.get("progresso") or 0)))
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO projects (nome, projeto_pai, unidade, setor, categoria, progresso, status, prazo, obs, ordem, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            data.get("updated_by") or "",
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM projects WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    return jsonify(rows_to_dict([row])[0]), 201


@app.route("/api/projects/<int:project_id>", methods=["DELETE"])
def api_delete_project(project_id):
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401
    if not require_admin():
        return jsonify({"error": "Apenas ADM pode excluir projetos"}), 403
    conn = connect()
    conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
    conn.commit()
    conn.close()
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
    conn = connect()
    total = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    conn.close()
    return jsonify({"ok": True, "total": total})

@app.route("/export.csv")
def export_csv():
    if not require_auth():
        return redirect(url_for("login"))
    conn = connect()
    rows = rows_to_dict(conn.execute("SELECT * FROM projects ORDER BY COALESCE(prazo,'9999-12-31'), ordem, id").fetchall())
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["ID", "Projeto", "Projeto Pai", "Unidade", "Setor", "Categoria", "Progresso", "Status", "Prazo", "Observacao", "Atualizado em", "Atualizado por"])
    for r in rows:
        writer.writerow([r["id"], r["nome"], r["projeto_pai"], r["unidade"], r["setor"], r["categoria"], r["progresso"], r["status"], r["prazo_br"], r["obs"], r["updated_at"], r["updated_by"]])
    return Response(output.getvalue(), mimetype="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=ossel_projetos.csv"})


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
