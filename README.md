# KnowledgeForge AI

> **Capture the thought. Discover the opportunity. Develop the work.**

KnowledgeForge is a security-first, local-first AI idea orchestration platform. It turns scattered voice notes, documents, and images into structured books, business opportunities, project plans, and searchable private knowledge.

The application preserves the original source, transcribes audio locally with Whisper, and sends the resulting text through a deliberately configured AI orchestration layer. The selected model can classify the idea, extract themes and opportunities, integrate it into an evolving workspace, and reorganize that workspace as its owner gives new direction.

## Why KnowledgeForge exists

KnowledgeForge began with a practical problem.

While documenting lessons from cloud security and AI infrastructure projects for [agyaponggyamfi.com](https://agyaponggyamfi.com/), ideas often arrived faster than they could be turned into useful writing. Recording a quick thought was easy. Finding it later, connecting it to related experiences, and developing dozens of fragments into a coherent article, book, business concept, or project was not.

Existing tools addressed parts of that workflow, but building a personal system created two additional benefits: complete visibility into what processes private material, and a hands-on environment for applying security-first engineering to AI systems. KnowledgeForge was born from that intersection—an everyday creative tool and a living engineering project.

It is built by **Agyapong Gyamfi**, a Cloud Security Engineer focused on securing AI agents, MCP servers, and the cloud infrastructure they depend on.

Read the fuller story in [About KnowledgeForge](docs/ABOUT.md).

## From capture to developed work

```text
Voice note / document / image
              |
              v
      Private source inbox
              |
              v
   Local extraction or Whisper
              |
              v
      AI orchestration layer
       |       |        |
       v       v        v
   classify  structure  discover
       |       |        |
       +-------+--------+
               |
               v
   Evolving book, business, or project workspace
```

KnowledgeForge can:

- receive audio through iCloud, OneDrive, Google Drive, a network folder, or direct upload;
- detect new files and transcribe supported audio locally with Whisper;
- preserve the original recording and clean transcript;
- ingest text, Markdown, PDF, Word, and image files;
- use OpenAI, Claude, Gemini, Kimi, DeepSeek, or local Ollama models;
- extract titles, summaries, tags, people, characters, scenes, themes, decisions, tasks, risks, deadlines, questions, and opportunities;
- classify ideas as book, business, project, personal, meeting, or journal material;
- integrate new material into a versioned working document;
- reorganize workspaces from persistent owner instructions and feedback;
- search and ask questions across the private source library;
- run on Windows today, in Docker, or on a private Linux host.

## Security-first by design

The local computer remains the system of record. Source media, transcripts, workspaces, databases, logs, and secrets are private and excluded from Git.

- **Local processing first:** Whisper transcription and source storage stay on the host.
- **Explicit AI egress:** content reaches a cloud model only when that provider is selected and configured. Ollama provides a local-model path.
- **Inspectable orchestration:** providers, models, prompts, processing stages, and storage locations are visible and configurable.
- **Non-destructive development:** source material is preserved and working documents are revisioned before AI reorganization.
- **Local network boundary:** the application binds to `127.0.0.1` by default and is not safe to expose directly to the internet without the controls in the deployment runbook.
- **Private by default:** `.env`, recordings, transcripts, summaries, databases, logs, and personal or business data remain gitignored.

See [SECURITY.md](SECURITY.md) for the trust boundaries and [Cloud/SaaS Runbook](docs/CLOUD-SAAS-RUNBOOK.md) for production controls.

## Quick start on Windows

Requirements: Python 3.10–3.13, FFmpeg on `PATH`, and Whisper.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
knowledgeforge verify
knowledgeforge serve
```

Open <http://127.0.0.1:8765>. Record or upload directly, or copy audio into the configured `Inbox`. The worker will transcribe it and the active AI provider can analyze and integrate it automatically.

For the complete setup, iCloud workflow, FFmpeg verification, desktop launchers, Docker, and troubleshooting, see [Setup](docs/SETUP.md).

## AI providers

Provider definitions live in `config/ai-providers.json`; secrets belong only in `.env.providers`. The interface exposes the configured providers and models without putting credentials in the browser or repository.

```powershell
Copy-Item .env.providers.example .env.providers
```

Configure one or more providers, restart KnowledgeForge, and choose the active AI from the application. See [Provider Configuration](docs/PROVIDERS.md).

## Repository map

```text
config/                      provider catalog (no secrets)
docs/                        architecture, setup, security, and deployment guides
scripts/                     Windows start/stop helpers
src/knowledgeforge/          application, pipeline, orchestration, and interface
tests/                       automated behavior tests
Inbox/                       private incoming sources (gitignored)
recordings/                  preserved private audio (gitignored)
transcripts/                 private transcript output (gitignored)
summaries/                   private generated work (gitignored)
database/                    private application state (gitignored)
logs/                        private operational logs (gitignored)
```

## Documentation

- [About and origin story](docs/ABOUT.md)
- [Architecture](docs/ARCHITECTURE.md)
- [AI and workspace workflow](docs/AI-AND-WRITER-WORKFLOW.md)
- [Provider configuration](docs/PROVIDERS.md)
- [Setup and operation](docs/SETUP.md)
- [Docker deployment](docs/DOCKER-DEPLOYMENT.md)
- [Cloud/SaaS upgrade runbook](docs/CLOUD-SAAS-RUNBOOK.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)

## Project status

KnowledgeForge is an evolving portfolio project and usable local application. It is intentionally not presented as a finished multi-tenant SaaS product. Remote deployment requires authentication, authorization, tenant isolation, encrypted object storage, managed secrets, abuse controls, monitoring, and a formal privacy model.

## Author

Built by [Agyapong Gyamfi](https://agyaponggyamfi.com/) while exploring secure AI orchestration, private knowledge systems, MCP infrastructure, and production-grade cloud security.

Contributions and thoughtful security feedback are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

## License

MIT License. See [LICENSE](LICENSE).
