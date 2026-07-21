"""SQLite repository for private audio notes, projects, and AI analysis."""

from __future__ import annotations
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Library:
    """Own schema migrations and keep SQL out of worker and web layers."""

    def __init__(self, database: Path) -> None:
        self.database = database
        database.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.database, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def _initialize(self) -> None:
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                """CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL)"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS book_sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL REFERENCES projects(id),
                position INTEGER NOT NULL, title TEXT NOT NULL, content TEXT NOT NULL,
                source_note_ids TEXT NOT NULL DEFAULT '[]', updated_at TEXT NOT NULL)"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS book_instructions (
                project_id INTEGER PRIMARY KEY REFERENCES projects(id), instructions TEXT NOT NULL,
                updated_at TEXT NOT NULL)"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS book_revisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL REFERENCES projects(id),
                trigger_note_id INTEGER, reason TEXT NOT NULL, snapshot TEXT NOT NULL, created_at TEXT NOT NULL)"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS opportunities (
                id INTEGER PRIMARY KEY AUTOINCREMENT, source_note_id INTEGER NOT NULL REFERENCES notes(id),
                project_id INTEGER REFERENCES projects(id), kind TEXT NOT NULL, title TEXT NOT NULL,
                description TEXT NOT NULL, rationale TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'new',
                created_at TEXT NOT NULL)"""
            )
            db.execute("""CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL)""")
            project_columns = {row[1] for row in db.execute("PRAGMA table_info(projects)")}
            if "workspace_type" not in project_columns:
                db.execute("ALTER TABLE projects ADD COLUMN workspace_type TEXT NOT NULL DEFAULT 'book'")
            db.execute("""CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT, source_name TEXT NOT NULL UNIQUE,
                audio_path TEXT NOT NULL, transcript_path TEXT NOT NULL, title TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'author', tags TEXT NOT NULL DEFAULT '[]',
                transcript TEXT NOT NULL, summary TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'ready',
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
            columns = {row[1] for row in db.execute("PRAGMA table_info(notes)")}
            additions = {
                "project_id": "INTEGER REFERENCES projects(id)",
                "analysis": "TEXT NOT NULL DEFAULT '{}'",
                "analysis_status": "TEXT NOT NULL DEFAULT 'pending'",
                "analysis_error": "TEXT NOT NULL DEFAULT ''",
            }
            for name, definition in additions.items():
                if name not in columns:
                    db.execute(f"ALTER TABLE notes ADD COLUMN {name} {definition}")
            db.execute("CREATE INDEX IF NOT EXISTS idx_notes_project ON notes(project_id)")

    def ensure_setting(self, key: str, value: str) -> str:
        """Create a default without replacing a choice previously made in the UI."""
        with self._connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO app_settings(key,value,updated_at) VALUES(?,?,?)",
                (key, value, _now()),
            )
            return str(db.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()[0])

    def get_setting(self, key: str, default: str = "") -> str:
        with self._connect() as db:
            row = db.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
        return str(row[0]) if row else default

    def set_settings(self, values: dict[str, str]) -> None:
        """Persist non-secret runtime choices such as provider and model."""
        with self._connect() as db:
            for key, value in values.items():
                db.execute(
                    """INSERT INTO app_settings(key,value,updated_at) VALUES(?,?,?)
                    ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at""",
                    (key, value, _now()),
                )

    def get_book(self, project_id: int) -> dict[str, Any]:
        with self._connect() as db:
            project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
            if not project:
                raise KeyError(project_id)
            sections = db.execute(
                "SELECT * FROM book_sections WHERE project_id=? ORDER BY position,id", (project_id,)
            ).fetchall()
            instruction = db.execute(
                "SELECT instructions FROM book_instructions WHERE project_id=?", (project_id,)
            ).fetchone()
        items = []
        for row in sections:
            item = dict(row)
            item["source_note_ids"] = json.loads(item["source_note_ids"] or "[]")
            items.append(item)
        return {"project": dict(project), "sections": items, "instructions": instruction[0] if instruction else ""}

    def save_book_instructions(self, project_id: int, instructions: str) -> None:
        with self._connect() as db:
            db.execute(
                """INSERT INTO book_instructions(project_id,instructions,updated_at) VALUES(?,?,?)
                ON CONFLICT(project_id) DO UPDATE SET instructions=excluded.instructions,updated_at=excluded.updated_at""",
                (project_id, instructions.strip(), _now()),
            )

    def replace_book(
        self, project_id: int, sections: list[dict[str, Any]], *, reason: str, trigger_note_id: int | None = None
    ) -> None:
        """Version the old manuscript before atomically replacing its working draft."""
        with self._connect() as db:
            old = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM book_sections WHERE project_id=? ORDER BY position,id", (project_id,)
                ).fetchall()
            ]
            db.execute(
                "INSERT INTO book_revisions(project_id,trigger_note_id,reason,snapshot,created_at) VALUES(?,?,?,?,?)",
                (project_id, trigger_note_id, reason[:500], json.dumps(old), _now()),
            )
            db.execute("DELETE FROM book_sections WHERE project_id=?", (project_id,))
            for position, section in enumerate(sections):
                db.execute(
                    """INSERT INTO book_sections(project_id,position,title,content,source_note_ids,updated_at)
                    VALUES(?,?,?,?,?,?)""",
                    (
                        project_id,
                        position,
                        section["title"],
                        section["content"],
                        json.dumps(section.get("source_note_ids", [])),
                        _now(),
                    ),
                )

    def list_revisions(self, project_id: int, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                """SELECT id,project_id,trigger_note_id,reason,created_at FROM book_revisions
                WHERE project_id=? ORDER BY id DESC LIMIT ?""",
                (project_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        item = dict(row)
        for field, fallback in (("tags", []), ("analysis", {})):
            try:
                item[field] = json.loads(item.get(field) or json.dumps(fallback))
            except json.JSONDecodeError:
                item[field] = fallback
        return item

    def ensure_project(self, name: str, description: str = "", workspace_type: str = "book") -> int:
        clean = name.strip() or "Unfiled"
        with self._connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO projects(name,description,created_at,workspace_type) VALUES(?,?,?,?)",
                (clean, description.strip(), _now(), workspace_type),
            )
            return int(db.execute("SELECT id FROM projects WHERE name=?", (clean,)).fetchone()[0])

    def list_projects(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("""SELECT p.*,COUNT(n.id) note_count FROM projects p LEFT JOIN notes n
                               ON n.project_id=p.id GROUP BY p.id ORDER BY p.name""").fetchall()
        return [dict(row) for row in rows]

    def upsert_transcript(
        self,
        *,
        source_name: str,
        audio_path: Path,
        transcript_path: Path,
        transcript: str,
        project_id: int | None = None,
    ) -> int:
        now = _now()
        with self._connect() as db:
            db.execute(
                """INSERT INTO notes(source_name,audio_path,transcript_path,title,transcript,
                       project_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)
                       ON CONFLICT(source_name) DO UPDATE SET audio_path=excluded.audio_path,
                       transcript_path=excluded.transcript_path,transcript=excluded.transcript,updated_at=excluded.updated_at""",
                (
                    source_name,
                    str(audio_path),
                    str(transcript_path),
                    Path(source_name).stem,
                    transcript,
                    project_id,
                    now,
                    now,
                ),
            )
            return int(db.execute("SELECT id FROM notes WHERE source_name=?", (source_name,)).fetchone()[0])

    def list_notes(
        self, query: str = "", category: str = "", project_id: int | None = None, limit: int = 200
    ) -> list[dict[str, Any]]:
        clauses, values = [], []
        if query:
            clauses.append(
                "(n.title LIKE ? OR n.transcript LIKE ? OR n.summary LIKE ? OR n.tags LIKE ? OR n.analysis LIKE ?)"
            )
            values.extend([f"%{query}%"] * 5)
        if category:
            clauses.append("n.category=?")
            values.append(category)
        if project_id:
            clauses.append("n.project_id=?")
            values.append(project_id)
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        with self._connect() as db:
            rows = db.execute(
                f"""SELECT n.*,p.name project_name FROM notes n LEFT JOIN projects p
                               ON p.id=n.project_id {where} ORDER BY n.created_at DESC LIMIT ?""",
                (*values, limit),
            ).fetchall()
        return [self._row(row) for row in rows]

    def get_note(self, note_id: int) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute(
                """SELECT n.*,p.name project_name FROM notes n LEFT JOIN projects p
                              ON p.id=n.project_id WHERE n.id=?""",
                (note_id,),
            ).fetchone()
        return self._row(row)

    def has_source(self, source_name: str) -> bool:
        with self._connect() as db:
            return db.execute("SELECT 1 FROM notes WHERE source_name=?", (source_name,)).fetchone() is not None

    def update_note(
        self, note_id: int, *, title: str, category: str, tags: list[str], summary: str, project_id: int | None = None
    ) -> bool:
        with self._connect() as db:
            result = db.execute(
                """UPDATE notes SET title=?,category=?,tags=?,summary=?,project_id=?,updated_at=?
                                 WHERE id=?""",
                (
                    title.strip(),
                    category.strip() or "author",
                    json.dumps(tags),
                    summary.strip(),
                    project_id,
                    _now(),
                    note_id,
                ),
            )
            return result.rowcount == 1

    def save_analysis(self, note_id: int, analysis: dict[str, Any], project_id: int | None) -> None:
        with self._connect() as db:
            db.execute(
                """UPDATE notes SET title=?,summary=?,category=?,tags=?,analysis=?,analysis_status='complete',
                       analysis_error='',project_id=?,updated_at=? WHERE id=?""",
                (
                    analysis["title"],
                    analysis["summary"],
                    analysis["content_type"],
                    json.dumps(analysis["tags"]),
                    json.dumps(analysis),
                    project_id,
                    _now(),
                    note_id,
                ),
            )
            db.execute("DELETE FROM opportunities WHERE source_note_id=? AND status='new'", (note_id,))
            for item in analysis.get("opportunities", []):
                db.execute(
                    """INSERT INTO opportunities(source_note_id,project_id,kind,title,description,rationale,created_at)
                    VALUES(?,?,?,?,?,?,?)""",
                    (note_id, project_id, item["kind"], item["title"], item["description"], item["rationale"], _now()),
                )

    def list_opportunities(self, status: str = "new", limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                """SELECT o.*,n.title source_title,p.name project_name FROM opportunities o
                JOIN notes n ON n.id=o.source_note_id LEFT JOIN projects p ON p.id=o.project_id
                WHERE o.status=? ORDER BY o.id DESC LIMIT ?""",
                (status, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def explore_opportunity(self, opportunity_id: int) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM opportunities WHERE id=?", (opportunity_id,)).fetchone()
            if not row:
                return None
        project_id = self.ensure_project(row["title"], row["description"], row["kind"])
        with self._connect() as db:
            db.execute(
                "UPDATE opportunities SET status='exploring',project_id=? WHERE id=?", (project_id, opportunity_id)
            )
        return {"project_id": project_id, "status": "exploring"}

    def mark_analysis_failed(self, note_id: int, error: str) -> None:
        with self._connect() as db:
            db.execute(
                "UPDATE notes SET analysis_status='failed',analysis_error=?,updated_at=? WHERE id=?",
                (error[:1000], _now(), note_id),
            )

    def context_notes(self, project_id: int | None = None, query: str = "", limit: int = 30):
        return self.list_notes(query=query, project_id=project_id, limit=limit)

    def stats(self) -> dict[str, int]:
        with self._connect() as db:
            total = db.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
            pending = db.execute("SELECT COUNT(*) FROM notes WHERE analysis_status!='complete'").fetchone()[0]
        return {"notes": int(total), "pending_analysis": int(pending)}
