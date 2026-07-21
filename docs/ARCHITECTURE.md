# Architecture

KnowledgeForge is a security-first idea orchestration system. Its architecture separates capture, local source processing, AI-provider egress, and durable workspace development so the owner can understand where private data lives and when it crosses a trust boundary.

KnowledgeForge is split into small modules so each operational concern can be tested or replaced independently.

```text
config.py       environment and private paths
library.py      SQLite persistence and search
pipeline.py     discovery, Whisper, transcript output, safe archive copy
organizer.py    offline summary/tag draft
web.py          FastAPI routes and background worker lifecycle
cli.py          verify, batch, watch, and serve commands
static/         dependency-light browser interface
```

## Processing guarantees

1. The worker discovers supported extensions without relying on `is_file()`, because online-only iCloud placeholders can report false.
2. Opening one byte requests local hydration before FFmpeg runs.
3. Transcript and metadata files are written through temporary files and atomically replaced.
4. Audio is copied locally only after transcript output succeeds.
5. The worker never deletes or moves iCloud sources.
6. Existing transcript, archive, and database records make repeated scans idempotent.
7. One failed recording is logged and retried without stopping the worker.

## Migration seams

- Replace polling with a queue without changing `Library` or the web API.
- Replace local Whisper through `TranscriptionPipeline._load_model` and `process`.
- Replace the offline organizer behind `organize_transcript`.
- Move SQLite to PostgreSQL by replacing the `Library` implementation.
- Split web and worker processes when deploying containers to the Linux VM.

## Private data

Runtime directories are excluded from Git and Docker build context. In Docker they live under `/data`; on Windows they default to the repository root or configured absolute paths.
