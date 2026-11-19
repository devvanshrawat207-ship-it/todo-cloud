"""Cloud-ready todo server. Standard library only (Python 3.8+).

Run locally:   python server.py        ->  http://localhost:8000
In the cloud:  the host sets PORT; the start command is `python server.py`.
Set DATABASE_PATH to a file on a persistent disk/volume so tasks survive restarts.
"""
import json
import os
import re
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = os.environ.get("DATABASE_PATH", str(BASE_DIR / "todos.db"))
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))
MAX_TEXT = 200

# Only these files are ever served, so no path can escape the project folder.
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/script.js": ("script.js", "text/javascript; charset=utf-8"),
}
TODO_PATH = re.compile(r"^/api/todos/(\d+)$")


def run_sql(sql, params=()):
    """Run one statement in its own connection; returns (rows, lastrowid)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            cur = conn.execute(sql, params)
            return cur.fetchall(), cur.lastrowid
    finally:
        conn.close()


def init_db():
    run_sql(
        """CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            done INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )


def to_dict(row):
    return {"id": row["id"], "text": row["text"], "done": bool(row["done"])}


def list_todos():
    rows, _ = run_sql("SELECT * FROM todos ORDER BY id")
    return [to_dict(r) for r in rows]


def get_todo(todo_id):
    rows, _ = run_sql("SELECT * FROM todos WHERE id = ?", (todo_id,))
    return to_dict(rows[0]) if rows else None


class Handler(BaseHTTPRequestHandler):
    server_version = "TodoServer/1.0"

    def send_json(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def error(self, status, message):
        self.send_json(status, {"error": message})

    def read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > 4096:
            raise ValueError("Request is too large.")
        data = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(data, dict):
            raise ValueError("Expected a JSON object.")
        return data

    def route(self):
        return self.path.split("?", 1)[0]

    def do_GET(self):
        path = self.route()
        if path == "/api/todos":
            return self.send_json(200, list_todos())
        if path == "/health":
            return self.send_json(200, {"status": "ok"})
        if path in STATIC_FILES:
            name, content_type = STATIC_FILES[path]
            try:
                data = (BASE_DIR / name).read_bytes()
            except FileNotFoundError:
                return self.error(404, "File not found.")
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(data)
            return
        self.error(404, "Not found.")

    def do_POST(self):
        if self.route() != "/api/todos":
            return self.error(404, "Not found.")
        try:
            text = str(self.read_json().get("text", "")).strip()
        except ValueError as exc:
            return self.error(400, str(exc))
        if not text or len(text) > MAX_TEXT:
            return self.error(400, f"A task must be 1 to {MAX_TEXT} characters.")
        _, new_id = run_sql("INSERT INTO todos (text) VALUES (?)", (text,))
        self.send_json(201, get_todo(new_id))

    def do_PATCH(self):
        match = TODO_PATH.match(self.route())
        if not match:
            return self.error(404, "Not found.")
        todo_id = int(match.group(1))
        try:
            data = self.read_json()
        except ValueError as exc:
            return self.error(400, str(exc))
        if not isinstance(data.get("done"), bool):
            return self.error(400, 'Send {"done": true} or {"done": false}.')
        run_sql("UPDATE todos SET done = ? WHERE id = ?", (int(data["done"]), todo_id))
        todo = get_todo(todo_id)
        if todo is None:
            return self.error(404, "Task not found.")
        self.send_json(200, todo)

    def do_DELETE(self):
        path = self.route()
        if path == "/api/todos/completed":
            run_sql("DELETE FROM todos WHERE done = 1")
            return self.send_json(200, {"ok": True})
        match = TODO_PATH.match(path)
        if not match:
            return self.error(404, "Not found.")
        run_sql("DELETE FROM todos WHERE id = ?", (int(match.group(1)),))
        self.send_json(200, {"ok": True})


if __name__ == "__main__":
    init_db()
    print(f"Todo server running on http://{HOST}:{PORT} (database: {DB_PATH})")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
