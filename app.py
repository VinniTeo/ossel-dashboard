import base64
import csv
import io
import json
import logging
import os
import re
import secrets
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import hmac
from flask import Flask, Response, jsonify, redirect, render_template, request, session, url_for

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
DEFAULT_GITHUB_DATA_PATH = "data/runtime_projects.json"

DEFAULT_USERS = [
    ("ADM", "Administrador", "admin"),
    ("Thiago", "Thiago", "admin"),
    ("Denis", "Denis", "admin"),
    ("Filipe", "Filipe", "troca"),
    ("Eduardo", "Eduardo", "troca"),
]

# Senhas abaixo existem apenas para desenvolvimento local. Em produção, configure as variáveis no Render.
LOCAL_DEV_PASSWORDS = {
    "ADM": "Ossel@Adm2026",
    "Thiago": "Ossel@Thiago2026",
    "Denis": "Ossel@Denis2026",
    "Filipe": "Ossel@Filipe2026",
    "Eduardo": "Ossel@Eduardo2026",
}

VALID_STATUSES = {"Pendente", "Em andamento", "Entregue"}
VALID_CATEGORIES = {
    "Troca de Máquinas",
    "Antenas",
    "Sistemas",
    "Infraestrutura",
    "Projetos",
    "Outros",
}
PROJECT_COLUMNS = [
    "id",
    "nome",
    "projeto_pai",
    "unidade",
    "setor",
    "categoria",
    "progresso",
    "status",
    "prazo",
    "obs",
    "ordem",
    "updated_at",
    "updated_by",
    "assigned_to",
]
MUTATING_METHODS = {"POST", "PATCH", "PUT", "DELETE"}
LOGIN_ATTEMPTS: Dict[str, List[float]] = {}

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger("ossel-dashboard")


def is_production() -> bool:
    flags = [
        os.environ.get("APP_ENV"),
        os.environ.get("FLASK_ENV"),
        os.environ.get("ENV"),
        os.environ.get("RENDER"),
        os.environ.get("RENDER_SERVICE_ID"),
    ]
    return any(str(v or "").lower() in {"production", "prod", "true"} for v in flags) or bool(os.environ.get("RENDER_SERVICE_ID"))


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=is_production(),
    PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 7,
    JSON_AS_ASCII=False,
)
if not os.environ.get("SECRET_KEY") and is_production():
    logger.warning("SECRET_KEY não configurada; sessões serão invalidadas a cada reinício. Configure no Render.")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_date_br(value: Any) -> Optional[str]:
    if not value or "mediante" in str(value).lower():
        return None
    raw = str(value).strip()
    try:
        return datetime.strptime(raw[:10], "%d/%m/%Y").date().isoformat()
    except Exception:
        return None


