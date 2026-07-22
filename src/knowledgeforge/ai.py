"""Provider-neutral AI analysis, manuscript integration, and library chat."""

from __future__ import annotations

import json
import logging
import os
import urllib.request
import base64
import mimetypes
from datetime import date
from pathlib import Path
from typing import Literal, TypeVar

from pydantic import BaseModel, Field

from .config import Settings
from .library import Library


class Character(BaseModel):
    name: str
    role: str = ""
    traits: list[str] = Field(default_factory=list)
    relationships: list[str] = Field(default_factory=list)


class Scene(BaseModel):
    title: str
    setting: str = ""
    participants: list[str] = Field(default_factory=list)
    synopsis: str
    conflict: str = ""
    chronology_hint: str = ""


class AssignedTask(BaseModel):
    task: str
    assignee: str = ""
    deadline: str = ""


class Opportunity(BaseModel):
    kind: Literal["book", "business", "project"]
    title: str
    description: str
    rationale: str


class NoteAnalysis(BaseModel):
    title: str
    summary: str
    content_type: Literal["author", "personal", "business", "meeting", "journal"]
    project_name: str
    workspace_type: Literal["book", "business", "project", "general"]
    idea_domains: list[Literal["book", "business", "project", "personal", "other"]]
    tags: list[str]
    characters: list[Character]
    scenes: list[Scene]
    themes: list[str]
    story_ideas: list[str]
    key_ideas: list[str]
    decisions: list[str]
    assigned_tasks: list[AssignedTask]
    deadlines: list[str]
    risks: list[str]
    open_questions: list[str]
    follow_up_items: list[str]
    opportunities: list[Opportunity]


class ManuscriptSection(BaseModel):
    title: str
    content: str
    source_note_ids: list[int] = Field(default_factory=list)


class ManuscriptDraft(BaseModel):
    change_summary: str
    sections: list[ManuscriptSection]


class PlanTask(BaseModel):
    title: str
    details: str = ""
    priority: Literal["critical", "high", "medium", "low"] = "medium"
    estimate_minutes: int = Field(default=30, ge=5, le=10080)
    target_date: str = ""
    dependencies: list[str] = Field(default_factory=list)


class ExecutionPlan(BaseModel):
    planning_note: str
    tasks: list[PlanTask]


Schema = TypeVar("Schema", bound=BaseModel)


