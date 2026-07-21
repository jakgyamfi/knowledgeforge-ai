# AI organization and writer workflow

KnowledgeForge keeps Whisper transcription local. When an AI provider is configured, only transcript text and selected note excerpts are sent for analysis or chat; raw audio, local paths, and the SQLite database are not uploaded.

## Enable OpenAI

1. Create an API key in the OpenAI API dashboard. A ChatGPT subscription does not automatically include API usage.
2. Copy `.env.example` to `.env` if needed.
3. Set `OPENAI_API_KEY` in `.env`. Never commit `.env`.
4. Optionally change `KF_DEFAULT_PROJECT` and `KF_AI_MODEL`.
5. Restart KnowledgeForge from the desktop shortcut.

The status line should say **AI ready**. Existing transcripts show **pending** and can be processed with **Analyze with AI**. New transcripts are analyzed and filed automatically.

The provider and model selectors at the top of the application switch the active AI immediately—no restart is required. The selection is stored in the private SQLite database. API keys remain only in `.env`; they are never returned to the browser.

## Analysis output

- title, summary, content type, project, and tags
- characters, traits, roles, and relationships
- scenes, settings, participants, conflict, and chronology hints
- themes, story ideas, and key ideas
- decisions, tasks, assignees, deadlines, risks, questions, and follow-ups

Missing information is returned as an empty list; the prompt forbids invented facts.

## Writer chat

Choose a project to constrain the library, then ask a question. Answers cite supporting notes as `[Note ID]`. Search stays local. Chat sends only retrieved excerpts to the configured provider.

Examples: find Chapter 4 ideas; check character contradictions; assemble an opening scene; create an outline; identify recurring ideas; or draft a rough chapter without inventing canon.

Provider code is isolated in `src/knowledgeforge/ai.py`. OpenAI and local Ollama are supported without changing Whisper or the library.

## Fully local AI with Ollama

Install Ollama and pull a model that handles structured output. Set `KF_AI_PROVIDER=ollama`, `KF_AI_MODEL` to the installed model, and `KF_OLLAMA_URL` if Ollama runs elsewhere. No transcript content is sent to a cloud provider in this mode.