def parse_date_any(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    raw = str(value).strip()
    if not raw:
        return None
    if "/" in raw:
        return parse_date_br(raw)
    if re.match(r"^\d{4}-\d{2}-\d{2}$", raw[:10]):
        return raw[:10]
    return None


def date_to_br(value: Any) -> str:
    if not value:
        return ""
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return str(value)


def clean_text(value: Any, max_len: int = 500) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\x00", "").strip()
    if len(text) > max_len:
        text = text[:max_len]
    return text


def clamp_int(value: Any, minimum: int = 0, maximum: int = 100, default: int = 0) -> int:
    try:
        num = int(float(value))
    except Exception:
        num = default
    return max(minimum, min(maximum, num))


def infer_unidade(nome: Any) -> str:
    original = str(nome or "").strip()
    n = original.lower()
    known = [
        "Sorocaba Central",
        "Vila Assis",
        "Millenium",
        "Giullias SBA",
        "Salto",
        "Votorantim",
        "Araçoiaba",
        "São Roque",
        "SA - INOVA",
        "SA - ADM",
        "SA - PERI 179",
        "SA - PERI 75",
        "SA - COMFLORES",
        "SA - ABAVILLI JARDIM",
        "SA - ABAVILLI BOSQUE",
        "SA - QUADRO ADM",
        "SA - QUADRO",
        "SA - LEONI",
        "SA - MONT CRISTO",
        "SCS - FUNE",
        "SCS - VEL GOIÁS",
        "SCS - GIULLIAS",
        "MAUA I",
        "MAUA II",
        "SP - FUNE JARDIM AVELINO",
        "SP - OSSEL HELIOPOLIS",
        "SP - FLOR DO SOL",
        "SP - GIULLIAS",
    ]
    for unit in sorted(known, key=len, reverse=True):
        if unit.lower() in n:
            return unit
    cleaned = original.replace("Troca de maquinas -", "").replace("Troca de máquinas -", "").replace("Troca das antenas -", "").strip()
    if " - " in cleaned:
        parts = cleaned.split(" - ")
        return " - ".join(parts[:2]).strip() if len(parts) >= 2 else parts[0].strip()
    return cleaned or "Sem unidade definida"


def normalize_unidade(value: Any, nome: Any = "", projeto_pai: Any = "") -> str:
    current = clean_text(value, 120)
    source = " ".join([str(nome or ""), str(projeto_pai or "")])
    inferred = infer_unidade(source)
    if not current or current in ["São", "SA", "SCS", "SP", "MAUA"]:
        return inferred
    if current == "Sao Roque":
        return "São Roque"
    return current


def status_from_progress(progress: Any) -> str:
    progress_int = clamp_int(progress)
    if progress_int >= 100:
        return "Entregue"
    if progress_int <= 0:
        return "Pendente"
    return "Em andamento"


def normalize_status(value: Any, progress: Any = None) -> str:
    status = clean_text(value, 40)
    if status in VALID_STATUSES:
        return status
    return status_from_progress(progress)


def env_key_for_user(username: str) -> str:
    return f"{str(username or '').strip().upper()}_PASSWORD".replace(" ", "_")


def get_login_user(username: str) -> Optional[Dict[str, str]]:
    normalized = (username or "").strip()
    for u, display_name, role in DEFAULT_USERS:
        if u.lower() == normalized.lower():
            return {"username": u, "display_name": display_name, "role": role}
    return None


def get_env_password(username: str) -> Optional[str]:
    user = get_login_user(username)
    if not user:
        return None
    configured = os.environ.get(env_key_for_user(user["username"]))
    if configured:
        return configured
    if is_production():
        logger.warning("Senha não configurada para usuário %s", user["username"])
        return None
    return LOCAL_DEV_PASSWORDS.get(user["username"])


def get_csrf_token() -> str:
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


app.jinja_env.globals["csrf_token"] = get_csrf_token


def validate_csrf() -> bool:
    expected = session.get("_csrf_token") or ""
    supplied = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token") or ""
    return bool(expected and supplied and hmac.compare_digest(str(expected), str(supplied)))


@app.before_request
def security_gate() -> Optional[Response]:
    if request.endpoint == "static":
        return None
    ensure_db_once()
    if request.method in MUTATING_METHODS and not validate_csrf():
        # Devolve um código estável para o frontend renovar o token automaticamente
        # e repetir a ação sem obrigar o usuário a perder a alteração em andamento.
        if request.path.startswith("/api/"):
            session.modified = True
            return jsonify({
                "error": "Sessão expirada ou token CSRF inválido. Atualizando a sessão automaticamente.",
                "error_code": "csrf_invalid",
                "csrf_token": get_csrf_token(),
            }), 400
        return render_template("login.html", erro="Sessão expirada. Recarregue a página e tente novamente."), 400
    return None


@app.after_request
def add_security_headers(resp: Response) -> Response:
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; form-action 'self'; base-uri 'self'; frame-ancestors 'none'",
    )
    if request.path.startswith("/api/") or request.path in {"/", "/login"}:
        resp.headers.setdefault("Cache-Control", "no-store")
    return resp


class GitHubSyncError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class SyncResult:
    enabled: bool
    saved: bool
    message: str
    data_path: str
    repo: str = ""
    updated_at: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "saved": self.saved,
            "message": self.message,
            "data_path": self.data_path,
            "repo": self.repo,
            "updated_at": self.updated_at,
        }


def github_repo() -> str:
    return (os.environ.get("GITHUB_REPO") or "").strip()


def github_token() -> str:
    return (os.environ.get("GITHUB_TOKEN") or "").strip()


def github_branch() -> str:
    return (os.environ.get("GITHUB_BRANCH") or "").strip()


