# Private logging and audit

KnowledgeForge creates the private `logs/` directory at startup.

| File | Purpose |
|---|---|
| `knowledgeforge.log` | watcher, transcription, analysis, web, and error events |
| `egress-audit.jsonl` | metadata-only AI and public-research routing events |

The egress audit records provider, model, destination host/port, TLS/local
status, operation type, timing, and byte counts when available. It intentionally
does not record prompts, transcripts, model responses, keys, or authorization
headers.

Both logs rotate when they reach `KF_LOG_MAX_MB` (10 MB by default). Rotated
segments are gzip-compressed, the active file restarts automatically, and
`KF_LOG_BACKUPS` (10 by default) controls retention. The whole folder is
gitignored.

Example:

```dotenv
KF_LOG_DIR=logs
KF_LOG_MAX_MB=10
KF_LOG_BACKUPS=10
```

Public research accepts HTTPS destinations only and rejects URLs containing
credentials or resolving to private, loopback, or link-local addresses. Ollama
is the explicit local HTTP exception at `127.0.0.1:11434`.
