import base64
import hashlib
import html
import json
import mimetypes
import secrets
import sqlite3
import threading
from datetime import UTC, datetime, timedelta
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from storage import CloudStorage


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "app.db"
SESSION_COOKIE = "drive_session"
MAX_UPLOAD_SIZE = 10 * 1024 * 1024
SHARE_EXPIRY_HOURS = 24

storage = CloudStorage(DATA_DIR / "cloud_storage")
session_lock = threading.Lock()
sessions: dict[str, int] = {}


def now_utc() -> datetime:
    return datetime.now(UTC)


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def dict_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def init_db() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            original_name TEXT NOT NULL,
            stored_name TEXT NOT NULL,
            content_type TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            uploaded_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS share_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(file_id) REFERENCES files(id)
        )
        """
    )
    conn.commit()
    conn.close()


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = dict_factory
    return conn


class DriveHandler(BaseHTTPRequestHandler):
    server_version = "MiniDrive/1.0"

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            return self.serve_static("index.html", "text/html; charset=utf-8")
        if path.startswith("/static/"):
            return self.serve_static(path.removeprefix("/static/"))
        if path == "/api/me":
            return self.handle_me()
        if path == "/api/files":
            return self.handle_list_files()
        if path.startswith("/api/download/"):
            return self.handle_download(path.split("/")[-1], require_auth=True)
        if path.startswith("/shared/"):
            return self.handle_shared_download(path.split("/")[-1])

        self.send_error(404, "Not found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/login":
            return self.handle_login()
        if path == "/api/signup":
            return self.handle_signup()
        if path == "/api/logout":
            return self.handle_logout()
        if path == "/api/upload":
            return self.handle_upload()
        if path.startswith("/api/share/"):
            return self.handle_create_share(path.split("/")[-1])

        self.send_error(404, "Not found")

    def log_message(self, fmt, *args):
        return

    def serve_static(self, relative_path: str, content_type: str | None = None):
        file_path = (STATIC_DIR / relative_path).resolve()
        if not file_path.is_file() or STATIC_DIR.resolve() not in file_path.parents and file_path != STATIC_DIR.resolve():
            self.send_error(404, "Static file not found")
            return

        guessed_type = content_type or mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", guessed_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            raise ValueError("Request body is required")
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON payload") from exc

    def parse_session_user(self) -> int | None:
        header = self.headers.get("Cookie")
        if not header:
            return None
        jar = cookies.SimpleCookie()
        jar.load(header)
        morsel = jar.get(SESSION_COOKIE)
        if morsel is None:
            return None
        token = morsel.value
        with session_lock:
            return sessions.get(token)

    def require_user_id(self) -> int | None:
        user_id = self.parse_session_user()
        if user_id is None:
            self.send_json({"error": "Authentication required"}, 401)
        return user_id

    def send_json(self, payload: dict | list, status: int = 200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_login(self):
        try:
            payload = self.read_json()
        except ValueError as exc:
            return self.send_json({"error": str(exc)}, 400)

        username = str(payload.get("username", "")).strip()
        password = str(payload.get("password", ""))

        conn = get_db()
        user = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        conn.close()

        if not user or user["password_hash"] != hash_password(password):
            return self.send_json({"error": "Invalid credentials"}, 401)

        token = secrets.token_urlsafe(32)
        with session_lock:
            sessions[token] = user["id"]

        body = json.dumps({"ok": True, "username": user["username"]}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header(
            "Set-Cookie",
            f"{SESSION_COOKIE}={token}; HttpOnly; Path=/; SameSite=Lax",
        )
        self.end_headers()
        self.wfile.write(body)

    def handle_signup(self):
        try:
            payload = self.read_json()
        except ValueError as exc:
            return self.send_json({"error": str(exc)}, 400)

        username = str(payload.get("username", "")).strip()
        password = str(payload.get("password", ""))
        confirm_password = str(payload.get("confirm_password", ""))

        if len(username) < 3:
            return self.send_json({"error": "Username must be at least 3 characters long"}, 400)
        if len(password) < 6:
            return self.send_json({"error": "Password must be at least 6 characters long"}, 400)
        if password != confirm_password:
            return self.send_json({"error": "Passwords do not match"}, 400)

        conn = get_db()
        existing_user = conn.execute(
            "SELECT id FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if existing_user:
            conn.close()
            return self.send_json({"error": "Username is already in use"}, 409)

        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, hash_password(password)),
        )
        user_id = cur.lastrowid
        conn.commit()
        conn.close()

        token = secrets.token_urlsafe(32)
        with session_lock:
            sessions[token] = user_id

        body = json.dumps({"ok": True, "username": username}).encode("utf-8")
        self.send_response(201)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header(
            "Set-Cookie",
            f"{SESSION_COOKIE}={token}; HttpOnly; Path=/; SameSite=Lax",
        )
        self.end_headers()
        self.wfile.write(body)

    def handle_logout(self):
        header = self.headers.get("Cookie")
        if header:
            jar = cookies.SimpleCookie()
            jar.load(header)
            morsel = jar.get(SESSION_COOKIE)
            if morsel is not None:
                with session_lock:
                    sessions.pop(morsel.value, None)

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header(
            "Set-Cookie",
            f"{SESSION_COOKIE}=deleted; Path=/; Max-Age=0; SameSite=Lax",
        )
        body = b'{"ok": true}'
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_me(self):
        user_id = self.parse_session_user()
        if user_id is None:
            return self.send_json({"authenticated": False})

        conn = get_db()
        user = conn.execute(
            "SELECT username FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        conn.close()
        if not user:
            return self.send_json({"authenticated": False})
        return self.send_json({"authenticated": True, "username": user["username"]})

    def handle_upload(self):
        user_id = self.require_user_id()
        if user_id is None:
            return

        try:
            payload = self.read_json()
            original_name = Path(str(payload.get("filename", "upload.bin"))).name
            content_b64 = str(payload.get("content_base64", ""))
            content_type = str(payload.get("content_type", "application/octet-stream"))
            file_bytes = base64.b64decode(content_b64)
        except (ValueError, TypeError):
            return self.send_json({"error": "Invalid upload payload"}, 400)

        if not original_name:
            return self.send_json({"error": "Filename is required"}, 400)
        if not file_bytes:
            return self.send_json({"error": "File content is required"}, 400)
        if len(file_bytes) > MAX_UPLOAD_SIZE:
            return self.send_json({"error": "File exceeds the 10 MB upload limit"}, 400)

        stored_name = storage.save_bytes(original_name, file_bytes)
        uploaded_at = now_utc().isoformat()

        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO files (user_id, original_name, stored_name, content_type, size_bytes, uploaded_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, original_name, stored_name, content_type, len(file_bytes), uploaded_at),
        )
        file_id = cur.lastrowid
        conn.commit()
        conn.close()

        return self.send_json(
            {
                "ok": True,
                "file": {
                    "id": file_id,
                    "name": original_name,
                    "size_bytes": len(file_bytes),
                    "uploaded_at": uploaded_at,
                },
            },
            201,
        )

    def handle_list_files(self):
        user_id = self.require_user_id()
        if user_id is None:
            return

        conn = get_db()
        rows = conn.execute(
            """
            SELECT f.id, f.original_name, f.content_type, f.size_bytes, f.uploaded_at,
                   (
                       SELECT token
                       FROM share_links s
                       WHERE s.file_id = f.id AND s.expires_at > ?
                       ORDER BY s.created_at DESC
                       LIMIT 1
                   ) AS share_token,
                   (
                       SELECT expires_at
                       FROM share_links s
                       WHERE s.file_id = f.id AND s.expires_at > ?
                       ORDER BY s.created_at DESC
                       LIMIT 1
                   ) AS share_expires_at
            FROM files f
            WHERE f.user_id = ?
            ORDER BY f.uploaded_at DESC
            """,
            (now_utc().isoformat(), now_utc().isoformat(), user_id),
        ).fetchall()
        conn.close()

        files = []
        for row in rows:
            files.append(
                {
                    "id": row["id"],
                    "name": row["original_name"],
                    "content_type": row["content_type"],
                    "size_bytes": row["size_bytes"],
                    "uploaded_at": row["uploaded_at"],
                    "download_url": f"/api/download/{row['id']}",
                    "share_url": f"/shared/{row['share_token']}" if row["share_token"] else None,
                    "share_expires_at": row["share_expires_at"],
                }
            )

        return self.send_json(files)

    def handle_download(self, file_id: str, require_auth: bool):
        try:
            file_id_int = int(file_id)
        except ValueError:
            return self.send_json({"error": "Invalid file id"}, 400)

        user_id = None
        if require_auth:
            user_id = self.require_user_id()
            if user_id is None:
                return

        conn = get_db()
        if require_auth:
            file_row = conn.execute(
                """
                SELECT id, original_name, stored_name, content_type
                FROM files
                WHERE id = ? AND user_id = ?
                """,
                (file_id_int, user_id),
            ).fetchone()
        else:
            file_row = conn.execute(
                """
                SELECT id, original_name, stored_name, content_type
                FROM files
                WHERE id = ?
                """,
                (file_id_int,),
            ).fetchone()
        conn.close()

        if not file_row:
            return self.send_json({"error": "File not found"}, 404)

        try:
            file_bytes = storage.read_bytes(file_row["stored_name"])
        except FileNotFoundError:
            return self.send_json({"error": "Stored object is missing"}, 404)

        filename = html.escape(file_row["original_name"], quote=True)
        self.send_response(200)
        self.send_header("Content-Type", file_row["content_type"])
        self.send_header("Content-Length", str(len(file_bytes)))
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(file_bytes)

    def handle_create_share(self, file_id: str):
        user_id = self.require_user_id()
        if user_id is None:
            return

        try:
            file_id_int = int(file_id)
        except ValueError:
            return self.send_json({"error": "Invalid file id"}, 400)

        conn = get_db()
        file_row = conn.execute(
            "SELECT id FROM files WHERE id = ? AND user_id = ?",
            (file_id_int, user_id),
        ).fetchone()
        if not file_row:
            conn.close()
            return self.send_json({"error": "File not found"}, 404)

        token = secrets.token_urlsafe(24)
        created_at = now_utc()
        expires_at = created_at + timedelta(hours=SHARE_EXPIRY_HOURS)
        conn.execute(
            """
            INSERT INTO share_links (file_id, token, expires_at, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (file_id_int, token, expires_at.isoformat(), created_at.isoformat()),
        )
        conn.commit()
        conn.close()

        return self.send_json(
            {
                "ok": True,
                "share_url": f"/shared/{token}",
                "expires_at": expires_at.isoformat(),
            }
        )

    def handle_shared_download(self, token: str):
        conn = get_db()
        row = conn.execute(
            """
            SELECT f.id
            FROM share_links s
            JOIN files f ON f.id = s.file_id
            WHERE s.token = ? AND s.expires_at > ?
            """,
            (token, now_utc().isoformat()),
        ).fetchone()
        conn.close()
        if not row:
            return self.send_json({"error": "Share link is invalid or expired"}, 404)
        return self.handle_download(str(row["id"]), require_auth=False)


def main():
    init_db()
    host = "127.0.0.1"
    port = 8000
    server = ThreadingHTTPServer((host, port), DriveHandler)
    print(f"CloudBox Drive running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