def github_data_path() -> str:
    path = (os.environ.get("GITHUB_DATA_PATH") or DEFAULT_GITHUB_DATA_PATH).strip().strip("/")
    return path or DEFAULT_GITHUB_DATA_PATH


def github_enabled() -> bool:
    return bool(github_repo() and github_token())


def github_content_url(include_ref: bool = False) -> str:
    path = urllib.parse.quote(github_data_path(), safe="/")
    url = f"https://api.github.com/repos/{github_repo()}/contents/{path}"
    if include_ref and github_branch():
        url += "?" + urllib.parse.urlencode({"ref": github_branch()})
    return url


def github_request(method: str, url: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    data = None
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ossel-dashboard",
    }
    token = github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw_msg = ""
        try:
            body = exc.read().decode("utf-8")
            raw_msg = (json.loads(body).get("message") if body else "") or ""
        except Exception:
            raw_msg = ""
        safe_message = raw_msg or "erro HTTP na API do GitHub"
        raise GitHubSyncError(f"GitHub HTTP {exc.code}: {safe_message}", exc.code) from None
    except urllib.error.URLError as exc:
        raise GitHubSyncError(f"Não foi possível conectar ao GitHub: {exc.reason}") from None
    except TimeoutError:
        raise GitHubSyncError("Tempo esgotado ao conectar ao GitHub") from None


