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


def test_workspace_can_be_renamed_contextualized_and_deleted_without_losing_sources(tmp_path: Path) -> None:
    library = Library(tmp_path / "library.db")
    project_id = library.ensure_project("Draft Venture", workspace_type="business")
    note_id = library.upsert_transcript(
        source_name="market-note.txt",
        audio_path=tmp_path / "market-note.txt",
        transcript_path=tmp_path / "market-note-transcript.txt",
        transcript="Customer evidence.",
        project_id=project_id,
    )
    library.add_workspace_card(project_id, "evidence", "First signal", "Interview evidence")
    updated = library.update_project(
        project_id,
        name="Security Venture",
        description="Build an evidence-led security product with measurable adoption.",
    )
    assert updated["name"] == "Security Venture"
    assert updated["description"].startswith("Build an evidence-led")
    assert library.delete_project(project_id)
    assert library.get_note(note_id)["project_id"] is None
    assert library.get_note(note_id)["transcript"] == "Customer evidence."


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


def test_compatible_provider_repairs_invalid_backslash_escape() -> None:
    repaired = AIService._validate_structured_content(
        r'{"title":"Draft stored in C:\KnowledgeForge\drafts"}',
        StructuredFixture,
    )
    assert repaired.title == r"Draft stored in C:\KnowledgeForge\drafts"


def test_workspace_research_rejects_local_and_private_urls() -> None:
    assert not AIService._public_url("http://127.0.0.1:8765/private")
    assert not AIService._public_url("http://localhost/private")
    assert not AIService._public_url("file:///etc/passwd")
    assert not AIService._public_url("https://user:password@example.com/private")


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


def test_private_profile_requires_explicit_update(tmp_path: Path) -> None:
    library = Library(tmp_path / "library.db")
    profile = library.update_profile(
        {
            "display_name": "Writer",
            "location": "United States",
            "skills": ["Cloud security", "Writing", "Cloud security"],
            "interests": ["AI infrastructure"],
            "suggestions": {"skills": ["Threat modeling"]},
        }
    )
    assert profile["skills"] == ["Cloud security", "Writing"]
    assert profile["suggestions"]["skills"] == ["Threat modeling"]
    # Suggestions remain separate until the owner deliberately updates skills.
    assert "Threat modeling" not in profile["skills"]


def test_profile_lists_preserve_owner_order_and_commas(tmp_path: Path) -> None:
    library = Library(tmp_path / "library.db")
    goals = [
        "Move income from $85,000 to $250,000+",
        "Publish a book and sell 100,000 copies",
        "Buy a house by December 2027",
    ]
    profile = library.update_profile({"goals": goals})
    assert profile["goals"] == goals


def test_profile_cv_path_is_available_to_server_but_not_required_for_older_databases(tmp_path: Path) -> None:
    database = tmp_path / "library.db"
    library = Library(database)
    cv = tmp_path / "imports" / "profile" / "private-cv.pdf"
    cv.parent.mkdir(parents=True)
    cv.write_bytes(b"private")
    profile = library.update_profile(
        {"cv_filename": "cv.pdf", "cv_path": str(cv), "cv_text": "Private extracted text"}
    )
    assert profile["cv_path"] == str(cv)
    assert profile["cv_text"] == "Private extracted text"
    assert Library(database).get_profile()["cv_filename"] == "cv.pdf"


def test_growth_sync_uses_goals_not_certification_inventory(tmp_path: Path) -> None:
    library = Library(tmp_path / "library.db")
    library.update_profile(
        {
            "goals": ["Move into cloud security by December 2026", "CCSP (ISC2) - In Progress"],
            "certifications": ["Terraform Associate - In Progress"],
            "suggestions": {"certifications": ["CCSP (ISC2) - In Progress", "AWS Security Specialty"]},
        }
    )
    items = library.sync_growth_from_profile()
    by_title = {item["title"]: item for item in items}
    assert by_title["CCSP (ISC2) - In Progress"]["status"] == "in_progress"
    assert "Terraform Associate - In Progress" not in by_title
    assert "AWS Security Specialty" not in by_title  # Unapproved, non-active suggestion stays out.
    assert by_title["Move into cloud security by December 2026"]["status"] == "active"


