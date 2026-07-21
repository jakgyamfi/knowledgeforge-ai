"""Audio discovery, transcription, archiving, and library indexing.

The pipeline is deliberately independent from FastAPI.  This makes it usable
from the CLI, the background web worker, tests, and a future queue container.
"""

from __future__ import annotations

import json
import logging
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import Settings
from .library import Library
from .ai import AIService

AUDIO_EXTENSIONS = {
    ".wav",
    ".mp3",
    ".m4a",
    ".aac",
    ".flac",
    ".ogg",
    ".wma",
    ".mp4",
    ".mov",
    ".webm",
}


class TranscriptionPipeline:
    """Coordinates local Whisper processing and durable private outputs."""

    def __init__(self, settings: Settings, library: Library | None = None) -> None:
        self.settings = settings
        self.library = library or Library(settings.database)
        self._model: Any | None = None
        # Whisper model loading is expensive and must not race between the web
        # upload endpoint and the polling worker.
        self._model_lock = threading.Lock()
        self.ai = AIService(settings, self.library)

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        with self._model_lock:
            if self._model is None:
                try:
                    import whisper
                except ImportError as exc:
                    raise RuntimeError(
                        "Whisper is missing. Activate the virtual environment and "
                        "run: python -m pip install -r requirements.txt"
                    ) from exc
                logging.info("Loading Whisper model '%s' on %s", self.settings.model, self.settings.device)
                self._model = whisper.load_model(self.settings.model, device=self.settings.device)
        return self._model

    def discover(self) -> list[Path]:
        """Find local files and iCloud placeholders by their media extension."""
        candidates: set[Path] = set()
        for source_root in (self.settings.inbox, self.settings.recordings):
            candidates.update(path for path in source_root.rglob("*") if path.suffix.lower() in AUDIO_EXTENSIONS)
        return sorted(candidates)

    def _relative_path(self, source: Path) -> Path:
        if source.is_relative_to(self.settings.inbox):
            return source.relative_to(self.settings.inbox)
        return source.relative_to(self.settings.recordings)

    def output_paths(self, source: Path) -> tuple[Path, Path, Path]:
        """Map one source to transcript, metadata, and local archive paths."""
        relative = self._relative_path(source)
        transcript = self.settings.transcripts / relative.with_suffix(".txt")
        metadata = self.settings.transcripts / relative.with_suffix(".json")
        archive = self.settings.recordings / relative
        return transcript, metadata, archive

    @staticmethod
    def _request_local_file(source: Path) -> None:
        """Open one byte so a cloud provider hydrates an online-only file."""
        logging.info("Ensuring recording is available locally: %s", source.name)
        with source.open("rb") as audio:
            audio.read(1)

    @staticmethod
    def _atomic_text(path: Path, content: str) -> None:
        """Avoid half-written transcript files if the process is interrupted."""
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(path)

    def _archive_copy(self, source: Path, archive: Path) -> None:
        """Copy from iCloud locally; never delete/move cloud files in the worker."""
        if source.is_relative_to(self.settings.recordings):
            return
        archive.parent.mkdir(parents=True, exist_ok=True)
        if archive.exists() and archive.stat().st_size == source.stat().st_size:
            return
        shutil.copy2(source, archive)
        logging.info("Archived local copy: %s", archive)

    def process(self, source: Path, *, overwrite: bool = False) -> int:
        """Process one recording and return its private library record ID."""
        transcript_path, metadata_path, archive_path = self.output_paths(source)
        self._request_local_file(source)

        if transcript_path.exists() and not overwrite:
            transcript = transcript_path.read_text(encoding="utf-8")
            self._archive_copy(source, archive_path)
        else:
            model = self._load_model()
            options: dict[str, Any] = {"fp16": self.settings.device != "cpu"}
            if self.settings.language:
                options["language"] = self.settings.language
            logging.info("Transcribing %s", source)
            result = model.transcribe(str(source), **options)
            transcript = str(result.get("text", "")).strip()
            self._atomic_text(transcript_path, transcript + "\n")
            metadata = {
                "source": str(source),
                "archived_audio": str(archive_path),
                "transcript": str(transcript_path),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "model": self.settings.model,
                "language": result.get("language"),
            }
            self._atomic_text(metadata_path, json.dumps(metadata, indent=2) + "\n")
            self._archive_copy(source, archive_path)
            logging.info("Saved transcript: %s", transcript_path)

        note_id = self.library.upsert_transcript(
            source_name=str(self._relative_path(source)),
            audio_path=archive_path,
            transcript_path=transcript_path,
            transcript=transcript.strip(),
        )
        if self.ai.enabled:
            try:
                logging.info("Analyzing and filing note %s", note_id)
                organized = self.ai.analyze(note_id)
                if organized.get("project_id") and self.library.get_setting("auto_integrate", "true") == "true":
                    logging.info("Integrating note %s into book project %s", note_id, organized["project_id"])
                    self.ai.reorganize_book(organized["project_id"], trigger_note_id=note_id)
            except Exception as exc:
                self.library.mark_analysis_failed(note_id, str(exc))
                logging.exception("AI analysis failed for note %s; retry it from the app.", note_id)
        return note_id

    def run_once(self, *, overwrite: bool = False) -> dict[str, int]:
        """Process a scan without allowing one bad cloud file to stop the batch."""
        completed = failed = 0
        for source in self.discover():
            try:
                transcript, _, archive = self.output_paths(source)
                source_name = str(self._relative_path(source))
                if transcript.exists() and archive.exists() and self.library.has_source(source_name):
                    continue
                self.process(source, overwrite=overwrite)
                completed += 1
            except OSError as exc:
                failed += 1
                logging.warning("Recording unavailable; will retry %s: %s", source.name, exc)
            except Exception:
                failed += 1
                logging.exception("Failed to process %s; later scans will retry.", source.name)
        return {"completed": completed, "failed": failed}

    def watch(self, stop_event: threading.Event | None = None) -> None:
        """Poll until signaled; used by both CLI and web application lifespan."""
        stop_event = stop_event or threading.Event()
        logging.info("Watching %s every %.1f seconds", self.settings.inbox, self.settings.poll_seconds)
        while not stop_event.is_set():
            self.run_once()
            stop_event.wait(self.settings.poll_seconds)
        logging.info("Watcher stopped.")
