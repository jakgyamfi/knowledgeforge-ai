"""Configuration loading for every KnowledgeForge entry point.

All mutable data paths are configurable so the same code can run on a Windows
desktop today and inside a Linux container later.  A local `.env` file is
supported without adding another runtime dependency.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path


def repository_root() -> Path:
    """Return the checkout root for editable and source-based installations."""
    return Path(__file__).resolve().parents[2]


def _load_env_file(path: Path) -> None:
    """Load simple KEY=VALUE pairs while preserving explicitly set variables."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def _path(root: Path, value: str) -> Path:
    candidate = Path(value).expanduser()
    return candidate if candidate.is_absolute() else root / candidate


def ensure_ffmpeg_on_path() -> Path | None:
    """Find WinGet FFmpeg when Windows has not refreshed PATH correctly.

    Package managers commonly install FFmpeg successfully while the current
    desktop session retains an older PATH.  This fallback is Windows-specific,
    user-independent, and does not modify the permanent system environment.
    """
    existing = shutil.which("ffmpeg")
    if existing:
        return Path(existing)
    local_app_data = os.getenv("LOCALAPPDATA")
    if not local_app_data:
        return None
    packages = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
    matches = sorted(packages.glob("Gyan.FFmpeg*/*/bin/ffmpeg.exe"), reverse=True)
    if not matches:
        return None
    binary = matches[0]
    os.environ["PATH"] = f"{binary.parent}{os.pathsep}{os.environ.get('PATH', '')}"
    return binary


@dataclass(frozen=True)
class Settings:
    """Validated runtime locations and behavior shared by CLI and web app."""

    root: Path
    inbox: Path
    recordings: Path
    transcripts: Path
    summaries: Path
    logs: Path
    database: Path
    model: str
    language: str | None
    device: str
    poll_seconds: float
    web_host: str
    web_port: int
    max_upload_mb: int
    ai_provider: str
    ai_model: str
    openai_api_key: str | None
    default_project: str
    ollama_url: str
    anthropic_api_key: str | None
    provider_catalog: Path
    imports: Path
    log_max_mb: int = 10
    log_backups: int = 10

    @classmethod
    def load(cls) -> "Settings":
        root = repository_root()
        _load_env_file(root / ".env")
        _load_env_file(root / ".env.providers")
        ensure_ffmpeg_on_path()
        settings = cls(
            root=root,
            inbox=_path(root, os.getenv("KF_INBOX_DIR", "Inbox")),
            recordings=_path(root, os.getenv("KF_RECORDINGS_DIR", "recordings")),
            transcripts=_path(root, os.getenv("KF_TRANSCRIPTS_DIR", "transcripts")),
            summaries=_path(root, os.getenv("KF_SUMMARIES_DIR", "summaries")),
            logs=_path(root, os.getenv("KF_LOG_DIR", "logs")),
            database=_path(root, os.getenv("KF_DATABASE_PATH", "database/knowledgeforge.db")),
            model=os.getenv("KF_WHISPER_MODEL", "base"),
            language=os.getenv("KF_LANGUAGE") or None,
            device=os.getenv("KF_DEVICE", "cpu"),
            poll_seconds=float(os.getenv("KF_POLL_SECONDS", "5")),
            web_host=os.getenv("KF_WEB_HOST", "127.0.0.1"),
            web_port=int(os.getenv("KF_WEB_PORT", "8765")),
            max_upload_mb=int(os.getenv("KF_MAX_UPLOAD_MB", "250")),
            ai_provider=os.getenv("KF_AI_PROVIDER", "openai").lower(),
            ai_model=os.getenv("KF_AI_MODEL", "gpt-5.6"),
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            default_project=os.getenv("KF_DEFAULT_PROJECT", "My Book"),
            ollama_url=os.getenv("KF_OLLAMA_URL", "http://127.0.0.1:11434"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
            provider_catalog=_path(root, os.getenv("KF_AI_PROVIDER_CATALOG", "config/ai-providers.json")),
            imports=_path(root, os.getenv("KF_IMPORTS_DIR", "imports")),
            log_max_mb=int(os.getenv("KF_LOG_MAX_MB", "10")),
            log_backups=int(os.getenv("KF_LOG_BACKUPS", "10")),
        )
        settings.ensure_directories()
        return settings

    def ensure_directories(self) -> None:
        """Create private runtime directories; `.gitignore` excludes them."""
        for directory in (
            self.inbox,
            self.recordings,
            self.transcripts,
            self.summaries,
            self.logs,
            self.database.parent,
            self.imports,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    @property
    def ai_enabled(self) -> bool:
        return (self.ai_provider == "openai" and bool(self.openai_api_key)) or self.ai_provider == "ollama"