def test_growth_plan_preserves_completed_actions_and_aggregates_workspace_tasks(tmp_path: Path) -> None:
    library = Library(tmp_path / "library.db")
    library.update_profile({"goals": ["Publish the first book"]})
    item = library.sync_growth_from_profile()[0]
    library.replace_ai_growth_actions(
        [
            {
                "item_title": item["title"],
                "title": "Draft the outline",
                "details": "Create the first outline.",
                "priority": "high",
                "estimate_minutes": 45,
            }
        ]
    )
    action = library.list_growth_actions()[0]
    library.update_growth_action(action["id"], {"status": "done"})
    library.replace_ai_growth_actions(
        [{"item_title": item["title"], "title": "Draft the outline", "estimate_minutes": 45}]
    )
    project_id = library.ensure_project("Book", workspace_type="book")
    library.add_task(project_id, title="Review chapter one", estimate_minutes=30)
    overview = library.growth_overview()
    assert [action["status"] for action in overview["actions"]] == ["done"]
    assert overview["items"][0]["progress"] == 90
    assert overview["items"][0]["done_actions"] == 1
    assert overview["workspace_tasks"][0]["title"] == "Review chapter one"
    assert overview["metrics"]["open_actions"] == 1


def test_purpose_specific_workspace_cards_and_completion(tmp_path: Path) -> None:
    library = Library(tmp_path / "library.db")
    project_id = library.ensure_project("Community Program", workspace_type="impact")
    library.add_workspace_card(project_id, "outcomes", "Improved access", "Owner-authored outcome")
    library.replace_workspace_cards(
        project_id,
        [{"collection": "indicators", "title": "Participation", "content": "Measure attendance"}],
    )
    library.replace_workspace_cards(
        project_id,
        [{"collection": "risks", "title": "Access barrier", "content": "Track exclusions"}],
    )
    cards = library.list_workspace_cards(project_id)
    assert any(card["title"] == "Improved access" for card in cards)
    assert not any(card["title"] == "Participation" for card in cards)
    assert any(card["title"] == "Access barrier" for card in cards)

    task = library.add_task(project_id, title="Publish outcome report")
    library.update_task(project_id, task["id"], {"status": "done"})
    completed = library.complete_workspace(project_id, {"outcome_summary": "Report published"})
    assert completed["project"]["status"] == "completed"
    assert completed["completion"]["review"]["outcome_summary"] == "Report published"
    assert library.reopen_workspace(project_id)["project"]["status"] == "active"


def test_profile_opportunity_refresh_preserves_saved_ideas(tmp_path: Path) -> None:
    library = Library(tmp_path / "library.db")
    note_id = library.upsert_transcript(
        source_name="idea.txt",
        audio_path=tmp_path / "idea.txt",
        transcript_path=tmp_path / "idea-transcript.txt",
        transcript="Create a security workshop.",
    )
    library.replace_profile_opportunities(
        [
            {
                "kind": "business",
                "title": "Security workshop",
                "description": "A practical workshop",
                "rationale": "Supported by experience",
                "score": 80,
                "evidence": [note_id],
            }
        ]
    )
    opportunity = library.list_opportunities()[0]
    library.update_opportunity(opportunity["id"], status="saved")
    library.replace_profile_opportunities(
        [
            {
                "kind": "learning",
                "title": "Research facilitation",
                "description": "Build facilitation skill",
                "rationale": "Closes a gap",
                "evidence": [note_id],
            }
        ]
    )
    assert library.list_opportunities("saved")[0]["title"] == "Security workshop"
    assert library.list_opportunities("new")[0]["title"] == "Research facilitation"


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
