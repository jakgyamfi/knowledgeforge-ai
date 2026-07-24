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
            opportunity_columns = {row[1] for row in db.execute("PRAGMA table_info(opportunities)")}
            opportunity_additions = {
                "score": "INTEGER NOT NULL DEFAULT 50",
                "confidence": "TEXT NOT NULL DEFAULT 'medium'",
                "evidence": "TEXT NOT NULL DEFAULT '[]'",
                "missing_capabilities": "TEXT NOT NULL DEFAULT '[]'",
                "effort": "TEXT NOT NULL DEFAULT ''",
                "expected_value": "TEXT NOT NULL DEFAULT ''",
                "risks": "TEXT NOT NULL DEFAULT '[]'",
                "next_step": "TEXT NOT NULL DEFAULT ''",
                "validation": "TEXT NOT NULL DEFAULT '{}'",
                "validated_at": "TEXT",
                "updated_at": "TEXT NOT NULL DEFAULT ''",
            }
            for name, definition in opportunity_additions.items():
                if name not in opportunity_columns:
                    db.execute(f"ALTER TABLE opportunities ADD COLUMN {name} {definition}")
            db.execute(
                """CREATE TABLE IF NOT EXISTS project_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id),
                title TEXT NOT NULL, details TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'todo', priority TEXT NOT NULL DEFAULT 'medium',
                position INTEGER NOT NULL DEFAULT 0, estimate_minutes INTEGER NOT NULL DEFAULT 30,
                target_date TEXT NOT NULL DEFAULT '', dependencies TEXT NOT NULL DEFAULT '[]',
                source TEXT NOT NULL DEFAULT 'ai', created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"""
            )
            db.execute("CREATE INDEX IF NOT EXISTS idx_project_tasks_project ON project_tasks(project_id,position)")
            db.execute("""CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL)""")
            project_columns = {row[1] for row in db.execute("PRAGMA table_info(projects)")}
            if "workspace_type" not in project_columns:
                db.execute("ALTER TABLE projects ADD COLUMN workspace_type TEXT NOT NULL DEFAULT 'book'")
            if "status" not in project_columns:
                db.execute("ALTER TABLE projects ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")
            if "completed_at" not in project_columns:
                db.execute("ALTER TABLE projects ADD COLUMN completed_at TEXT")
            db.execute(
                """CREATE TABLE IF NOT EXISTS user_profiles (
                id INTEGER PRIMARY KEY, display_name TEXT NOT NULL DEFAULT '',
                location TEXT NOT NULL DEFAULT '', headline TEXT NOT NULL DEFAULT '',
                summary TEXT NOT NULL DEFAULT '', skills TEXT NOT NULL DEFAULT '[]',
                certifications TEXT NOT NULL DEFAULT '[]', interests TEXT NOT NULL DEFAULT '[]',
                goals TEXT NOT NULL DEFAULT '[]', industries TEXT NOT NULL DEFAULT '[]',
                avoid TEXT NOT NULL DEFAULT '[]', preferences TEXT NOT NULL DEFAULT '{}',
                cv_text TEXT NOT NULL DEFAULT '', cv_filename TEXT NOT NULL DEFAULT '',
                cv_path TEXT NOT NULL DEFAULT '',
                suggestions TEXT NOT NULL DEFAULT '{}', updated_at TEXT NOT NULL)"""
            )
            profile_columns = {row[1] for row in db.execute("PRAGMA table_info(user_profiles)")}
            if "cv_path" not in profile_columns:
                db.execute("ALTER TABLE user_profiles ADD COLUMN cv_path TEXT NOT NULL DEFAULT ''")
            db.execute(
                """INSERT OR IGNORE INTO user_profiles(id,updated_at) VALUES(1,?)""",
                (_now(),),
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS growth_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
                title TEXT NOT NULL UNIQUE, status TEXT NOT NULL DEFAULT 'active',
                progress INTEGER NOT NULL DEFAULT 0, target_date TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT 'profile',
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS growth_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                growth_item_id INTEGER REFERENCES growth_items(id),
                project_id INTEGER REFERENCES projects(id),
                title TEXT NOT NULL, details TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'todo', priority TEXT NOT NULL DEFAULT 'medium',
                position INTEGER NOT NULL DEFAULT 0, estimate_minutes INTEGER NOT NULL DEFAULT 30,
                target_date TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT 'ai',
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"""
            )
            db.execute("CREATE INDEX IF NOT EXISTS idx_growth_actions_status ON growth_actions(status,position)")
            db.execute(
                """CREATE TABLE IF NOT EXISTS workspace_cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id),
                collection TEXT NOT NULL, title TEXT NOT NULL, content TEXT NOT NULL DEFAULT '',
                metadata TEXT NOT NULL DEFAULT '{}', position INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"""
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_workspace_cards ON workspace_cards(project_id,collection,position)"
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS workspace_completions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id),
                review TEXT NOT NULL, snapshot TEXT NOT NULL, created_at TEXT NOT NULL)"""
            )
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

    @staticmethod
    def _json_list(value: str) -> list[Any]:
        try:
            parsed = json.loads(value or "[]")
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []

    def get_profile(self) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute("SELECT * FROM user_profiles WHERE id=1").fetchone()
        profile = dict(row)
        for key in ("skills", "certifications", "interests", "goals", "industries", "avoid"):
            profile[key] = self._json_list(profile[key])
        for key in ("preferences", "suggestions"):
            try:
                profile[key] = json.loads(profile[key] or "{}")
            except json.JSONDecodeError:
                profile[key] = {}
        return profile

    def update_profile(self, values: dict[str, Any]) -> dict[str, Any]:
        allowed_text = {"display_name", "location", "headline", "summary", "cv_text", "cv_filename", "cv_path"}
        allowed_lists = {"skills", "certifications", "interests", "goals", "industries", "avoid"}
        changes: dict[str, Any] = {}
        for key in allowed_text:
            if key in values:
                changes[key] = str(values[key]).strip()
        for key in allowed_lists:
            if key in values:
                # Preserve the owner's ordering. Sets previously alphabetized
                # goals and other lists, which made carefully ordered content
                # feel as though the application had rewritten it.
                cleaned = []
                seen = set()
                for item in values[key]:
                    value = str(item).strip()
                    marker = value.casefold()
                    if value and marker not in seen:
                        cleaned.append(value)
                        seen.add(marker)
                changes[key] = json.dumps(cleaned)
        if "preferences" in values:
            changes["preferences"] = json.dumps(values["preferences"])
        if "suggestions" in values:
            changes["suggestions"] = json.dumps(values["suggestions"])
        if changes:
            assignments = ",".join(f"{key}=?" for key in changes)
            with self._connect() as db:
                db.execute(
                    f"UPDATE user_profiles SET {assignments},updated_at=? WHERE id=1",
                    (*changes.values(), _now()),
                )
        return self.get_profile()

    def clear_profile_suggestions(self) -> dict[str, Any]:
        return self.update_profile({"suggestions": {}})

    @staticmethod
    def _growth_status(title: str, kind: str) -> str:
        lowered = title.casefold()
        if "complete" in lowered or "earned" in lowered:
            return "completed"
        if "in progress" in lowered or "in-progress" in lowered:
            return "in_progress"
        return "active" if kind == "goal" else "planned"

    def sync_growth_from_profile(self) -> list[dict[str, Any]]:
        """Mirror Goals into commitments without treating credentials as goals.

        Certifications describe what the owner has earned.  Anything currently
        being pursued belongs in Goals and becomes a commitment from there.
        Profile-derived commitments removed from Goals are archived so they do
        not linger in the active dashboard or destroy historical actions.
        """
        profile = self.get_profile()
        entries = [("goal", value, "profile") for value in profile["goals"]]
        active_titles = {str(value).strip().casefold() for value in profile["goals"] if str(value).strip()}
        with self._connect() as db:
            profile_rows = db.execute(
                "SELECT id,title,status FROM growth_items WHERE source IN ('profile','profile_suggestion')"
            ).fetchall()
            for row in profile_rows:
                if str(row["title"]).casefold() not in active_titles and row["status"] != "completed":
                    db.execute(
                        "UPDATE growth_items SET status='archived',updated_at=? WHERE id=?",
                        (_now(), row["id"]),
                    )
            for kind, raw_title, source in entries:
                title = str(raw_title).strip()
                if not title:
                    continue
                status = self._growth_status(title, kind)
                db.execute(
                    """INSERT INTO growth_items(kind,title,status,source,created_at,updated_at)
                    VALUES(?,?,?,?,?,?) ON CONFLICT(title) DO UPDATE SET
                    kind=excluded.kind,
                    source=CASE WHEN growth_items.source='manual' THEN growth_items.source ELSE excluded.source END,
                    status=CASE WHEN growth_items.status IN ('completed','in_progress')
                        THEN growth_items.status ELSE excluded.status END,
                    updated_at=excluded.updated_at""",
                    (kind, title, status, source, _now(), _now()),
                )
        return self.list_growth_items()

    def list_growth_items(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                """SELECT * FROM growth_items ORDER BY
                CASE status WHEN 'in_progress' THEN 0 WHEN 'active' THEN 1 WHEN 'planned' THEN 2
                WHEN 'completed' THEN 3 ELSE 4 END, kind,title"""
            ).fetchall()
        return [dict(row) for row in rows]

    def update_growth_item(self, item_id: int, values: dict[str, Any]) -> dict[str, Any] | None:
        allowed = {"status", "progress", "target_date", "notes"}
        changes = {key: value for key, value in values.items() if key in allowed and value is not None}
        if "progress" in changes:
            changes["progress"] = max(0, min(100, int(changes["progress"])))
            if changes["progress"] == 100:
                changes["status"] = "completed"
        if changes:
            assignments = ",".join(f"{key}=?" for key in changes)
            with self._connect() as db:
                result = db.execute(
                    f"UPDATE growth_items SET {assignments},updated_at=? WHERE id=?",
                    (*changes.values(), _now(), item_id),
                )
            if result.rowcount != 1:
                return None
        return next((item for item in self.list_growth_items() if item["id"] == item_id), None)

    def list_growth_actions(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                """SELECT a.*,g.title growth_title,g.kind growth_kind,g.status growth_status,p.name project_name
                FROM growth_actions a LEFT JOIN growth_items g ON g.id=a.growth_item_id
                LEFT JOIN projects p ON p.id=a.project_id
                ORDER BY CASE a.status WHEN 'doing' THEN 0 WHEN 'todo' THEN 1 WHEN 'done' THEN 2 ELSE 3 END,
                CASE a.priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                CASE WHEN a.target_date='' THEN 1 ELSE 0 END,a.target_date,a.position,a.id"""
            ).fetchall()
        return [dict(row) for row in rows]

    def update_growth_action(self, action_id: int, values: dict[str, Any]) -> dict[str, Any] | None:
        allowed = {"status", "title", "details", "priority", "estimate_minutes", "target_date"}
        changes = {key: value for key, value in values.items() if key in allowed and value is not None}
        if changes:
            assignments = ",".join(f"{key}=?" for key in changes)
            with self._connect() as db:
                result = db.execute(
                    f"UPDATE growth_actions SET {assignments},updated_at=? WHERE id=?",
                    (*changes.values(), _now(), action_id),
                )
            if result.rowcount != 1:
                return None
        self.recalculate_growth_progress()
        return next((action for action in self.list_growth_actions() if action["id"] == action_id), None)

    def recalculate_growth_progress(self) -> None:
        """Derive commitment progress from completed linked actions.

        Action completion is useful evidence, but it is not proof that a major
        goal is finished.  Automatic progress therefore tops out at 90%;
        the owner explicitly confirms completion to reach 100%.
        """
        with self._connect() as db:
            rows = db.execute(
                """SELECT g.id,g.status,
                COUNT(a.id) total,
                SUM(CASE WHEN a.status='done' THEN 1 ELSE 0 END) done
                FROM growth_items g LEFT JOIN growth_actions a
                ON a.growth_item_id=g.id AND a.status!='dismissed'
                GROUP BY g.id,g.status"""
            ).fetchall()
            for row in rows:
                if row["status"] in {"completed", "archived"}:
                    continue
                total = int(row["total"] or 0)
                done = int(row["done"] or 0)
                progress = min(90, round(done * 100 / total)) if total else 0
                db.execute(
                    "UPDATE growth_items SET progress=?,updated_at=? WHERE id=?",
                    (progress, _now(), row["id"]),
                )

    def replace_ai_growth_actions(self, actions: list[dict[str, Any]]) -> None:
        """Refresh open AI actions while retaining completed and manual work."""
        items = {item["title"].casefold(): item for item in self.list_growth_items()}
        projects = {project["name"].casefold(): project for project in self.list_projects()}
        with self._connect() as db:
            db.execute("DELETE FROM growth_actions WHERE source='ai' AND status NOT IN ('done','dismissed')")
            completed = {
                row[0].strip().casefold()
                for row in db.execute("SELECT title FROM growth_actions WHERE status='done'").fetchall()
            }
            for position, action in enumerate(actions):
                if action["title"].strip().casefold() in completed:
                    continue
                item = items.get(str(action.get("item_title", "")).casefold())
                project = projects.get(str(action.get("project_name", "")).casefold())
                db.execute(
                    """INSERT INTO growth_actions(growth_item_id,project_id,title,details,priority,position,
                    estimate_minutes,target_date,source,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?, 'ai',?,?)""",
                    (
                        item["id"] if item else None,
                        project["id"] if project else None,
                        action["title"].strip(),
                        action.get("details", "").strip(),
                        action.get("priority", "medium"),
                        position,
                        int(action.get("estimate_minutes", 30)),
                        action.get("target_date", ""),
                        _now(),
                        _now(),
                    ),
                )
        self.recalculate_growth_progress()

    def growth_overview(self) -> dict[str, Any]:
        self.sync_growth_from_profile()
        self.recalculate_growth_progress()
        items = self.list_growth_items()
        actions = self.list_growth_actions()
        with self._connect() as db:
            workspace_rows = db.execute(
                """SELECT t.*,p.name project_name,p.workspace_type FROM project_tasks t
                JOIN projects p ON p.id=t.project_id
                WHERE p.status='active' AND t.status IN ('todo','doing')
                ORDER BY CASE t.status WHEN 'doing' THEN 0 ELSE 1 END,
                CASE t.priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                CASE WHEN t.target_date='' THEN 1 ELSE 0 END,t.target_date,t.position"""
            ).fetchall()
        workspace_tasks = [dict(row) for row in workspace_rows]
        visible_actions = [
            action for action in actions
            if action.get("growth_status") not in {"completed", "archived"}
        ]
        open_actions = [action for action in visible_actions if action["status"] in {"todo", "doing"}]
        active_items = [item for item in items if item["status"] not in {"completed", "archived"}]
        completed_items = [item for item in items if item["status"] == "completed"]
        for item in active_items:
            linked = [action for action in actions if action["growth_item_id"] == item["id"]]
            item["done_actions"] = sum(action["status"] == "done" for action in linked)
            item["total_actions"] = sum(action["status"] != "dismissed" for action in linked)
            activity = max((action["updated_at"] for action in linked), default=item["updated_at"])
            try:
                age_days = (datetime.now(timezone.utc) - datetime.fromisoformat(activity)).days
            except (TypeError, ValueError):
                age_days = 0
            item["stalled"] = item["total_actions"] == 0 or age_days >= 7
            item["last_activity"] = activity
        return {
            "items": active_items,
            "completed_items": completed_items,
            "actions": visible_actions,
            "workspace_tasks": workspace_tasks,
            "metrics": {
                "active_items": len(active_items),
                "completed_items": len(completed_items),
                "open_actions": len(open_actions) + len(workspace_tasks),
                "minutes_remaining": sum(int(item["estimate_minutes"]) for item in open_actions + workspace_tasks),
            },
            "planning_note": self.get_setting("growth_planning_note", ""),
            "last_planned_at": self.get_setting("growth_last_planned_at", ""),
        }

    def list_workspace_cards(self, project_id: int, collection: str = "") -> list[dict[str, Any]]:
        sql = "SELECT * FROM workspace_cards WHERE project_id=?"
        params: list[Any] = [project_id]
        if collection:
            sql += " AND collection=?"
            params.append(collection)
        sql += " ORDER BY collection,position,id"
        with self._connect() as db:
            rows = db.execute(sql, params).fetchall()
        cards = []
        for row in rows:
            card = dict(row)
            try:
                card["metadata"] = json.loads(card["metadata"] or "{}")
            except json.JSONDecodeError:
                card["metadata"] = {}
            cards.append(card)
        return cards

    def replace_workspace_cards(self, project_id: int, cards: list[dict[str, Any]]) -> None:
        """Replace AI-generated studio cards while preserving owner-authored cards."""
        with self._connect() as db:
            db.execute(
                "DELETE FROM workspace_cards WHERE project_id=? AND json_extract(metadata,'$.source')='ai'",
                (project_id,),
            )
            offsets: dict[str, int] = {}
            for card in cards:
                collection = str(card.get("collection", "notes")).strip() or "notes"
                position = offsets.get(collection, 0)
                offsets[collection] = position + 1
                metadata = dict(card.get("metadata", {}))
                metadata["source"] = "ai"
                db.execute(
                    """INSERT INTO workspace_cards(project_id,collection,title,content,metadata,position,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?)""",
                    (
                        project_id,
                        collection,
                        str(card.get("title", "Untitled")).strip(),
                        str(card.get("content", "")).strip(),
                        json.dumps(metadata),
                        position,
                        _now(),
                        _now(),
                    ),
                )

    def add_workspace_card(
        self, project_id: int, collection: str, title: str, content: str = "", metadata: dict | None = None
    ) -> dict[str, Any]:
        metadata = {"source": "manual", **(metadata or {})}
        with self._connect() as db:
            position = int(
                db.execute(
                    "SELECT COALESCE(MAX(position),-1)+1 FROM workspace_cards WHERE project_id=? AND collection=?",
                    (project_id, collection),
                ).fetchone()[0]
            )
            cursor = db.execute(
                """INSERT INTO workspace_cards(project_id,collection,title,content,metadata,position,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?)""",
                (project_id, collection, title.strip(), content.strip(), json.dumps(metadata), position, _now(), _now()),
            )
            card_id = int(cursor.lastrowid)
        return next(card for card in self.list_workspace_cards(project_id) if card["id"] == card_id)

    def update_workspace_card(
        self, project_id: int, card_id: int, *, title: str, content: str, collection: str
    ) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT metadata FROM workspace_cards WHERE id=? AND project_id=?",
                (card_id, project_id),
            ).fetchone()
            if not row:
                return None
            try:
                metadata = json.loads(row["metadata"] or "{}")
            except json.JSONDecodeError:
                metadata = {}
            # Once the owner edits an AI card it becomes authoritative and is
            # preserved during future AI studio refreshes.
            metadata["source"] = "manual"
            db.execute(
                """UPDATE workspace_cards SET collection=?,title=?,content=?,metadata=?,updated_at=?
                WHERE id=? AND project_id=?""",
                (collection, title.strip(), content.strip(), json.dumps(metadata), _now(), card_id, project_id),
            )
        return next(card for card in self.list_workspace_cards(project_id) if card["id"] == card_id)

    def workspace_snapshot(self, project_id: int) -> dict[str, Any]:
        book = self.get_book(project_id)
        return {
            **book,
            "cards": self.list_workspace_cards(project_id),
            "tasks": self.list_tasks(project_id),
            "completion": self.latest_completion(project_id),
        }

    def latest_completion(self, project_id: int) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM workspace_completions WHERE project_id=? ORDER BY id DESC LIMIT 1",
                (project_id,),
            ).fetchone()
        if not row:
            return None
        item = dict(row)
        item["review"] = json.loads(item["review"])
        return item

    def complete_workspace(self, project_id: int, review: dict[str, Any]) -> dict[str, Any]:
        snapshot = self.workspace_snapshot(project_id)
        snapshot["completion"] = None
        with self._connect() as db:
            db.execute(
                "INSERT INTO workspace_completions(project_id,review,snapshot,created_at) VALUES(?,?,?,?)",
                (project_id, json.dumps(review), json.dumps(snapshot, default=str), _now()),
            )
            db.execute("UPDATE projects SET status='completed',completed_at=? WHERE id=?", (_now(), project_id))
            db.execute(
                "UPDATE opportunities SET status='completed',updated_at=? WHERE project_id=?",
                (_now(), project_id),
            )
        return self.workspace_snapshot(project_id)

    def reopen_workspace(self, project_id: int) -> dict[str, Any]:
        with self._connect() as db:
            db.execute("UPDATE projects SET status='active',completed_at=NULL WHERE id=?", (project_id,))
            db.execute(
                "UPDATE opportunities SET status='exploring',updated_at=? WHERE project_id=? AND status='completed'",
                (_now(), project_id),
            )
        return self.workspace_snapshot(project_id)

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

    def list_tasks(self, project_id: int) -> list[dict[str, Any]]:
        """Return the living execution plan in its current AI/user-defined order."""
        with self._connect() as db:
            rows = db.execute(
                """SELECT * FROM project_tasks WHERE project_id=?
                ORDER BY CASE status WHEN 'doing' THEN 0 WHEN 'todo' THEN 1 WHEN 'done' THEN 2 ELSE 3 END,
                position,id""",
                (project_id,),
            ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            try:
                item["dependencies"] = json.loads(item["dependencies"] or "[]")
            except json.JSONDecodeError:
                item["dependencies"] = []
            items.append(item)
        return items

    def add_task(
        self,
        project_id: int,
        *,
        title: str,
        details: str = "",
        priority: str = "medium",
        estimate_minutes: int = 30,
        target_date: str = "",
    ) -> dict[str, Any]:
        """Add an owner-authored task. AI replanning never deletes manual tasks."""
        with self._connect() as db:
            position = int(
                db.execute(
                    "SELECT COALESCE(MAX(position),-1)+1 FROM project_tasks WHERE project_id=?", (project_id,)
                ).fetchone()[0]
            )
            cursor = db.execute(
                """INSERT INTO project_tasks(project_id,title,details,priority,position,estimate_minutes,
                target_date,source,created_at,updated_at) VALUES(?,?,?,?,?,?,?,'manual',?,?)""",
                (
                    project_id,
                    title.strip(),
                    details.strip(),
                    priority,
                    position,
                    estimate_minutes,
                    target_date,
                    _now(),
                    _now(),
                ),
            )
            task_id = int(cursor.lastrowid)
        return next(item for item in self.list_tasks(project_id) if item["id"] == task_id)

    def update_task(self, project_id: int, task_id: int, values: dict[str, Any]) -> dict[str, Any] | None:
        allowed = {"title", "details", "status", "priority", "estimate_minutes", "target_date", "position"}
        changes = {key: value for key, value in values.items() if key in allowed and value is not None}
        if not changes:
            return next((item for item in self.list_tasks(project_id) if item["id"] == task_id), None)
        assignments = ",".join(f"{key}=?" for key in changes)
        with self._connect() as db:
            result = db.execute(
                f"UPDATE project_tasks SET {assignments},updated_at=? WHERE id=? AND project_id=?",
                (*changes.values(), _now(), task_id, project_id),
            )
        if result.rowcount != 1:
            return None
        return next(item for item in self.list_tasks(project_id) if item["id"] == task_id)

    def replace_ai_tasks(self, project_id: int, tasks: list[dict[str, Any]]) -> None:
        """Replace open AI suggestions while preserving completed and owner-authored work."""
        with self._connect() as db:
            db.execute("DELETE FROM project_tasks WHERE project_id=? AND source='ai' AND status!='done'", (project_id,))
            completed = {
                str(row[0]).strip().casefold()
                for row in db.execute(
                    "SELECT title FROM project_tasks WHERE project_id=? AND status='done'", (project_id,)
                ).fetchall()
            }
            for position, task in enumerate(tasks):
                if task["title"].strip().casefold() in completed:
                    continue
                db.execute(
                    """INSERT INTO project_tasks(project_id,title,details,status,priority,position,estimate_minutes,
                    target_date,dependencies,source,created_at,updated_at) VALUES(?,?,?,'todo',?,?,?,?,?,'ai',?,?)""",
                    (
                        project_id,
                        task["title"].strip(),
                        task.get("details", "").strip(),
                        task.get("priority", "medium"),
                        position,
                        int(task.get("estimate_minutes", 30)),
                        task.get("target_date", ""),
                        json.dumps(task.get("dependencies", [])),
                        _now(),
                        _now(),
                    ),
                )

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

    def update_project(self, project_id: int, *, name: str, description: str) -> dict[str, Any] | None:
        """Rename a workspace and update the owner-supplied strategic context."""
        clean_name = name.strip()
        if not clean_name:
            return None
        with self._connect() as db:
            try:
                result = db.execute(
                    "UPDATE projects SET name=?,description=? WHERE id=?",
                    (clean_name, description.strip(), project_id),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("A workspace with that name already exists.") from exc
        if result.rowcount != 1:
            return None
        return next((project for project in self.list_projects() if project["id"] == project_id), None)

    def delete_project(self, project_id: int) -> bool:
        """Delete workspace structure while preserving its source library records."""
        with self._connect() as db:
            if not db.execute("SELECT 1 FROM projects WHERE id=?", (project_id,)).fetchone():
                return False
            db.execute("UPDATE notes SET project_id=NULL,updated_at=? WHERE project_id=?", (_now(), project_id))
            db.execute("UPDATE opportunities SET project_id=NULL,updated_at=? WHERE project_id=?", (_now(), project_id))
            db.execute("UPDATE growth_actions SET project_id=NULL,updated_at=? WHERE project_id=?", (_now(), project_id))
            for table in (
                "workspace_completions",
                "workspace_cards",
                "project_tasks",
                "book_revisions",
                "book_sections",
                "book_instructions",
            ):
                db.execute(f"DELETE FROM {table} WHERE project_id=?", (project_id,))
            db.execute("DELETE FROM projects WHERE id=?", (project_id,))
        return True

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

    def clear_note_audio(self, note_id: int) -> bool:
        """Detach deleted source audio while preserving its transcript and analysis."""
        with self._connect() as db:
            result = db.execute(
                "UPDATE notes SET audio_path='',updated_at=? WHERE id=?",
                (_now(), note_id),
            )
        return result.rowcount == 1

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
                    """INSERT INTO opportunities(source_note_id,project_id,kind,title,description,rationale,
                    score,confidence,evidence,missing_capabilities,effort,expected_value,risks,next_step,
                    created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        note_id,
                        project_id,
                        item["kind"],
                        item["title"],
                        item["description"],
                        item["rationale"],
                        int(item.get("score", 50)),
                        item.get("confidence", "medium"),
                        json.dumps(item.get("evidence", [note_id])),
                        json.dumps(item.get("missing_capabilities", [])),
                        item.get("effort", ""),
                        item.get("expected_value", ""),
                        json.dumps(item.get("risks", [])),
                        item.get("next_step", ""),
                        _now(),
                        _now(),
                    ),
                )

    def list_opportunities(self, status: str = "new", limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                """SELECT o.*,n.title source_title,p.name project_name FROM opportunities o
                JOIN notes n ON n.id=o.source_note_id LEFT JOIN projects p ON p.id=o.project_id
                WHERE o.status=? ORDER BY o.id DESC LIMIT ?""",
                (status, limit),
            ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            for field in ("evidence", "missing_capabilities", "risks"):
                item[field] = self._json_list(item.get(field, "[]"))
            try:
                item["validation"] = json.loads(item.get("validation") or "{}")
            except json.JSONDecodeError:
                item["validation"] = {}
            items.append(item)
        return items

    def replace_profile_opportunities(self, opportunities: list[dict[str, Any]]) -> None:
        """Refresh unaccepted suggestions while preserving saved, validated, and explored ideas."""
        with self._connect() as db:
            valid_ids = {int(row[0]) for row in db.execute("SELECT id FROM notes").fetchall()}
            if not valid_ids:
                return
            fallback = max(valid_ids)
            db.execute("DELETE FROM opportunities WHERE status='new'")
            for item in opportunities:
                evidence = [int(note_id) for note_id in item.get("evidence", []) if int(note_id) in valid_ids]
                source_note_id = evidence[0] if evidence else fallback
                db.execute(
                    """INSERT INTO opportunities(source_note_id,kind,title,description,rationale,score,confidence,
                    evidence,missing_capabilities,effort,expected_value,risks,next_step,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        source_note_id,
                        item["kind"],
                        item["title"],
                        item["description"],
                        item["rationale"],
                        int(item.get("score", 50)),
                        item.get("confidence", "medium"),
                        json.dumps(evidence),
                        json.dumps(item.get("missing_capabilities", [])),
                        item.get("effort", ""),
                        item.get("expected_value", ""),
                        json.dumps(item.get("risks", [])),
                        item.get("next_step", ""),
                        _now(),
                        _now(),
                    ),
                )

    def get_opportunity(self, opportunity_id: int) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM opportunities WHERE id=?", (opportunity_id,)).fetchone()
        if not row:
            return None
        item = dict(row)
        for field in ("evidence", "missing_capabilities", "risks"):
            item[field] = self._json_list(item.get(field, "[]"))
        item["validation"] = json.loads(item.get("validation") or "{}")
        return item

    def update_opportunity(self, opportunity_id: int, *, status: str | None = None, validation: dict | None = None):
        changes: dict[str, Any] = {}
        if status is not None:
            changes["status"] = status
        if validation is not None:
            changes["validation"] = json.dumps(validation)
            changes["validated_at"] = _now()
        if not changes:
            return self.get_opportunity(opportunity_id)
        changes["updated_at"] = _now()
        assignments = ",".join(f"{key}=?" for key in changes)
        with self._connect() as db:
            result = db.execute(
                f"UPDATE opportunities SET {assignments} WHERE id=?",
                (*changes.values(), opportunity_id),
            )
        return self.get_opportunity(opportunity_id) if result.rowcount else None

    def explore_opportunity(self, opportunity_id: int) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM opportunities WHERE id=?", (opportunity_id,)).fetchone()
            if not row:
                return None
        workspace_type = {
            "book": "book",
            "business": "business",
            "nonprofit": "impact",
            "impact": "impact",
        }.get(row["kind"], "project")
        project_id = self.ensure_project(row["title"], row["description"], workspace_type)
        with self._connect() as db:
            db.execute(
                "UPDATE opportunities SET status='exploring',project_id=?,updated_at=? WHERE id=?",
                (project_id, _now(), opportunity_id),
            )
        return {"project_id": project_id, "status": "exploring", "workspace_type": workspace_type}

    def mark_analysis_failed(self, note_id: int, error: str) -> None:
        with self._connect() as db:
            db.execute(
                "UPDATE notes SET analysis_status='failed',analysis_error=?,updated_at=? WHERE id=?",
                (error[:1000], _now(), note_id),
            )

    def pending_analysis_ids(self, limit: int = 100) -> list[int]:
        """Return unfinished notes oldest-first so the queue is predictable.

        Both ``pending`` and ``failed`` notes are included. A failed note is not
        retried continuously; callers invoke this queue only at deliberate
        recovery points such as startup, saving a key, changing providers, or
        pressing "Process pending now".
        """
        with self._connect() as db:
            rows = db.execute(
                """SELECT id FROM notes
                WHERE analysis_status!='complete'
                ORDER BY created_at ASC, id ASC LIMIT ?""",
                (max(1, min(limit, 500)),),
            ).fetchall()
        return [int(row["id"]) for row in rows]

    def context_notes(self, project_id: int | None = None, query: str = "", limit: int = 30):
        return self.list_notes(query=query, project_id=project_id, limit=limit)

    def stats(self) -> dict[str, int]:
        with self._connect() as db:
            total = db.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
            pending = db.execute("SELECT COUNT(*) FROM notes WHERE analysis_status!='complete'").fetchone()[0]
        return {"notes": int(total), "pending_analysis": int(pending)}
