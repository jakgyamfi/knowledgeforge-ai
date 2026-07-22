"""FastAPI application: capture, transcription, organization, projects, and chat."""

from __future__ import annotations
import logging
import mimetypes
import re
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated
from uuid import uuid4
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .ai import AIService
from .config import Settings
from .library import Library
from .organizer import organize_transcript
from .pipeline import AUDIO_EXTENSIONS, TranscriptionPipeline


class NoteUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    category: str = Field(default="author", max_length=50)
    tags: list[str] = Field(default_factory=list, max_length=30)
    summary: str = Field(default="", max_length=100_000)
    project_id: int | None = None


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    workspace_type: str = Field(default="book", pattern="^(book|business|project|general)$")


class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=5000)
    project_id: int | None = None
    selected_note_ids: list[int] = Field(default_factory=list, max_length=100)


class AISelection(BaseModel):
    provider: str = Field(min_length=1, max_length=80, pattern="^[a-z0-9_-]+$")
    model: str = Field(min_length=1, max_length=120)


class BookInstructions(BaseModel):
    instructions: str = Field(default="", max_length=50_000)


class ReorganizeRequest(BaseModel):
    feedback: str = Field(default="", max_length=50_000)


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    details: str = Field(default="", max_length=5000)
    priority: str = Field(default="medium", pattern="^(critical|high|medium|low)$")
    estimate_minutes: int = Field(default=30, ge=5, le=10080)
    target_date: str = Field(default="", max_length=10)


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    details: str | None = Field(default=None, max_length=5000)
    status: str | None = Field(default=None, pattern="^(todo|doing|done|dismissed)$")
    priority: str | None = Field(default=None, pattern="^(critical|high|medium|low)$")
    estimate_minutes: int | None = Field(default=None, ge=5, le=10080)
    target_date: str | None = Field(default=None, max_length=10)
    position: int | None = Field(default=None, ge=0)


def _safe_filename(filename: str) -> str:
    name = Path(filename or "recording.webm").name
    return re.sub(r"[^A-Za-z0-9._ -]+", "-", name).strip(" .-") or "recording.webm"