class AIService:
    """Keep provider details behind one boundary so workflows remain portable."""

    def __init__(self, settings: Settings, library: Library) -> None:
        self.settings, self.library = settings, library
        self._openai_client = None
        self._anthropic_client = None
        self._compatible_clients: dict[str, object] = {}

    @property
    def provider(self) -> str:
        return self.library.get_setting("ai_provider", self.settings.ai_provider)

    @property
    def model(self) -> str:
        return self.library.get_setting("ai_model", self.settings.ai_model)

    @property
    def enabled(self) -> bool:
        config = self._provider_config()
        return config.get("adapter") == "ollama" or bool(os.getenv(config.get("api_key_env", "")))

    def _catalog(self) -> list[dict]:
        try:
            return list(json.loads(self.settings.provider_catalog.read_text(encoding="utf-8"))["providers"])
        except (OSError, ValueError, KeyError, TypeError):
            fallback = Path(__file__).with_name("ai-providers.json")
            return list(json.loads(fallback.read_text(encoding="utf-8"))["providers"])

    def _provider_config(self) -> dict:
        return next((item for item in self._catalog() if item.get("id") == self.provider), {})

    def options(self) -> dict:
        """Expose catalog metadata but never environment-variable values."""
        providers = []
        for item in self._catalog():
            provider = dict(item)
            provider.pop("api_key_env", None)
            provider.pop("base_url_env", None)
            if item["id"] == "ollama":
                models, configured = self._ollama_models()
                provider["models"] = models or item.get("models", [])
            else:
                configured = bool(os.getenv(item.get("api_key_env", "")))
            provider["configured"] = configured
            providers.append(provider)
        return {"selected": {"provider": self.provider, "model": self.model}, "providers": providers}

    def _ollama_models(self) -> tuple[list[str], bool]:
        try:
            with urllib.request.urlopen(f"{self.settings.ollama_url.rstrip('/')}/api/tags", timeout=2) as response:
                payload = json.loads(response.read())
                return [str(item["name"]) for item in payload.get("models", [])], True
        except (OSError, ValueError, KeyError):
            return [], False

    def _ollama_chat(self, messages: list[dict[str, str]], schema: dict | None = None) -> str:
        payload: dict = {"model": self.model, "messages": messages, "stream": False}
        if schema:
            payload.update({"format": schema, "options": {"temperature": 0}})
        request = urllib.request.Request(
            f"{self.settings.ollama_url.rstrip('/')}/api/chat",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=600) as response:
            return str(json.loads(response.read())["message"]["content"])

    def _structured(self, messages: list[dict[str, str]], schema: type[Schema]) -> Schema:
        if not self.enabled:
            raise RuntimeError(
                "The selected AI provider is not configured. Add its API key or choose another provider."
            )
        adapter = self._provider_config().get("adapter", self.provider)
        if adapter == "ollama":
            return schema.model_validate_json(self._ollama_chat(messages, schema.model_json_schema()))
        if adapter == "anthropic":
            if self._anthropic_client is None:
                from anthropic import Anthropic

                self._anthropic_client = Anthropic(api_key=self.settings.anthropic_api_key)
            response = self._anthropic_client.messages.create(
                model=self.model,
                max_tokens=16000,
                system=messages[0]["content"],
                messages=messages[1:],
                tools=[
                    {
                        "name": "return_result",
                        "description": "Return the required structured result.",
                        "input_schema": schema.model_json_schema(),
                    }
                ],
                tool_choice={"type": "tool", "name": "return_result"},
            )
            block = next(block for block in response.content if block.type == "tool_use")
            return schema.model_validate(block.input)
        if adapter == "openai_compatible":
            config = self._provider_config()
            client = self._compatible_clients.get(self.provider)
            if client is None:
                from openai import OpenAI

                client = OpenAI(api_key=os.getenv(config["api_key_env"]), base_url=config["base_url"])
                self._compatible_clients[self.provider] = client
            schema_prompt = messages + [
                {
                    "role": "user",
                    "content": "Return only JSON matching this schema exactly:\n"
                    + json.dumps(schema.model_json_schema()),
                }
            ]
            response = client.chat.completions.create(
                model=self.model, messages=schema_prompt, response_format={"type": "json_object"}
            )
            return schema.model_validate_json(response.choices[0].message.content)
        if self._openai_client is None:
            from openai import OpenAI

            self._openai_client = OpenAI(api_key=self.settings.openai_api_key)
        response = self._openai_client.responses.parse(model=self.model, input=messages, text_format=schema)
        if response.output_parsed is None:
            raise RuntimeError("AI returned no structured result")
        return response.output_parsed

    def _text(self, system: str, user: str) -> str:
        if not self.enabled:
            raise RuntimeError(
                "The selected AI provider is not configured. Add its API key or choose another provider."
            )
        adapter = self._provider_config().get("adapter", self.provider)
        if adapter == "ollama":
            return self._ollama_chat([{"role": "system", "content": system}, {"role": "user", "content": user}])
        if adapter == "anthropic":
            if self._anthropic_client is None:
                from anthropic import Anthropic

                self._anthropic_client = Anthropic(api_key=self.settings.anthropic_api_key)
            response = self._anthropic_client.messages.create(
                model=self.model, max_tokens=16000, system=system, messages=[{"role": "user", "content": user}]
            )
            return "".join(block.text for block in response.content if block.type == "text")
        if adapter == "openai_compatible":
            config = self._provider_config()
            client = self._compatible_clients.get(self.provider)
            if client is None:
                from openai import OpenAI

                client = OpenAI(api_key=os.getenv(config["api_key_env"]), base_url=config["base_url"])
                self._compatible_clients[self.provider] = client
            response = client.chat.completions.create(
                model=self.model, messages=[{"role": "system", "content": system}, {"role": "user", "content": user}]
            )
            return str(response.choices[0].message.content)
        if self._openai_client is None:
            from openai import OpenAI

            self._openai_client = OpenAI(api_key=self.settings.openai_api_key)
        return self._openai_client.responses.create(model=self.model, instructions=system, input=user).output_text

    def describe_image(self, path: Path) -> str:
        """Turn an imported image of notes, diagrams, or book material into source text."""
        if not self.enabled:
            raise RuntimeError("Configure an AI provider before importing images.")
        encoded = base64.b64encode(path.read_bytes()).decode()
        mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        prompt = (
            "Extract all useful written content and ideas from this image. Describe diagrams and context faithfully."
        )
        adapter = self._provider_config().get("adapter", self.provider)
        if adapter == "ollama":
            payload = {
                "model": self.model,
                "stream": False,
                "messages": [{"role": "user", "content": prompt, "images": [encoded]}],
            }
            request = urllib.request.Request(
                f"{self.settings.ollama_url.rstrip('/')}/api/chat",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=600) as response:
                return str(json.loads(response.read())["message"]["content"])
        if adapter == "anthropic":
            if self._anthropic_client is None:
                from anthropic import Anthropic

                self._anthropic_client = Anthropic(api_key=self.settings.anthropic_api_key)
            response = self._anthropic_client.messages.create(
                model=self.model,
                max_tokens=8000,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": mime, "data": encoded}},
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
            )
            return "".join(block.text for block in response.content if block.type == "text")
        if adapter == "openai_compatible":
            config = self._provider_config()
            from openai import OpenAI

            client = OpenAI(api_key=os.getenv(config["api_key_env"]), base_url=config["base_url"])
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}},
                        ],
                    }
                ],
            )
            return str(response.choices[0].message.content)
        if self._openai_client is None:
            from openai import OpenAI

            self._openai_client = OpenAI(api_key=self.settings.openai_api_key)
        response = self._openai_client.responses.create(
            model=self.model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": f"data:{mime};base64,{encoded}"},
                    ],
                }
            ],
        )
        return response.output_text

    def analyze(self, note_id: int) -> dict:
        note = self.library.get_note(note_id)
        if not note:
            raise KeyError(note_id)
        project_rows = self.library.list_projects()
        projects = [p["name"] for p in project_rows]
        messages = [
            {
                "role": "system",
                "content": (
                    "Organize dictated knowledge. Extract only supported information and use empty arrays when absent. "
                    "Choose project_name exactly from the supplied projects; never invent facts."
                ),
            },
            {
                "role": "user",
                "content": f"Workspaces: {[(p['name'], p['workspace_type']) for p in project_rows]}\nDefault book: {self.settings.default_project}\n\n{note['transcript']}",
            },
        ]
        result = self._structured(messages, NoteAnalysis).model_dump()
        if result["project_name"] not in projects:
            result["project_name"] = self.settings.default_project
        project_id = self.library.ensure_project(result["project_name"], workspace_type=result["workspace_type"])
        self.library.save_analysis(note_id, result, project_id)
        return self.library.get_note(note_id) or result

    def reorganize_book(self, project_id: int, *, feedback: str = "", trigger_note_id: int | None = None) -> dict:
        book = self.library.get_book(project_id)
        notes = self.library.context_notes(project_id, limit=40)
        manuscript = "\n\n".join(f"## {s['title']}\n{s['content']}" for s in book["sections"])
        evidence = "\n\n".join(f"[Note {n['id']}] {n['summary']}\n{n['transcript'][:5000]}" for n in notes)
        instructions = book["instructions"] or "Preserve the author's voice and do not invent unsupported canon."
        prompt = (
            f"AUTHOR INSTRUCTIONS:\n{instructions}\n\nLATEST FEEDBACK:\n{feedback}\n\nCURRENT MANUSCRIPT:\n"
            f"{manuscript[:60000]}\n\nSOURCE NOTES:\n{evidence[:100000]}"
        )
        draft = self._structured(
            [
                {
                    "role": "system",
                    "content": (
                        "Maintain the workspace's working document: manuscript for a book, plan for a business, or project brief. "
                        "Integrate relevant source-note material into logical sections, preserve useful existing content, cite note IDs, "
                        "Do not invent facts; keep uncertain ideas clearly tentative."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            ManuscriptDraft,
        )
        result = draft.model_dump()
        self.library.replace_book(
            project_id, result["sections"], reason=result["change_summary"] or feedback, trigger_note_id=trigger_note_id
        )
        # Content integration and execution planning are one workflow. Library
        # preserves completed and owner-authored tasks during this refresh.
        try:
            self.refresh_plan(project_id, reason=feedback or "New source material integrated")
        except Exception:
            # A planning-provider failure must not roll back a successfully
            # integrated manuscript or project document.
            logging.exception("Automatic execution-plan refresh failed for project %s", project_id)
        return self.library.get_book(project_id)

    def refresh_plan(self, project_id: int, *, reason: str = "Workspace updated") -> dict:
        """Create an ordered, time-estimated plan from current workspace evidence."""
        book = self.library.get_book(project_id)
        notes = self.library.context_notes(project_id, limit=50)
        current_tasks = self.library.list_tasks(project_id)
        workspace = "\n\n".join(f"## {s['title']}\n{s['content']}" for s in book["sections"])
        evidence = "\n\n".join(f"[Note {n['id']}] {n['summary']}\n{n['transcript'][:4000]}" for n in notes)
        task_state = json.dumps(
            [
                {k: task[k] for k in ("title", "status", "priority", "estimate_minutes", "target_date", "source")}
                for task in current_tasks
            ],
            indent=2,
        )
        plan = self._structured(
            [
                {
                    "role": "system",
                    "content": "Act as a cautious execution planner. Convert supported workspace material into concrete, ordered tasks. Prioritize outcomes and dependencies, give realistic effort estimates in minutes, and use ISO YYYY-MM-DD target dates only when evidence supports a deadline or a useful proposed schedule. Never invent commitments. Keep tasks small enough to complete and omit vague busywork. Existing completed and manual tasks are authoritative.",
                },
                {
                    "role": "user",
                    "content": f"TODAY: {date.today().isoformat()}\nREPLAN REASON: {reason}\nWORKSPACE: {book['project']['name']} ({book['project']['workspace_type']})\nOWNER DIRECTION:\n{book['instructions']}\n\nCURRENT WORK:\n{workspace[:60000]}\n\nSOURCE EVIDENCE:\n{evidence[:90000]}\n\nCURRENT TASK STATE:\n{task_state}",
                },
            ],
            ExecutionPlan,
        ).model_dump()
        self.library.replace_ai_tasks(project_id, plan["tasks"])
        return {"planning_note": plan["planning_note"], "tasks": self.library.list_tasks(project_id)}

    def answer(self, question: str, project_id: int | None = None, selected_ids: list[int] | None = None) -> dict:
        notes = (
            [note for i in selected_ids if (note := self.library.get_note(i))]
            if selected_ids
            else self.library.context_notes(project_id, limit=30)
        )
        context = "\n\n".join(
            f"[Note {n['id']}: {n['title']}]\n{n['summary']}\n{n['transcript'][:8000]}" for n in notes
        )
        answer = self._text(
            "Answer only from the supplied private notes. Cite [Note ID], identify uncertainty and contradictions.",
            f"QUESTION:\n{question}\n\nPRIVATE NOTES:\n{context or 'No notes.'}",
        )
        return {"answer": answer, "sources": [{"id": n["id"], "title": n["title"]} for n in notes]}
