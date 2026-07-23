from pathlib import Path
import json

from pydantic import BaseModel

from knowledgeforge.ai import AIService
from knowledgeforge.config import Settings
from knowledgeforge.library import Library
from knowledgeforge.organizer import organize_transcript
from knowledgeforge.pipeline import TranscriptionPipeline
from knowledgeforge.secrets import ProviderSecrets


class StructuredFixture(BaseModel):
    title: str


def settings(tmp_path: Path) -> Settings:
    return Settings(
        root=tmp_path,
        inbox=tmp_path / "Inbox",
        recordings=tmp_path / "recordings",
        transcripts=tmp_path / "transcripts",
        summaries=tmp_path / "summaries",
        logs=tmp_path / "logs",
        database=tmp_path / "database" / "knowledgeforge.db",
        model="base",
        language=None,
        device="cpu",
        poll_seconds=5,
        web_host="127.0.0.1",
        web_port=8765,
        max_upload_mb=250,
        ai_provider="openai",
        ai_model="gpt-5.6",
        openai_api_key=None,
        default_project="My Book",
        ollama_url="http://127.0.0.1:11434",
        anthropic_api_key=None,
        provider_catalog=tmp_path / "config" / "ai-providers.json",
        imports=tmp_path / "imports",
    )


def test_pipeline_paths_and_non_destructive_archive(tmp_path: Path) -> None:
    config = settings(tmp_path)
    config.ensure_directories()
    pipeline = TranscriptionPipeline(config)
    source = config.inbox / "chapter-one" / "idea.m4a"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"safe-test-audio")
    transcript, metadata, archive = pipeline.output_paths(source)
    assert transcript == config.transcripts / "chapter-one" / "idea.txt"
    assert metadata == config.transcripts / "chapter-one" / "idea.json"
    pipeline._archive_copy(source, archive)
    assert source.exists()  # iCloud source is never deleted by the worker.
    assert archive.read_bytes() == b"safe-test-audio"


def test_library_search_and_update(tmp_path: Path) -> None:
    library = Library(tmp_path / "library.db")
    note_id = library.upsert_transcript(
        source_name="idea.m4a",
        audio_path=tmp_path / "idea.m4a",
        transcript_path=tmp_path / "idea.txt",
        transcript="A lighthouse appears in the final chapter.",
    )
    assert library.list_notes("lighthouse")[0]["id"] == note_id
    project_id = library.ensure_project("Novel")
    assert library.update_note(
        note_id,
        title="The Lighthouse",
        category="author",
        tags=["ending"],
        summary="Final scene",
        project_id=project_id,
    )
    assert library.get_note(note_id)["tags"] == ["ending"]
    assert library.get_note(note_id)["project_name"] == "Novel"


def test_structured_analysis_is_saved_without_losing_transcript(tmp_path: Path) -> None:
    library = Library(tmp_path / "library.db")
    note_id = library.upsert_transcript(
        source_name="idea.m4a",
        audio_path=tmp_path / "idea.m4a",
        transcript_path=tmp_path / "idea.txt",
        transcript="Mara enters the lighthouse.",
    )
    analysis = {
        "title": "Arrival",
        "summary": "Mara arrives.",
        "content_type": "author",
        "tags": ["mara"],
        "characters": [{"name": "Mara"}],
        "scenes": [],
        "themes": [],
        "story_ideas": [],
        "key_ideas": [],
        "decisions": [],
        "assigned_tasks": [],
        "deadlines": [],
        "risks": [],
        "open_questions": [],
        "follow_up_items": [],
    }
    library.save_analysis(note_id, analysis, library.ensure_project("Novel"))
    note = library.get_note(note_id)
    assert note["analysis_status"] == "complete"
    assert note["analysis"]["characters"][0]["name"] == "Mara"
    assert note["transcript"] == "Mara enters the lighthouse."


def test_runtime_ai_selection_is_persistent(tmp_path: Path) -> None:
    database = tmp_path / "library.db"
    library = Library(database)
    assert library.ensure_setting("ai_provider", "openai") == "openai"
    library.set_settings({"ai_provider": "ollama", "ai_model": "local-writing-model"})
    reopened = Library(database)
    assert reopened.get_setting("ai_provider") == "ollama"
    assert reopened.get_setting("ai_model") == "local-writing-model"


def test_compatible_provider_structured_response_wrappers() -> None:
    direct = AIService._validate_structured_content('{"title":"Direct"}', StructuredFixture)
    wrapped = AIService._validate_structured_content(
        '{"answer":"{\\"title\\":\\"Wrapped\\"}"}',
        StructuredFixture,
    )
    fenced = AIService._validate_structured_content(
        '{"answer":"```json\\n{\\"title\\":\\"Fenced\\"}\\n```"}',
        StructuredFixture,
    )
    assert (direct.title, wrapped.title, fenced.title) == ("Direct", "Wrapped", "Fenced")