def create_app() -> FastAPI:
    settings = Settings.load()
    library = Library(settings.database)
    library.ensure_setting("ai_provider", settings.ai_provider)
    library.ensure_setting("ai_model", settings.ai_model)
    library.ensure_setting("auto_integrate", "true")
    library.ensure_project(settings.default_project, "Default workspace for captured book ideas.", "book")
    library.ensure_project("Business Ideas", "Captured business concepts and working plans.", "business")
    library.ensure_project("Project Ideas", "Captured project concepts and implementation plans.", "project")
    pipeline = TranscriptionPipeline(settings, library)
    ai = AIService(settings, library)
    stop_event = threading.Event()
    worker = threading.Thread(target=pipeline.watch, args=(stop_event,), name="knowledgeforge-watcher", daemon=True)

    def process_import(path: Path) -> None:
        """Extract imported documents/images, then run the same organization workflow as audio."""
        suffix = path.suffix.lower()
        if suffix in {".txt", ".md"}:
            content = path.read_text(encoding="utf-8", errors="replace")
        elif suffix == ".pdf":
            from pypdf import PdfReader

            content = "\n\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
        elif suffix == ".docx":
            from docx import Document

            content = "\n".join(paragraph.text for paragraph in Document(path).paragraphs)
        elif suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
            content = ai.describe_image(path)
        else:
            raise ValueError(f"Unsupported import type: {suffix}")
        transcript_path = settings.transcripts / "imports" / f"{path.stem}.txt"
        transcript_path.parent.mkdir(parents=True, exist_ok=True)
        transcript_path.write_text(content.strip() + "\n", encoding="utf-8")
        note_id = library.upsert_transcript(
            source_name=f"imports/{path.name}",
            audio_path=path,
            transcript_path=transcript_path,
            transcript=content.strip(),
        )
        if ai.enabled:
            organized = ai.analyze(note_id)
            if organized.get("project_id") and library.get_setting("auto_integrate", "true") == "true":
                ai.reorganize_book(organized["project_id"], trigger_note_id=note_id)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        worker.start()
        yield
        stop_event.set()
        worker.join(timeout=max(settings.poll_seconds + 2, 10))

    app = FastAPI(
        title="KnowledgeForge AI",
        version="0.5.0",
        description=(
            "Security-first AI idea orchestration for developing private, unstructured source material "
            "into books, business opportunities, and projects."
        ),
        lifespan=lifespan,
    )
    static_dir = Path(__file__).parent / "static"
    app.mount("/assets", StaticFiles(directory=static_dir), name="assets")

    @app.get("/", include_in_schema=False)
    def home():
        return FileResponse(static_dir / "index.html")

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "library": library.stats(),
            "watcher_alive": worker.is_alive(),
            "ai_enabled": ai.enabled,
            "ai_provider": ai.provider,
            "ai_model": ai.model,
        }

    @app.get("/api/ai/options")
    def ai_options():
        return ai.options()

    @app.put("/api/ai/selection")
    def select_ai(payload: AISelection):
        options = ai.options()
        provider = next((item for item in options["providers"] if item["id"] == payload.provider), None)
        if provider is None:
            raise HTTPException(422, "Unknown provider; add it to config/ai-providers.json")
        # OpenAI choices are curated. Ollama names come from the local service;
        # a custom Ollama model is accepted when the service is temporarily off.
        if provider["id"] != "ollama" and payload.model not in provider["models"]:
            raise HTTPException(422, "Unsupported catalog model")
        library.set_settings({"ai_provider": payload.provider, "ai_model": payload.model.strip()})
        logging.info("AI selection changed to %s / %s", payload.provider, payload.model)
        return ai.options()

    @app.get("/api/books/{project_id}")
    def get_book(project_id: int):
        try:
            book = library.get_book(project_id)
        except KeyError as exc:
            raise HTTPException(404, "Book project not found") from exc
        book["revisions"] = library.list_revisions(project_id)
        return book

    @app.put("/api/books/{project_id}/instructions")
    def save_instructions(project_id: int, payload: BookInstructions):
        try:
            library.get_book(project_id)
        except KeyError as exc:
            raise HTTPException(404, "Book project not found") from exc
        library.save_book_instructions(project_id, payload.instructions)
        return library.get_book(project_id)

    @app.post("/api/books/{project_id}/reorganize")
    def reorganize_book(project_id: int, payload: ReorganizeRequest):
        try:
            return ai.reorganize_book(project_id, feedback=payload.feedback)
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc
        except Exception as exc:
            logging.exception("Book reorganization failed")
            raise HTTPException(502, "Book reorganization failed; see private log.") from exc

    @app.get("/api/projects/{project_id}/tasks")
    def project_tasks(project_id: int):
        try:
            library.get_book(project_id)
        except KeyError as exc:
            raise HTTPException(404, "Workspace not found") from exc
        return library.list_tasks(project_id)

    @app.post("/api/projects/{project_id}/tasks", status_code=201)
    def create_task(project_id: int, payload: TaskCreate):
        try:
            library.get_book(project_id)
        except KeyError as exc:
            raise HTTPException(404, "Workspace not found") from exc
        return library.add_task(project_id, **payload.model_dump())

    @app.patch("/api/projects/{project_id}/tasks/{task_id}")
    def update_task(project_id: int, task_id: int, payload: TaskUpdate):
        task = library.update_task(project_id, task_id, payload.model_dump(exclude_unset=True))
        if task is None:
            raise HTTPException(404, "Task not found")
        return task

    @app.post("/api/projects/{project_id}/tasks/replan")
    def replan_tasks(project_id: int):
        try:
            return ai.refresh_plan(project_id, reason="Owner requested a fresh execution plan")
        except KeyError as exc:
            raise HTTPException(404, "Workspace not found") from exc
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc
        except Exception as exc:
            logging.exception("Execution-plan refresh failed")
            raise HTTPException(502, "Execution-plan refresh failed; see private log.") from exc

    @app.get("/api/books/{project_id}/export")
    def export_book(project_id: int):
        try:
            book = library.get_book(project_id)
        except KeyError as exc:
            raise HTTPException(404, "Book project not found") from exc
        content = f"# {book['project']['name']}\n\n" + "\n\n".join(
            f"## {section['title']}\n\n{section['content']}" for section in book["sections"]
        )
        filename = re.sub(r"[^A-Za-z0-9._-]+", "-", book["project"]["name"]).strip("-") or "book"
        return Response(
            content,
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="{filename}.md"'},
        )

    @app.get("/api/projects")
    def projects():
        return library.list_projects()

    @app.post("/api/projects", status_code=201)
    def create_project(payload: ProjectCreate):
        project_id = library.ensure_project(payload.name, payload.description, payload.workspace_type)
        return next(p for p in library.list_projects() if p["id"] == project_id)

    @app.get("/api/opportunities")
    def opportunities(status: str = Query(default="new", pattern="^(new|exploring|dismissed)$")):
        return library.list_opportunities(status)

    @app.post("/api/opportunities/{opportunity_id}/explore")
    def explore_opportunity(opportunity_id: int):
        result = library.explore_opportunity(opportunity_id)
        if result is None:
            raise HTTPException(404, "Opportunity not found")
        return result

    @app.get("/api/notes")
    def notes(
        q: str = Query(default="", max_length=200),
        category: str = Query(default="", max_length=50),
        project_id: int | None = None,
    ):
        return library.list_notes(q.strip(), category.strip(), project_id)

    @app.get("/api/notes/{note_id}")
    def note(note_id: int):
        item = library.get_note(note_id)
        if not item:
            raise HTTPException(404, "Note not found")
        return item

    @app.patch("/api/notes/{note_id}")
    def update_note(note_id: int, payload: NoteUpdate):
        tags = sorted({tag.strip().lower() for tag in payload.tags if tag.strip()})
        if not library.update_note(
            note_id,
            title=payload.title,
            category=payload.category,
            tags=tags,
            summary=payload.summary,
            project_id=payload.project_id,
        ):
            raise HTTPException(404, "Note not found")
        return library.get_note(note_id)

    @app.post("/api/notes/{note_id}/analyze")
    def analyze(note_id: int):
        if not library.get_note(note_id):
            raise HTTPException(404, "Note not found")
        try:
            organized = ai.analyze(note_id)
            if organized.get("project_id") and library.get_setting("auto_integrate", "true") == "true":
                ai.reorganize_book(organized["project_id"], trigger_note_id=note_id)
            return library.get_note(note_id)
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc
        except Exception as exc:
            library.mark_analysis_failed(note_id, str(exc))
            logging.exception("Analysis failed")
            raise HTTPException(502, "AI analysis failed; details are in the private log.") from exc

    @app.post("/api/notes/{note_id}/organize")
    def local_organize(note_id: int):
        item = library.get_note(note_id)
        if not item:
            raise HTTPException(404, "Note not found")
        draft = organize_transcript(item["transcript"])
        library.update_note(
            note_id,
            title=item["title"],
            category=item["category"],
            tags=list(draft["tags"]),
            summary=str(draft["summary"]),
            project_id=item["project_id"],
        )
        return library.get_note(note_id)

    @app.post("/api/chat")
    def chat(payload: ChatRequest):
        try:
            return ai.answer(payload.question, payload.project_id, payload.selected_note_ids)
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc
        except Exception as exc:
            logging.exception("Library chat failed")
            raise HTTPException(502, "AI chat failed; see private log.") from exc

    @app.post("/api/scan", status_code=202)
    def scan(background: BackgroundTasks):
        background.add_task(pipeline.run_once)
        return {"accepted": True}

    @app.post("/api/upload", status_code=202)
    async def upload(file: Annotated[UploadFile, File()]):
        original = _safe_filename(file.filename or "recording.webm")
        extension = Path(original).suffix.lower()
        if extension not in AUDIO_EXTENSIONS:
            raise HTTPException(415, f"Unsupported audio type: {extension or 'none'}")
        destination = settings.inbox / f"{uuid4().hex[:8]}-{original}"
        maximum = settings.max_upload_mb * 1024 * 1024
        written = 0
        try:
            with destination.open("wb") as output:
                while chunk := await file.read(1024 * 1024):
                    written += len(chunk)
                    if written > maximum:
                        raise HTTPException(413, f"Upload exceeds {settings.max_upload_mb} MB")
                    output.write(chunk)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        finally:
            await file.close()
        logging.info("Accepted upload: %s", destination.name)
        return {"accepted": True, "filename": destination.name}

    @app.post("/api/import", status_code=202)
    async def import_content(background: BackgroundTasks, file: Annotated[UploadFile, File()]):
        original = _safe_filename(file.filename or "content.txt")
        allowed = {".txt", ".md", ".pdf", ".docx", ".png", ".jpg", ".jpeg", ".webp", ".gif"}
        if Path(original).suffix.lower() not in allowed:
            raise HTTPException(415, "Supported imports: TXT, Markdown, PDF, DOCX, PNG, JPG, WEBP, GIF")
        destination = settings.imports / f"{uuid4().hex[:8]}-{original}"
        maximum = settings.max_upload_mb * 1024 * 1024
        written = 0
        try:
            with destination.open("wb") as output:
                while chunk := await file.read(1024 * 1024):
                    written += len(chunk)
                    if written > maximum:
                        raise HTTPException(413, f"Upload exceeds {settings.max_upload_mb} MB")
                    output.write(chunk)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        finally:
            await file.close()
        background.add_task(process_import, destination)
        return {"accepted": True, "filename": destination.name}

    @app.get("/api/notes/{note_id}/audio")
    def audio(note_id: int):
        item = library.get_note(note_id)
        if not item:
            raise HTTPException(404, "Note not found")
        path = Path(item["audio_path"])
        if not path.exists():
            raise HTTPException(404, "Archived audio is unavailable")
        return FileResponse(path, media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream")

    return app
