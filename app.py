import csv
import io
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from flask import Flask, jsonify, redirect, render_template, request, Response, session, url_for

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "instance" / "ossel_dashboard.db"
SEED_PATH = BASE_DIR / "data" / "seed.json"

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "ossel-dashboard-secret-change-me")
APP_PIN = os.environ.get("APP_PIN", "ossel2026")


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
    n = nome.replace("Troca de maquinas -", "").replace("Troca das antenas -", "").strip()
    if " - " in n:
        return n.split(" - ")[0].strip()
    parts = n.split()
    return parts[0].strip() if parts else ""


def status_from_progress(progress):
    progress = int(progress or 0)
    if progress >= 100:
        return "Entregue"
    if progress <= 0:
        return "Pendente"
    return "Em andamento"


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
    conn.commit()
    conn.close()

@app.before_request
def ensure_db():
    init_db()


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("pin") == APP_PIN:
            session["auth"] = True
            return redirect(url_for("index"))
        return render_template("login.html", erro="PIN inválido")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


def require_auth():
    return bool(session.get("auth"))


@app.route("/")
def index():
    if not require_auth():
        return redirect(url_for("login"))
    return render_template("index.html")


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
    data = request.get_json(force=True) or {}
    allowed = ["nome", "projeto_pai", "unidade", "setor", "categoria", "progresso", "status", "prazo", "obs", "ordem", "updated_by"]
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
    if not updates:
        return jsonify({"ok": True})
    cols = ", ".join([f"{k}=?" for k in updates])
    values = list(updates.values()) + [project_id]
    conn = connect()
    conn.execute(f"UPDATE projects SET {cols} WHERE id=?", values)
    conn.commit()
    row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    conn.close()
    return jsonify(rows_to_dict([row])[0])


@app.route("/api/projects", methods=["POST"])
def api_create_project():
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401
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
    conn = connect()
    conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})



@app.route("/api/admin/reseed", methods=["POST"])
def api_reseed():
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401
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