def validate_projects_payload(projects: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cleaned: List[Dict[str, Any]] = []
    for idx, item in enumerate(projects, start=1):
        if not isinstance(item, dict):
            continue
        progress = clamp_int(item.get("progresso"), 0, 100, 0)
        categoria = clean_text(item.get("categoria"), 80) or "Outros"
        if categoria not in VALID_CATEGORIES:
            categoria = categoria or "Outros"
        nome = clean_text(item.get("nome"), 180) or "Novo item"
        projeto_pai = clean_text(item.get("projeto_pai"), 180)
        projeto = {
            "nome": nome,
            "projeto_pai": projeto_pai,
            "unidade": normalize_unidade(item.get("unidade"), nome, projeto_pai),
            "setor": clean_text(item.get("setor"), 120),
            "categoria": categoria,
            "progresso": progress,
            "status": normalize_status(item.get("status"), progress),
            "prazo": parse_date_any(item.get("prazo") or item.get("prazo_br")),
            "obs": clean_text(item.get("obs"), 2000),
            "ordem": clamp_int(item.get("ordem"), 0, 999999, idx),
            "updated_at": clean_text(item.get("updated_at"), 40) or utc_now_iso(),
            "updated_by": clean_text(item.get("updated_by"), 80),
            "assigned_to": clean_text(item.get("assigned_to"), 80),
        }
        try:
            row_id = int(item.get("id"))
            if row_id > 0:
                projeto["id"] = row_id
        except Exception:
            pass
        cleaned.append(projeto)
    return cleaned


def parse_github_backup(raw: Any) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if isinstance(raw, dict):
        projects_raw = raw.get("projects")
        if projects_raw is None:
            projects_raw = []
        if not isinstance(projects_raw, list):
            raise GitHubSyncError("Arquivo JSON remoto inválido: campo projects não é uma lista")
        return validate_projects_payload(projects_raw), raw
    if isinstance(raw, list):
        return validate_projects_payload(raw), {"schema_version": 0}
    raise GitHubSyncError("Arquivo JSON remoto inválido")


def load_projects_from_github() -> Tuple[Optional[List[Dict[str, Any]]], Dict[str, Any]]:
    if not github_enabled():
        return None, {"enabled": False, "message": "GitHub desativado"}
    try:
        data = github_request("GET", github_content_url(include_ref=True))
        content = base64.b64decode((data.get("content") or "").encode("ascii")).decode("utf-8")
        parsed = json.loads(content)
        projects, meta = parse_github_backup(parsed)
        logger.info("Backup GitHub restaurado: %s projeto(s)", len(projects))
        return projects, {"enabled": True, "message": "Backup GitHub carregado", "meta": meta, "sha": data.get("sha")}
    except GitHubSyncError as exc:
        if exc.status_code == 404:
            return None, {"enabled": True, "message": "Arquivo remoto ainda não existe", "missing": True}
        logger.error("GitHub restore error: %s", exc)
        return None, {"enabled": True, "message": str(exc), "error": True}
    except Exception as exc:
        logger.error("GitHub restore error: %s", exc)
        return None, {"enabled": True, "message": "Erro ao interpretar backup remoto", "error": True}


def serialize_projects_for_backup(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    rows = conn.execute("SELECT * FROM projects ORDER BY COALESCE(prazo,'9999-12-31'), ordem, id").fetchall()
    return validate_projects_payload([dict(r) for r in rows])


def build_backup_payload(projects: List[Dict[str, Any]], actor: str, action: str) -> Dict[str, Any]:
    now = utc_now_iso()
    return {
        "schema_version": 1,
        "app": "ossel-dashboard",
        "source": "render" if is_production() else "local",
        "data_path": github_data_path(),
        "updated_at": now,
        "updated_by": actor or "sistema",
        "action": action,
        "project_count": len(projects),
        "projects": projects,
    }


def put_backup_payload(payload: Dict[str, Any]) -> None:
    payload_json = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False)
    # Validação final antes de enviar: se não for JSON válido, isso lança exceção.
    json.loads(payload_json)
    content = base64.b64encode(payload_json.encode("utf-8")).decode("ascii")

    def get_sha() -> Optional[str]:
        try:
            current = github_request("GET", github_content_url(include_ref=True))
            return current.get("sha")
        except GitHubSyncError as exc:
            if exc.status_code == 404:
                return None
            raise

    last_error: Optional[GitHubSyncError] = None
    for attempt in range(2):
        sha = get_sha()
        body: Dict[str, Any] = {
            "message": f"Atualiza dados do painel OSSEL ({payload.get('action') or 'sync'})",
            "content": content,
        }
        if sha:
            body["sha"] = sha
        if github_branch():
            body["branch"] = github_branch()
        try:
            github_request("PUT", github_content_url(include_ref=False), body)
            return
        except GitHubSyncError as exc:
            last_error = exc
            if exc.status_code == 409 and attempt == 0:
                time.sleep(0.4)
                continue
            raise
    if last_error:
        raise last_error


def backup_projects_to_github(conn: sqlite3.Connection, actor: str = "sistema", action: str = "sync") -> SyncResult:
    data_path = github_data_path()
    repo = github_repo()
    if not github_enabled():
        return SyncResult(
            enabled=False,
            saved=False,
            message="Persistência GitHub desativada. Configure GITHUB_REPO e GITHUB_TOKEN no Render para manter os dados após deploy.",
            data_path=data_path,
            repo=repo,
        )
    try:
        projects = serialize_projects_for_backup(conn)
        payload = build_backup_payload(projects, actor, action)
        put_backup_payload(payload)
        return SyncResult(True, True, "Dados salvos no GitHub com segurança.", data_path, repo, payload["updated_at"])
    except GitHubSyncError as exc:
        logger.error("GitHub backup error: %s", exc)
        return SyncResult(True, False, str(exc), data_path, repo)
    except Exception as exc:
        logger.error("GitHub backup error: %s", exc)
        return SyncResult(True, False, "Falha inesperada ao salvar no GitHub.", data_path, repo)


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate_columns(cur: sqlite3.Cursor) -> None:
    project_cols = {r[1] for r in cur.execute("PRAGMA table_info(projects)").fetchall()}
    migrations = {
        "projeto_pai": "ALTER TABLE projects ADD COLUMN projeto_pai TEXT",
        "unidade": "ALTER TABLE projects ADD COLUMN unidade TEXT",
        "setor": "ALTER TABLE projects ADD COLUMN setor TEXT",
        "obs": "ALTER TABLE projects ADD COLUMN obs TEXT",
        "ordem": "ALTER TABLE projects ADD COLUMN ordem INTEGER",
        "updated_at": "ALTER TABLE projects ADD COLUMN updated_at TEXT",
        "updated_by": "ALTER TABLE projects ADD COLUMN updated_by TEXT",
        "assigned_to": "ALTER TABLE projects ADD COLUMN assigned_to TEXT",
    }
    for col, sql in migrations.items():
        if col not in project_cols:
            cur.execute(sql)


def insert_project_row(cur: sqlite3.Cursor, item: Dict[str, Any], ordem_fallback: int = 999) -> None:
    cleaned = validate_projects_payload([{**item, "ordem": item.get("ordem", ordem_fallback)}])[0]
    columns = [c for c in PROJECT_COLUMNS if c != "id"]
    values = [cleaned.get(c) for c in columns]
    if cleaned.get("id"):
        columns = ["id"] + columns
        values = [cleaned.get("id")] + values
    placeholders = ", ".join(["?"] * len(columns))
    cur.execute(f"INSERT INTO projects ({', '.join(columns)}) VALUES ({placeholders})", values)


def load_seed_projects() -> List[Dict[str, Any]]:
    if not SEED_PATH.exists():
        return []
    try:
        seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error("Erro ao ler seed.json: %s", exc)
        return []
    rows: List[Dict[str, Any]] = []
    if isinstance(seed, dict) and isinstance(seed.get("projects"), list):
        return validate_projects_payload(seed["projects"])
    if not isinstance(seed, list):
        return []
    ordem = 1
    for p in seed:
        if not isinstance(p, dict):
            continue
        subs = p.get("subprojetos") or []
        rows.append(
            {
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
            }
        )
        ordem += 1
        for sp in subs:
            rows.append(
                {
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
                }
            )
            ordem += 1
    return validate_projects_payload(rows)


def replace_projects(conn: sqlite3.Connection, projects: List[Dict[str, Any]]) -> None:
    cur = conn.cursor()
    cur.execute("DELETE FROM projects")
    cur.execute("DELETE FROM sqlite_sequence WHERE name='projects'")
    for idx, item in enumerate(projects, start=1):
        insert_project_row(cur, item, idx)


def init_db() -> None:
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
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    migrate_columns(cur)
    for username, display_name, role in DEFAULT_USERS:
        now = utc_now_iso()
        existing = cur.execute("SELECT * FROM users WHERE lower(username)=lower(?)", (username,)).fetchone()
        if existing:
            cur.execute(
                "UPDATE users SET display_name=?, role=?, updated_at=? WHERE id=?",
                (display_name, role, now, existing["id"]),
            )
        else:
            cur.execute(
                "INSERT INTO users (username, display_name, role, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (username, display_name, role, now, now),
            )
    count = cur.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    if count == 0:
        restored, restore_meta = load_projects_from_github()
        if restored is not None:
            replace_projects(conn, restored)
        else:
            seed = load_seed_projects()
            if seed:
                replace_projects(conn, seed)
                if github_enabled() and restore_meta.get("missing"):
                    # Cria o arquivo remoto inicial somente quando ele não existe.
                    sync = backup_projects_to_github(conn, actor="sistema", action="seed-inicial")
                    if not sync.saved:
                        logger.warning("Seed carregado localmente, mas backup inicial falhou: %s", sync.message)
    for row in cur.execute("SELECT id, nome, projeto_pai, unidade, progresso FROM projects").fetchall():
        fixed = normalize_unidade(row["unidade"], row["nome"], row["projeto_pai"])
        fixed_status = status_from_progress(row["progresso"])
        cur.execute("UPDATE projects SET unidade=?, status=? WHERE id=?", (fixed, fixed_status, row["id"]))
    conn.commit()
    conn.close()


DB_INITIALIZED = False


def ensure_db_once() -> None:
    global DB_INITIALIZED
    if not DB_INITIALIZED:
        init_db()
        DB_INITIALIZED = True


def rows_to_dict(rows: Iterable[sqlite3.Row]) -> List[Dict[str, Any]]:
    out = []
    for r in rows:
        d = dict(r)
        d["prazo_br"] = date_to_br(d.get("prazo"))
        d["can_edit"] = can_edit_project_row(d)
        out.append(d)
    return out


def get_user_by_username(username: str) -> Optional[sqlite3.Row]:
    conn = connect()
    row = conn.execute("SELECT * FROM users WHERE lower(username)=lower(?)", (username or "",)).fetchone()
    conn.close()
    return row


def require_auth() -> bool:
    return bool(session.get("auth") and session.get("user_id") and session.get("role"))


def require_admin() -> bool:
    return bool(require_auth() and session.get("role") == "admin")


def current_user() -> Optional[Dict[str, Any]]:
    if not require_auth():
        return None
    return {
        "id": session.get("user_id"),
        "username": session.get("username"),
        "display_name": session.get("display_name"),
        "role": session.get("role"),
        "is_admin": session.get("role") == "admin",
    }


def can_edit_project_row(row: Any) -> bool:
    if not require_auth() or row is None:
        return False
    getter = row.get if isinstance(row, dict) else lambda key, default=None: row[key] if key in row.keys() else default
    if session.get("role") == "admin":
        return True
    if session.get("role") == "troca" and getter("categoria") == "Troca de Máquinas":
        return True
    return False


def client_key() -> str:
    username = ""
    if request.method == "POST":
        if request.form:
            username = request.form.get("username") or ""
        elif request.is_json:
            payload = request.get_json(silent=True) or {}
            username = payload.get("username") or ""
    forwarded = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    ip = forwarded or request.remote_addr or "unknown"
    return f"{ip}:{str(username).lower()}"


def login_blocked(key: str) -> bool:
    now = time.time()
    window = 10 * 60
    attempts = [t for t in LOGIN_ATTEMPTS.get(key, []) if now - t < window]
    LOGIN_ATTEMPTS[key] = attempts
    return len(attempts) >= 8


def record_failed_login(key: str) -> None:
    LOGIN_ATTEMPTS.setdefault(key, []).append(time.time())


def clear_failed_login(key: str) -> None:
    LOGIN_ATTEMPTS.pop(key, None)


def mutation_actor() -> str:
    return str(session.get("display_name") or session.get("username") or "sistema")


def finish_mutation(conn: sqlite3.Connection, action: str) -> SyncResult:
    sync = backup_projects_to_github(conn, actor=mutation_actor(), action=action)
    if sync.enabled and not sync.saved:
        conn.rollback()
        return sync
    conn.commit()
    return sync


def json_error(message: str, status: int, sync: Optional[SyncResult] = None) -> Tuple[Response, int]:
    payload: Dict[str, Any] = {"error": message}
    if sync is not None:
        payload["remote_sync"] = sync.as_dict()
    return jsonify(payload), status


@app.route("/login", methods=["GET", "POST"])
def login():
    if require_auth() and request.method == "GET":
        return redirect(url_for("index"))
    if request.method == "POST":
        key = client_key()
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if login_blocked(key):
            return render_template("login.html", erro="Muitas tentativas. Aguarde alguns minutos e tente novamente.", username=username), 429
        login_user = get_login_user(username)
        expected_password = get_env_password(username)
        if not login_user or not expected_password or not hmac.compare_digest(str(expected_password), str(password)):
            record_failed_login(key)
            time.sleep(0.25)
            return render_template("login.html", erro="Usuário ou senha inválidos.", username=username), 401
        db_user = get_user_by_username(login_user["username"])
        if not db_user:
            conn = connect()
            now = utc_now_iso()
            conn.execute(
                "INSERT INTO users (username, display_name, role, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (login_user["username"], login_user["display_name"], login_user["role"], now, now),
            )
            conn.commit()
            conn.close()
            db_user = get_user_by_username(login_user["username"])
        session.clear()
        session.permanent = True
        session["auth"] = True
        session["user_id"] = db_user["id"] if db_user else 0
        session["username"] = login_user["username"]
        session["display_name"] = login_user["display_name"]
        session["role"] = login_user["role"]
        get_csrf_token()
        clear_failed_login(key)
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


@app.route("/healthz")
def healthz():
    return jsonify({"ok": True, "github_enabled": github_enabled(), "db": str(DB_PATH)})


@app.route("/api/me")
def api_me():
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401
    return jsonify(current_user())


@app.route("/api/csrf")
def api_csrf():
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401
    session.modified = True
    return jsonify({"csrf_token": get_csrf_token(), "user": current_user()})


@app.route("/api/sync-status")
def api_sync_status():
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401
    status: Dict[str, Any] = {
        "enabled": github_enabled(),
        "repo": github_repo(),
        "data_path": github_data_path(),
        "branch": github_branch() or None,
        "message": "GitHub configurado" if github_enabled() else "GitHub não configurado. Alterações ficam apenas no SQLite local.",
    }
    if github_enabled():
        try:
            data = github_request("GET", github_content_url(include_ref=True))
            content = base64.b64decode((data.get("content") or "").encode("ascii")).decode("utf-8")
            parsed = json.loads(content)
            meta = parsed if isinstance(parsed, dict) else {}
            status.update(
                {
                    "remote_file_exists": True,
                    "sha": data.get("sha"),
                    "updated_at": meta.get("updated_at"),
                    "project_count": meta.get("project_count") if isinstance(meta, dict) else None,
                    "message": "Persistência GitHub ativa",
                }
            )
        except GitHubSyncError as exc:
            status.update({"remote_file_exists": False, "message": str(exc), "error": True})
        except Exception:
            status.update({"remote_file_exists": False, "message": "Não foi possível ler o status remoto", "error": True})
    return jsonify(status)


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
def api_update_project(project_id: int):
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not row:
            conn.rollback()
            return jsonify({"error": "Projeto não encontrado"}), 404
        if not can_edit_project_row(row):
            conn.rollback()
            return jsonify({"error": "Sem permissão para alterar este projeto"}), 403
        allowed = ["nome", "projeto_pai", "unidade", "setor", "categoria", "progresso", "status", "prazo", "obs", "ordem", "assigned_to"] if session.get("role") == "admin" else ["progresso", "obs"]
        updates: Dict[str, Any] = {}
        for key in allowed:
            if key not in data:
                continue
            value = data.get(key)
            if key == "progresso":
                progress = clamp_int(value)
                updates["progresso"] = progress
                updates["status"] = status_from_progress(progress)
            elif key == "status":
                updates["status"] = normalize_status(value, row["progresso"])
            elif key == "prazo":
                updates["prazo"] = parse_date_any(value)
            elif key == "ordem":
                updates["ordem"] = clamp_int(value, 0, 999999, int(row["ordem"] or 999))
            elif key in {"nome", "projeto_pai"}:
                cleaned = clean_text(value, 180)
                if key == "nome" and not cleaned:
                    conn.rollback()
                    return jsonify({"error": "Nome do projeto é obrigatório"}), 400
                updates[key] = cleaned
            elif key == "obs":
                updates[key] = clean_text(value, 2000)
            elif key == "categoria":
                updates[key] = clean_text(value, 80) or "Outros"
            elif key == "assigned_to":
                updates[key] = clean_text(value, 80)
            else:
                updates[key] = clean_text(value, 160)
        if "unidade" in updates:
            updates["unidade"] = normalize_unidade(updates["unidade"], updates.get("nome", row["nome"]), updates.get("projeto_pai", row["projeto_pai"]))
        updates["updated_at"] = utc_now_iso()
        updates["updated_by"] = mutation_actor()
        cols = ", ".join([f"{k}=?" for k in updates])
        values = list(updates.values()) + [project_id]
        conn.execute(f"UPDATE projects SET {cols} WHERE id=?", values)
        updated = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        sync = finish_mutation(conn, f"atualiza-projeto-{project_id}")
        if sync.enabled and not sync.saved:
            return json_error("Não foi possível salvar no GitHub. A alteração foi cancelada para evitar perda após deploy.", 503, sync)
        response = rows_to_dict([updated])[0]
        response["remote_sync"] = sync.as_dict()
        return jsonify(response)
    except Exception as exc:
        conn.rollback()
        logger.exception("Erro ao atualizar projeto")
        return jsonify({"error": "Erro ao atualizar projeto."}), 500
    finally:
        conn.close()


@app.route("/api/projects", methods=["POST"])
def api_create_project():
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401
    if not require_admin():
        return jsonify({"error": "Apenas administradores podem criar projetos"}), 403
    data = request.get_json(silent=True) or {}
    nome = clean_text(data.get("nome"), 180) or "Novo item"
    progresso = clamp_int(data.get("progresso"))
    item = {
        "nome": nome,
        "projeto_pai": clean_text(data.get("projeto_pai"), 180),
        "unidade": normalize_unidade(data.get("unidade"), nome, data.get("projeto_pai")),
        "setor": clean_text(data.get("setor"), 120),
        "categoria": clean_text(data.get("categoria"), 80) or "Troca de Máquinas",
        "progresso": progresso,
        "status": status_from_progress(progresso),
        "prazo": parse_date_any(data.get("prazo") or data.get("prazo_iso")),
        "obs": clean_text(data.get("obs"), 2000),
        "ordem": clamp_int(data.get("ordem"), 0, 999999, 999),
        "updated_at": utc_now_iso(),
        "updated_by": mutation_actor(),
        "assigned_to": clean_text(data.get("assigned_to"), 80),
    }
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        insert_project_row(cur, item, item["ordem"])
        row = conn.execute("SELECT * FROM projects WHERE id=?", (cur.lastrowid,)).fetchone()
        sync = finish_mutation(conn, "cria-projeto")
        if sync.enabled and not sync.saved:
            return json_error("Não foi possível salvar no GitHub. O novo projeto foi cancelado para evitar perda após deploy.", 503, sync)
        response = rows_to_dict([row])[0]
        response["remote_sync"] = sync.as_dict()
        return jsonify(response), 201
    except Exception:
        conn.rollback()
        logger.exception("Erro ao criar projeto")
        return jsonify({"error": "Erro ao criar projeto."}), 500
    finally:
        conn.close()


@app.route("/api/projects/<int:project_id>", methods=["DELETE"])
def api_delete_project(project_id: int):
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401
    if not require_admin():
        return jsonify({"error": "Apenas administradores podem excluir projetos"}), 403
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not row:
            conn.rollback()
            return jsonify({"error": "Projeto não encontrado"}), 404
        conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
        sync = finish_mutation(conn, f"exclui-projeto-{project_id}")
        if sync.enabled and not sync.saved:
            return json_error("Não foi possível salvar no GitHub. A exclusão foi cancelada para evitar inconsistência.", 503, sync)
        return jsonify({"ok": True, "remote_sync": sync.as_dict()})
    except Exception:
        conn.rollback()
        logger.exception("Erro ao excluir projeto")
        return jsonify({"error": "Erro ao excluir projeto."}), 500
    finally:
        conn.close()


@app.route("/api/admin/reseed", methods=["POST"])
def api_reseed():
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401
    if not require_admin():
        return jsonify({"error": "Apenas administradores podem importar a base"}), 403
    data = request.get_json(silent=True) or {}
    if data.get("confirm") != "IMPORTAR_BASE_COMPLETA":
        return jsonify({"error": "Confirmação inválida"}), 400
    seed = load_seed_projects()
    if not seed:
        return jsonify({"error": "Arquivo data/seed.json não contém projetos para importar"}), 400
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        replace_projects(conn, seed)
        sync = finish_mutation(conn, "reimporta-base")
        if sync.enabled and not sync.saved:
            return json_error("Não foi possível salvar no GitHub. A importação foi cancelada para evitar perda após deploy.", 503, sync)
        total = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        return jsonify({"ok": True, "total": total, "remote_sync": sync.as_dict()})
    except Exception:
        conn.rollback()
        logger.exception("Erro ao importar base")
        return jsonify({"error": "Erro ao importar base."}), 500
    finally:
        conn.close()


@app.route("/export.csv")
def export_csv():
    if not require_auth():
        return redirect(url_for("login"))
    conn = connect()
    rows = rows_to_dict(conn.execute("SELECT * FROM projects ORDER BY COALESCE(prazo,'9999-12-31'), ordem, id").fetchall())
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow([
        "ID",
        "Projeto",
        "Projeto Pai",
        "Unidade",
        "Setor",
        "Categoria",
        "Responsável",
        "Progresso",
        "Status",
        "Prazo",
        "Observação",
        "Atualizado em",
        "Atualizado por",
    ])
    for r in rows:
        writer.writerow([
            r.get("id"),
            r.get("nome"),
            r.get("projeto_pai"),
            r.get("unidade"),
            r.get("setor"),
            r.get("categoria"),
            r.get("assigned_to", ""),
            r.get("progresso"),
            r.get("status"),
            r.get("prazo_br"),
            r.get("obs"),
            r.get("updated_at"),
            r.get("updated_by"),
        ])
    return Response(
        output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=ossel_projetos.csv"},
    )


@app.errorhandler(404)
def page_not_found(_error):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Recurso não encontrado"}), 404
    return redirect(url_for("index" if require_auth() else "login"))


@app.errorhandler(500)
def internal_error(_error):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Erro interno. Tente novamente."}), 500
    return render_template("login.html", erro="Erro interno. Tente novamente."), 500


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=not is_production())
