# Changelog

All notable changes to KnowledgeForge are documented here.

## 0.11.0

### Added

- Purpose-specific Book, Venture, Impact, Project, and Idea Studios.
- Profile- and CV-informed opportunity discovery with approval-based validation.
- Workspace accelerator for book architecture, chapter briefs, continuity,
  venture hypotheses, success measures, milestones, and execution tasks.
- Unified growth planning across goals, certifications, and active workspaces.
- Complete-project chat across source material, living documents, studio cards,
  owner direction, and execution plans.
- Secure provider selection for OpenAI, Anthropic, Z.ai, xAI, Meta, Gemini,
  Moonshot/Kimi, DeepSeek, and local Ollama models.
- Windows Credential Manager/DPAPI secret storage and deployment-specific
  Linux/container secret backends.
- Owner-approved public HTTPS research and selected-material improvement.
- Private operational logging and metadata-only outbound audit logging with
  size-based rotation and gzip compression.
- Embedded Markdown and PDF user manuals.

### Security

- Private recordings, transcripts, imports, profiles, databases, logs, runtime
  configuration, and API keys remain excluded from Git.
- Public research rejects HTTP, credentialed URLs, and private, loopback, or
  link-local network destinations.
- API keys are never returned to the browser and credential inputs are cleared
  after submission.

### Validation

- Ruff linting passes.
- 25 automated tests pass.
- Source distribution and wheel builds pass.