def test_pending_analysis_queue_is_oldest_first(tmp_path: Path) -> None:
    library = Library(tmp_path / "library.db")
    first = library.upsert_transcript(
        source_name="first.txt",
        audio_path=tmp_path / "first.txt",
        transcript_path=tmp_path / "first-transcript.txt",
        transcript="First thought",
    )
    second = library.upsert_transcript(
        source_name="second.txt",
        audio_path=tmp_path / "second.txt",
        transcript_path=tmp_path / "second-transcript.txt",
        transcript="Second thought",
    )
    library.mark_analysis_failed(first, "temporary provider error")
    assert library.pending_analysis_ids() == [first, second]


def test_opportunity_can_be_promoted_to_workspace(tmp_path: Path) -> None:
    library = Library(tmp_path / "library.db")
    note_id = library.upsert_transcript(
        source_name="idea.txt",
        audio_path=tmp_path / "idea.txt",
        transcript_path=tmp_path / "idea.txt",
        transcript="A possible consulting business.",
    )
    analysis = {
        "title": "Consulting idea",
        "summary": "A service opportunity.",
        "content_type": "business",
        "tags": ["consulting"],
        "opportunities": [
            {
                "kind": "business",
                "title": "Advisory Studio",
                "description": "A focused advisory service.",
                "rationale": "Matches existing expertise.",
            }
        ],
    }
    library.save_analysis(note_id, analysis, library.ensure_project("Business Ideas", workspace_type="business"))
    opportunity = library.list_opportunities()[0]
    promoted = library.explore_opportunity(opportunity["id"])
    assert promoted["status"] == "exploring"
    assert library.get_book(promoted["project_id"])["project"]["workspace_type"] == "business"


def test_local_organizer_is_deterministic() -> None:
    result = organize_transcript(
        "Mara enters the lighthouse. The storm cuts the electricity. Mara discovers the hidden journal. Extra detail follows."
    )
    assert result["summary"].endswith("hidden journal.")
    assert "mara" in result["tags"]


def test_living_plan_preserves_manual_and_completed_tasks(tmp_path: Path) -> None:
    library = Library(tmp_path / "library.db")
    project_id = library.ensure_project("Launch", workspace_type="project")
    manual = library.add_task(project_id, title="Confirm the scope", estimate_minutes=45)
    library.replace_ai_tasks(
        project_id,
        [{"title": "Build prototype", "priority": "high", "estimate_minutes": 120, "dependencies": []}],
    )
    generated = next(task for task in library.list_tasks(project_id) if task["source"] == "ai")
    library.update_task(project_id, generated["id"], {"status": "done"})

    library.replace_ai_tasks(
        project_id,
        [
            {"title": "Build prototype", "priority": "high", "estimate_minutes": 120, "dependencies": []},
            {
                "title": "Document rollout",
                "priority": "medium",
                "estimate_minutes": 60,
                "dependencies": ["Build prototype"],
            },
        ],
    )
    tasks = library.list_tasks(project_id)
    assert next(task for task in tasks if task["id"] == manual["id"])["source"] == "manual"
    assert len([task for task in tasks if task["title"] == "Build prototype"]) == 1
    assert next(task for task in tasks if task["title"] == "Build prototype")["status"] == "done"
    assert next(task for task in tasks if task["title"] == "Document rollout")["estimate_minutes"] == 60


def test_file_secret_backend_does_not_fall_back_to_environment(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "environment-value")
    (tmp_path / "OPENAI_API_KEY").write_text("mounted-value\n", encoding="utf-8")
    store = ProviderSecrets("file", tmp_path)
    assert store.get("OPENAI_API_KEY") == "mounted-value"
    assert store.source("OPENAI_API_KEY") == "file"
    (tmp_path / "OPENAI_API_KEY").unlink()
    assert store.get("OPENAI_API_KEY") is None


def test_environment_backend_is_explicit(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "environment-value")
    store = ProviderSecrets("environment")
    assert store.get("OPENAI_API_KEY") == "environment-value"
    assert not store.writable


def test_packaged_provider_catalog_contains_current_choices() -> None:
    catalog_path = Path(__file__).parents[1] / "config" / "ai-providers.json"
    providers = {item["id"]: item for item in json.loads(catalog_path.read_text(encoding="utf-8"))["providers"]}
    assert providers["zai"]["models"][0] == "glm-5.2"
    assert "gemini-3.1-pro-preview" in providers["gemini"]["models"]
    assert "claude-sonnet-5" in providers["anthropic"]["models"]
    assert providers["xai"]["models"][0] == "grok-4.5"
    assert "meta" in providers
