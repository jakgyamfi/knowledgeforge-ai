"""Provider-neutral AI analysis, manuscript integration, and library chat."""

from __future__ import annotations

import base64
import ipaddress
import json
import logging
import mimetypes
import re
import socket
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, Field

from .config import Settings
from .library import Library
from .logging_config import audit_egress
from .secrets import ProviderSecrets

logger = logging.getLogger(__name__)


class _ReadableHTML(HTMLParser):
    """Extract bounded visible text from public research pages."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self.hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data: str) -> None:
        if not self.hidden and (text := " ".join(data.split())):
            self.parts.append(text)


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
    kind: Literal["career", "business", "book", "project", "learning", "collaboration", "nonprofit", "other"]
    title: str
    description: str
    rationale: str
    score: int = Field(default=50, ge=0, le=100)
    confidence: Literal["low", "medium", "high"] = "medium"
    evidence: list[int] = Field(default_factory=list)
    missing_capabilities: list[str] = Field(default_factory=list)
    effort: str = ""
    expected_value: str = ""
    risks: list[str] = Field(default_factory=list)
    next_step: str = ""


class NoteAnalysis(BaseModel):
    title: str
    summary: str
    content_type: Literal["author", "personal", "business", "meeting", "journal"]
    project_name: str
    workspace_type: Literal["book", "business", "impact", "project", "general"]
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


class GrowthActionDraft(PlanTask):
    item_title: str = ""
    project_name: str = ""


class GrowthPlan(BaseModel):
    planning_note: str
    risks: list[str] = Field(default_factory=list)
    actions: list[GrowthActionDraft]


class ProfileSuggestions(BaseModel):
    headline: str = ""
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    rationale: list[str] = Field(default_factory=list)


class OpportunityBatch(BaseModel):
    opportunities: list[Opportunity]


class WorkspaceCardDraft(BaseModel):
    collection: str
    title: str
    content: str = ""
    metadata: dict = Field(default_factory=dict)


class WorkspaceBlueprint(BaseModel):
    direction: str
    cards: list[WorkspaceCardDraft]
    initial_tasks: list[PlanTask] = Field(default_factory=list)


class CompletionReview(BaseModel):
    outcome_summary: str
    deliverables: list[str] = Field(default_factory=list)
    lessons: list[str] = Field(default_factory=list)
    unresolved_items: list[str] = Field(default_factory=list)
    demonstrated_skills: list[str] = Field(default_factory=list)
    follow_up_opportunities: list[str] = Field(default_factory=list)
    profile_suggestions: ProfileSuggestions = Field(default_factory=ProfileSuggestions)


class ValidationFinding(BaseModel):
    claim: str
    assessment: Literal["supports", "challenges", "uncertain"]
    source_urls: list[str] = Field(default_factory=list)


class ValidationReport(BaseModel):
    verdict: Literal["promising", "needs-evidence", "weak", "not-currently-viable"]
    summary: str
    findings: list[ValidationFinding]
    assumptions_to_test: list[str] = Field(default_factory=list)
    recommended_experiments: list[str] = Field(default_factory=list)
    checked_at: str


class WorkspaceResearch(BaseModel):
    title: str
    executive_summary: str
    findings: list[ValidationFinding] = Field(default_factory=list)
    statistics: list[str] = Field(default_factory=list)
    ideas: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    checked_at: str


class WorkspaceAcceleration(BaseModel):
    """Purpose-specific structure and execution derived from a workspace."""

    executive_summary: str
    cards: list[WorkspaceCardDraft] = Field(default_factory=list)
    tasks: list[PlanTask] = Field(default_factory=list)
    success_measures: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)


Schema = TypeVar("Schema", bound=BaseModel)


class AIService:
    """Keep provider details behind one boundary so workflows remain portable."""

    def __init__(self, settings: Settings, library: Library) -> None:
        self.settings, self.library = settings, library
        self.secrets = ProviderSecrets()
        self._openai_client = None
        self._anthropic_client = None
        self._meta_client = None
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
        return config.get("adapter") == "ollama" or bool(self.secrets.get(config.get("api_key_env", "")))

    def _catalog(self) -> list[dict]:
        try:
            return list(json.loads(self.settings.provider_catalog.read_text(encoding="utf-8"))["providers"])
        except (OSError, ValueError, KeyError, TypeError):
            fallback = Path(__file__).with_name("ai-providers.json")
            return list(json.loads(fallback.read_text(encoding="utf-8"))["providers"])

    def _provider_config(self) -> dict:
        return next((item for item in self._catalog() if item.get("id") == self.provider), {})

    def _audit_llm_request(self, operation: str) -> None:
        """Record routing metadata only; never record prompts or responses."""
        config = self._provider_config()
        endpoint = self.settings.ollama_url if config.get("adapter") == "ollama" else config.get("base_url", "")
        parsed = urllib.parse.urlparse(endpoint)
        audit_egress(
            "llm_request_started",
            operation=operation,
            provider=self.provider,
            model=self.model,
            host=parsed.hostname or self.provider,
            port=parsed.port or (443 if parsed.scheme == "https" else 11434 if self.provider == "ollama" else None),
            tls=parsed.scheme == "https",
            local=self.provider == "ollama",
        )

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
                configured = bool(self.secrets.get(item.get("api_key_env", "")))
                if configured and item.get("discover_models"):
                    provider["models"] = self._discover_models(item) or item.get("models", [])
            provider["configured"] = configured
            providers.append(provider)
        return {"selected": {"provider": self.provider, "model": self.model}, "providers": providers}

    def _discover_models(self, config: dict) -> list[str]:
        """Query a provider's model endpoint, falling back silently to reviewed IDs."""
        try:
            adapter = config.get("adapter")
            key = self.secrets.get(config.get("api_key_env", ""))
            if adapter in {"openai", "openai_compatible"}:
                from openai import OpenAI

                kwargs = {"api_key": key, "timeout": 4.0}
                if adapter == "openai_compatible":
                    kwargs["base_url"] = config["base_url"]
                entries = OpenAI(**kwargs).models.list().data
            elif adapter == "anthropic":
                from anthropic import Anthropic

                entries = Anthropic(api_key=key, timeout=4.0).models.list(limit=100).data
            elif adapter == "meta_llama":
                from llama_api_client import LlamaAPIClient

                response = LlamaAPIClient(api_key=key, timeout=4.0).models.list()
                entries = getattr(response, "data", response)
            else:
                return []
            ids = [str(getattr(entry, "id", "")) for entry in entries]
            reviewed = config.get("models", [])
            prefixes = {model.split("-", 1)[0].lower() for model in reviewed}
            return sorted({model for model in ids if model and model.split("-", 1)[0].lower() in prefixes})
        except Exception:
            return []

    def secret_status(self) -> dict:
        """Expose credential presence and backend without exposing values."""
        providers = []
        for item in self._catalog():
            if name := item.get("api_key_env"):
                providers.append(
                    {
                        "id": item["id"],
                        "label": item["label"],
                        "configured": bool(self.secrets.get(name)),
                        "source": self.secrets.source(name),
                    }
                )
        return {"backend": self.secrets.backend, "writable": self.secrets.writable, "providers": providers}

    def set_secret(self, provider_id: str, value: str) -> dict:
        item = next((entry for entry in self._catalog() if entry.get("id") == provider_id), None)
        if not item or not item.get("api_key_env"):
            raise KeyError(provider_id)
        self.secrets.set(item["api_key_env"], value)
        self._openai_client = None
        self._anthropic_client = None
        self._compatible_clients.pop(provider_id, None)
        return self.secret_status()

    def delete_secret(self, provider_id: str) -> dict:
        item = next((entry for entry in self._catalog() if entry.get("id") == provider_id), None)
        if not item or not item.get("api_key_env"):
            raise KeyError(provider_id)
        self.secrets.delete(item["api_key_env"])
        self._openai_client = None
        self._anthropic_client = None
        self._compatible_clients.pop(provider_id, None)
        return self.secret_status()

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

    def _meta_chat(self, messages: list[dict[str, str]]) -> str:
        """Call Meta's first-party Llama API and normalize its content shape."""
        if self._meta_client is None:
            from llama_api_client import LlamaAPIClient

            self._meta_client = LlamaAPIClient(api_key=self.secrets.get("LLAMA_API_KEY"))
        response = self._meta_client.chat.completions.create(model=self.model, messages=messages)
        content = getattr(response.completion_message, "content", "")
        if isinstance(content, str):
            return content
        return "".join(str(getattr(item, "text", "")) for item in content)

    def _structured(self, messages: list[dict[str, str]], schema: type[Schema]) -> Schema:
        if not self.enabled:
            raise RuntimeError(
                "The selected AI provider is not configured. Add its API key or choose another provider."
            )
        adapter = self._provider_config().get("adapter", self.provider)
        self._audit_llm_request(f"structured:{schema.__name__}")
        if adapter == "ollama":
            return schema.model_validate_json(self._ollama_chat(messages, schema.model_json_schema()))
        if adapter == "meta_llama":
            schema_prompt = messages + [
                {
                    "role": "user",
                    "content": "Return only JSON matching this schema exactly:\n"
                    + json.dumps(schema.model_json_schema()),
                }
            ]
            return self._validate_structured_content(self._meta_chat(schema_prompt), schema)
        if adapter == "anthropic":
            if self._anthropic_client is None:
                from anthropic import Anthropic

                self._anthropic_client = Anthropic(api_key=self.secrets.get("ANTHROPIC_API_KEY"))
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

                client = OpenAI(api_key=self.secrets.get(config["api_key_env"]), base_url=config["base_url"])
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
            return self._validate_structured_content(response.choices[0].message.content, schema)
        if self._openai_client is None:
            from openai import OpenAI

            self._openai_client = OpenAI(api_key=self.secrets.get("OPENAI_API_KEY"))
        response = self._openai_client.responses.parse(model=self.model, input=messages, text_format=schema)
        if response.output_parsed is None:
            raise RuntimeError("AI returned no structured result")
        return response.output_parsed

    @staticmethod
    def _validate_structured_content(content: str | None, schema: type[Schema]) -> Schema:
        """Validate provider JSON, including common compatibility wrappers.

        Some OpenAI-compatible providers return the requested object directly.
        Others, including some GLM endpoints, wrap the serialized object in an
        ``answer`` property. Normalizing that transport difference here keeps
        the rest of KnowledgeForge provider-neutral.
        """
        if not content:
            raise RuntimeError("AI returned no structured result")
        candidate = content.strip()
        if candidate.startswith("```"):
            candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", candidate, flags=re.IGNORECASE)
        parsed = AIService._parse_provider_json(candidate)
        if isinstance(parsed, dict) and isinstance(parsed.get("answer"), str):
            nested = parsed["answer"].strip()
            if nested.startswith("```"):
                nested = re.sub(r"^```(?:json)?\s*|\s*```$", "", nested, flags=re.IGNORECASE)
            parsed = AIService._parse_provider_json(nested)
        return schema.model_validate(parsed)

    @staticmethod
    def _parse_provider_json(candidate: str) -> Any:
        """Parse provider JSON with one conservative compatibility repair.

        Language models occasionally place Windows paths or Markdown escapes
        in JSON strings without escaping the backslash. The response is still
        unambiguous, but Python's strict JSON parser rejects it. Retry only
        after escaping backslashes that are not valid JSON escape sequences;
        schema validation still protects every downstream field.
        """
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as original:
            repaired = re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", candidate)
            if repaired == candidate:
                raise original
            return json.loads(repaired, strict=False)

    def _text(self, system: str, user: str) -> str:
        if not self.enabled:
            raise RuntimeError(
                "The selected AI provider is not configured. Add its API key or choose another provider."
            )
        adapter = self._provider_config().get("adapter", self.provider)
        self._audit_llm_request("text")
        if adapter == "ollama":
            return self._ollama_chat([{"role": "system", "content": system}, {"role": "user", "content": user}])
        if adapter == "meta_llama":
            return self._meta_chat([{"role": "system", "content": system}, {"role": "user", "content": user}])
        if adapter == "anthropic":
            if self._anthropic_client is None:
                from anthropic import Anthropic

                self._anthropic_client = Anthropic(api_key=self.secrets.get("ANTHROPIC_API_KEY"))
            response = self._anthropic_client.messages.create(
                model=self.model, max_tokens=16000, system=system, messages=[{"role": "user", "content": user}]
            )
            return "".join(block.text for block in response.content if block.type == "text")
        if adapter == "openai_compatible":
            config = self._provider_config()
            client = self._compatible_clients.get(self.provider)
            if client is None:
                from openai import OpenAI

                client = OpenAI(api_key=self.secrets.get(config["api_key_env"]), base_url=config["base_url"])
                self._compatible_clients[self.provider] = client
            response = client.chat.completions.create(
                model=self.model, messages=[{"role": "system", "content": system}, {"role": "user", "content": user}]
            )
            return str(response.choices[0].message.content)
        if self._openai_client is None:
            from openai import OpenAI

            self._openai_client = OpenAI(api_key=self.secrets.get("OPENAI_API_KEY"))
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
        if adapter == "meta_llama":
            raise RuntimeError(
                "Image analysis is not yet enabled for the Meta Llama API adapter; import text or audio."
            )
        if adapter == "anthropic":
            if self._anthropic_client is None:
                from anthropic import Anthropic

                self._anthropic_client = Anthropic(api_key=self.secrets.get("ANTHROPIC_API_KEY"))
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

            client = OpenAI(api_key=self.secrets.get(config["api_key_env"]), base_url=config["base_url"])
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

            self._openai_client = OpenAI(api_key=self.secrets.get("OPENAI_API_KEY"))
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
        profile = self.library.get_profile()
        messages = [
            {
                "role": "system",
                "content": (
                    "Organize dictated knowledge. Extract only supported information and use empty arrays when absent. "
                    "Choose project_name exactly from the supplied projects; never invent facts. Discover worthwhile "
                    "career, venture, book, project, learning, collaboration, and nonprofit opportunities without forcing "
                    "the note into a category. Score conservatively and cite supporting note IDs."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"OWNER PROFILE: {json.dumps(profile, default=str)[:30000]}\n"
                    f"Workspaces: {[(p['name'], p['workspace_type']) for p in project_rows]}\n"
                    f"Default book: {self.settings.default_project}\nSOURCE NOTE ID: {note_id}\n\n{note['transcript']}"
                ),
            },
        ]
        result = self._structured(messages, NoteAnalysis).model_dump()
        if result["project_name"] not in projects:
            result["project_name"] = self.settings.default_project
        project_id = self.library.ensure_project(result["project_name"], workspace_type=result["workspace_type"])
        self.library.save_analysis(note_id, result, project_id)
        return self.library.get_note(note_id) or result

    def suggest_profile_updates(self) -> dict:
        """Infer profile additions without applying them; the owner must approve."""
        profile = self.library.get_profile()
        notes = self.library.context_notes(limit=50)
        evidence = "\n\n".join(
            f"[Note {note['id']}] {note['title']}\n{note['summary']}\n{note['transcript'][:3000]}" for note in notes
        )
        suggestions = self._structured(
            [
                {
                    "role": "system",
                    "content": (
                        "Suggest updates to a private opportunity profile. Treat explicit profile fields as authoritative. "
                        "Infer only capabilities supported by CV or source evidence, explain each suggestion, and never "
                        "silently overwrite the owner profile."
                    ),
                },
                {
                    "role": "user",
                    "content": f"CURRENT PROFILE:\n{json.dumps(profile, default=str)[:40000]}\n\nEVIDENCE:\n{evidence[:100000]}",
                },
            ],
            ProfileSuggestions,
        ).model_dump()
        self.library.update_profile({"suggestions": suggestions})
        return suggestions

    def refresh_opportunities(self) -> list[dict]:
        """Generate a profile-aware feed across the private source library."""
        profile = self.library.get_profile()
        notes = self.library.context_notes(limit=80)
        evidence = "\n\n".join(
            f"[Note {note['id']}] {note['title']}\n{note['summary']}\n{note['transcript'][:3500]}" for note in notes
        )
        batch = self._structured(
            [
                {
                    "role": "system",
                    "content": (
                        "Act as a cautious opportunity strategist. Find worthwhile opportunities supported by the owner "
                        "profile and supplied private evidence. Consider careers, businesses, services, books, products, "
                        "projects, learning, certifications, collaborations, speaking, grants, communities, and nonprofit "
                        "impact. Do not force categories or invent demand. Rank by fit, evidence, feasibility, impact, "
                        "timing, risk, and effort. Evidence must contain supplied note IDs."
                    ),
                },
                {
                    "role": "user",
                    "content": f"OWNER PROFILE:\n{json.dumps(profile, default=str)[:50000]}\n\nLIBRARY:\n{evidence[:140000]}",
                },
            ],
            OpportunityBatch,
        ).model_dump()
        self.library.replace_profile_opportunities(batch["opportunities"])
        return self.library.list_opportunities()

    def initialize_workspace(
        self, project_id: int, opportunity: dict | None = None, *, include_initial_tasks: bool = True
    ) -> dict:
        """Create the appropriate studio blueprint from one shared workspace engine."""
        workspace = self.library.workspace_snapshot(project_id)
        project = workspace["project"]
        profile = self.library.get_profile()
        type_guidance = {
            "book": (
                "Create a Book Studio: outline/chapters, scene board, characters, locations, themes, continuity, "
                "research, unresolved questions, writing goals, and publication considerations. Preserve uncertainty."
            ),
            "business": (
                "Create a Venture Studio: customer/problem, existing alternatives, value proposition, solution, "
                "channels, revenue, costs, key metrics, unfair advantage, assumptions, experiments, and evidence."
            ),
            "impact": (
                "Create an Impact Studio: need, beneficiaries, inputs, activities, outputs, outcomes, impact, indicators, "
                "partners, assumptions, risks, safeguards, and sustainability."
            ),
        }.get(project["workspace_type"], "Create a practical project studio with goals, evidence, milestones, and risks.")
        blueprint = self._structured(
            [
                {
                    "role": "system",
                    "content": (
                        f"{type_guidance} Return concise cards. Distinguish evidence from hypotheses. "
                        "Do not invent commitments, facts, beneficiaries, customers, or story canon."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"PROFILE:\n{json.dumps(profile, default=str)[:30000]}\n"
                        f"PROJECT:\n{json.dumps(project, default=str)}\n"
                        f"OPPORTUNITY:\n{json.dumps(opportunity or {}, default=str)}\n"
                        f"CURRENT WORKSPACE:\n{json.dumps(workspace, default=str)[:100000]}"
                    ),
                },
            ],
            WorkspaceBlueprint,
        ).model_dump()
        self.library.save_book_instructions(project_id, blueprint["direction"])
        self.library.replace_workspace_cards(project_id, blueprint["cards"])
        if include_initial_tasks and blueprint["initial_tasks"]:
            self.library.replace_ai_tasks(project_id, blueprint["initial_tasks"])
        return self.library.workspace_snapshot(project_id)

    @staticmethod
    def _web_search(query: str, limit: int = 6) -> list[dict[str, str]]:
        """Use Bing's public RSS result format; the query contains no private library text."""
        url = "https://www.bing.com/search?format=rss&q=" + urllib.parse.quote_plus(query)
        request = urllib.request.Request(url, headers={"User-Agent": "KnowledgeForge/0.8"})
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = response.read()
            audit_egress(
                "public_search", host="www.bing.com", port=443, tls=True, status="success",
                elapsed_ms=round((time.monotonic() - started) * 1000), response_bytes=len(payload),
            )
            root = ET.fromstring(payload)
        except Exception as exc:
            audit_egress(
                "public_search", host="www.bing.com", port=443, tls=True, status="failed",
                error_type=type(exc).__name__, elapsed_ms=round((time.monotonic() - started) * 1000),
            )
            raise
        results = []
        for item in root.findall(".//item")[:limit]:
            results.append(
                {
                    "title": item.findtext("title", ""),
                    "url": item.findtext("link", ""),
                    "snippet": item.findtext("description", ""),
                }
            )
        return results

    @staticmethod
    def _public_url(url: str) -> bool:
        """Reject local, credentialed, and private-network research targets."""
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            return False
        try:
            addresses = {
                ipaddress.ip_address(item[4][0])
                for item in socket.getaddrinfo(
                    parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM
                )
            }
        except (OSError, ValueError):
            return False
        return bool(addresses) and all(
            address.is_global and not address.is_private and not address.is_loopback and not address.is_link_local
            for address in addresses
        )

    @classmethod
    def _fetch_public_page(cls, url: str) -> str:
        """Fetch a bounded public HTML page for evidence review."""
        if not cls._public_url(url):
            return ""
        request = urllib.request.Request(url, headers={"User-Agent": "KnowledgeForge/0.10 research"})
        parsed = urllib.parse.urlparse(url)
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=12) as response:
                final_url = response.geturl()
                if not cls._public_url(final_url):
                    return ""
                content_type = response.headers.get_content_type()
                if content_type not in {"text/html", "text/plain"}:
                    return ""
                payload = response.read(600_000)
                charset = response.headers.get_content_charset() or "utf-8"
            audit_egress(
                "public_research_fetch", host=parsed.hostname, port=parsed.port or 443, tls=True,
                status="success", elapsed_ms=round((time.monotonic() - started) * 1000),
                response_bytes=len(payload),
            )
        except Exception as exc:
            audit_egress(
                "public_research_fetch", host=parsed.hostname, port=parsed.port or 443, tls=True,
                status="failed", error_type=type(exc).__name__,
                elapsed_ms=round((time.monotonic() - started) * 1000),
            )
            raise
        text = payload.decode(charset, errors="replace")
        if content_type == "text/plain":
            return " ".join(text.split())[:20_000]
        parser = _ReadableHTML()
        parser.feed(text)
        return " ".join(parser.parts)[:20_000]

    def validate_opportunity(self, opportunity_id: int) -> dict:
        """Research one approved opportunity without exposing the CV or source library to search."""
        opportunity = self.library.get_opportunity(opportunity_id)
        if not opportunity:
            raise KeyError(opportunity_id)
        profile = self.library.get_profile()
        location = profile.get("location") or "United States"
        query = f"{opportunity['title']} {location} market demand outlook alternatives"
        results = self._web_search(query)
        report = self._structured(
            [
                {
                    "role": "system",
                    "content": (
                        "Validate an opportunity using only the supplied public search snippets and opportunity summary. "
                        "Separate evidence from judgment, cite source URLs in every finding, identify contradictions, "
                        "and recommend small tests rather than claiming certainty."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"DATE: {date.today().isoformat()}\nLOCATION: {location}\n"
                        f"OPPORTUNITY: {json.dumps(opportunity, default=str)[:20000]}\n"
                        f"PUBLIC SEARCH RESULTS: {json.dumps(results, default=str)[:50000]}"
                    ),
                },
            ],
            ValidationReport,
        ).model_dump()
        self.library.update_opportunity(opportunity_id, status="validated", validation=report)
        return self.library.get_opportunity(opportunity_id) or report

    def complete_workspace(self, project_id: int) -> dict:
        snapshot = self.library.workspace_snapshot(project_id)
        open_tasks = [task for task in snapshot["tasks"] if task["status"] not in {"done", "dismissed"}]
        if open_tasks:
            raise RuntimeError("Complete or dismiss the remaining execution-plan tasks first.")
        review = self._structured(
            [
                {
                    "role": "system",
                    "content": (
                        "Review completed work from supplied evidence. Record outcomes, deliverables, lessons, unresolved "
                        "items, demonstrated skills, and follow-up opportunities. Suggest profile additions but do not "
                        "apply them. Never claim an outcome unsupported by the workspace."
                    ),
                },
                {"role": "user", "content": json.dumps(snapshot, default=str)[:150000]},
            ],
            CompletionReview,
        ).model_dump()
        current = self.library.get_profile().get("suggestions", {})
        current["workspace_completion"] = review["profile_suggestions"]
        self.library.update_profile({"suggestions": current})
        return self.library.complete_workspace(project_id, review)

    def reorganize_book(self, project_id: int, *, feedback: str = "", trigger_note_id: int | None = None) -> dict:
        book = self.library.get_book(project_id)
        workspace_type = book["project"]["workspace_type"]
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
                        "Maintain the workspace's living document. For books, produce an author-controlled manuscript organized into "
                        "parts/chapters/scenes without inventing canon. For businesses, maintain an evidence-led venture brief that "
                        "separates assumptions from validated facts. For impact work, maintain a Theory-of-Change brief connecting "
                        "need, activities, outputs, outcomes, impact, indicators, assumptions, safeguards, and risks. For other projects, "
                        "maintain a clear project brief. Integrate relevant source material, preserve useful content, cite note IDs, "
                        f"and keep uncertainty explicit. WORKSPACE TYPE: {workspace_type}."
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
        try:
            self.initialize_workspace(project_id, include_initial_tasks=False)
        except Exception:
            # Studio-card refresh is helpful but must not roll back the primary
            # working document when a provider times out.
            logger.exception("Automatic studio refresh failed for project %s", project_id)
        # Content integration and execution planning are one workflow. Library
        # preserves completed and owner-authored tasks during this refresh.
        try:
            self.refresh_plan(project_id, reason=feedback or "New source material integrated")
        except Exception:
            # A planning-provider failure must not roll back a successfully
            # integrated manuscript or project document.
            logger.exception("Automatic execution-plan refresh failed for project %s", project_id)
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

    def refresh_growth_plan(self, weeks: int = 4) -> dict:
        """Plan across goals and active workspaces for a chosen horizon."""
        weeks = weeks if weeks in {2, 4, 12} else 4
        self.library.sync_growth_from_profile()
        profile = self.library.get_profile()
        items = self.library.list_growth_items()
        projects = self.library.list_projects()
        workspace_tasks = {
            project["name"]: self.library.list_tasks(project["id"])
            for project in projects
            if project.get("status", "active") == "active"
        }
        plan = self._structured(
            [
                {
                    "role": "system",
                    "content": (
                        "Act as a portfolio execution coach. Build one realistic, prioritized action queue spanning the owner's "
                        "in-progress certifications, personal goals, and active workspaces. Every item explicitly marked in progress "
                        "must receive concrete next actions unless already complete. Avoid duplicate work already represented by an "
                        "open workspace task. Use small outcome-based actions, realistic minute estimates, and ISO dates. Balance "
                        "urgent deadlines with steady certification and career progress. Do not mark progress or completion without evidence."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"TODAY: {date.today().isoformat()}\n"
                        f"PROFILE: {json.dumps({k: profile[k] for k in ('headline','location','skills','certifications','interests','goals')})}\n"
                        f"TRACKED GROWTH: {json.dumps(items)}\n"
                        f"ACTIVE WORKSPACES: {json.dumps(projects)}\n"
                        f"CURRENT WORKSPACE TASKS: {json.dumps(workspace_tasks)}\n"
                        f"Return a focused plan for the next {weeks} weeks. item_title and project_name must exactly match supplied names when used."
                    ),
                },
            ],
            GrowthPlan,
        ).model_dump()
        self.library.replace_ai_growth_actions(plan["actions"])
        self.library.set_settings(
            {
                "growth_planning_note": plan["planning_note"],
                "growth_plan_risks": json.dumps(plan["risks"]),
                "growth_last_planned_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        return self.library.growth_overview()

    def answer(self, question: str, project_id: int | None = None, selected_ids: list[int] | None = None) -> dict:
        notes = (
            [note for i in selected_ids if (note := self.library.get_note(i))]
            if selected_ids
            else self.library.context_notes(project_id, limit=30)
        )
        note_context = "\n\n".join(
            f"[Note {n['id']}: {n['title']}]\n{n['summary']}\n{n['transcript'][:8000]}" for n in notes
        )
        workspace_context = ""
        if project_id:
            snapshot = self.library.workspace_snapshot(project_id)
            workspace_context = json.dumps(
                {
                    "project": snapshot["project"],
                    "owner_direction": snapshot["instructions"],
                    "living_document": snapshot["sections"],
                    "studio_cards": snapshot["cards"],
                    "execution_plan": snapshot["tasks"],
                },
                default=str,
            )[:100000]
        answer = self._text(
            (
                "Answer from the complete supplied project context: imported documents and images, transcribed audio, "
                "the living document, studio cards, owner direction, and execution plan. Cite [Note ID] for source-library "
                "claims and identify uncertainty, contradictions, and unsupported assumptions."
            ),
            f"QUESTION:\n{question}\n\nPROJECT WORKSPACE:\n{workspace_context or 'No selected workspace.'}\n\nSOURCE LIBRARY:\n{note_context or 'No source records.'}",
        )
        return {"answer": answer, "sources": [{"id": n["id"], "title": n["title"]} for n in notes]}

    def research_workspace(self, project_id: int, query: str) -> dict:
        """Research an owner-approved public query and return source-linked advice."""
        workspace = self.library.workspace_snapshot(project_id)
        profile = self.library.get_profile()
        public_query = f"{workspace['project']['name']} {query} {profile.get('location','')}".strip()
        results = self._web_search(public_query, limit=8)
        pages = []
        for result in results[:5]:
            try:
                extract = self._fetch_public_page(result["url"])
            except Exception:
                logger.info("Public research page could not be read: %s", result["url"])
                extract = ""
            if extract:
                pages.append({"title": result["title"], "url": result["url"], "extract": extract})
        report = self._structured(
            [
                {
                    "role": "system",
                    "content": (
                        "Act as a rigorous research strategist. Use only the supplied public search results, page extracts, and workspace "
                        "description. Prefer credible primary, institutional, academic, government, standards, reputable "
                        "industry, and well-attributed review sources. Separate evidence from interpretation, cite URLs for "
                        "claims, expose disagreements and limitations, and convert findings into measurable recommendations. "
                        "Do not silently modify the workspace."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"DATE: {date.today().isoformat()}\nRESEARCH REQUEST: {query}\n"
                        f"WORKSPACE: {json.dumps(workspace, default=str)[:70000]}\n"
                        f"PUBLIC RESULTS: {json.dumps(results, default=str)[:40000]}\n"
                        f"PUBLIC PAGE EXTRACTS: {json.dumps(pages, default=str)[:100000]}"
                    ),
                },
            ],
            WorkspaceResearch,
        ).model_dump()
        report["raw_results"] = results
        report["pages_reviewed"] = [{"title": page["title"], "url": page["url"]} for page in pages]
        return report

    def improve_workspace_selection(self, project_id: int, selection: str, instruction: str) -> dict:
        """Improve owner-selected material using full workspace context without mutating it."""
        snapshot = self.library.workspace_snapshot(project_id)
        improved = self._text(
            (
                "Improve the selected material for clarity, strategic strength, evidence discipline, execution value, "
                "and measurable outcomes. Respect the workspace type and owner direction. Do not fabricate facts or sources. "
                "Return a polished replacement followed by a short 'Why this is stronger' note."
            ),
            (
                f"WORKSPACE CONTEXT:\n{json.dumps(snapshot, default=str)[:100000]}\n\n"
                f"OWNER REQUEST:\n{instruction}\n\nSELECTED MATERIAL:\n{selection}"
            ),
        )
        return {"improved": improved}

    def accelerate_workspace(self, project_id: int, objective: str = "") -> dict:
        """Build the next purpose-specific structure and execution layer."""
        snapshot = self.library.workspace_snapshot(project_id)
        kind = snapshot["project"]["workspace_type"]
        guidance = {
            "book": (
                "Create a book architecture: reader promise, premise, themes, story or argument spine, ordered "
                "parts and chapters, a brief for every chapter, scenes/evidence to use, character/voice/continuity "
                "notes where relevant, research gaps, and next writing actions."
            ),
            "business": (
                "Create an opportunity-to-execution architecture: customer/problem hypotheses, value proposition, "
                "alternatives, evidence ledger, assumptions, smallest validation tests, offer, channels, risks, "
                "success metrics, milestones, and ordered actions."
            ),
            "impact": (
                "Create an impact architecture: need, beneficiaries, theory of change, activities, outputs, outcomes, "
                "indicators, partnerships, funding assumptions, safeguards, risks, milestones, and ordered actions."
            ),
        }.get(
            kind,
            "Create a delivery and growth architecture: outcome, scope, evidence, capability gaps, milestones, "
            "dependencies, risks, success metrics, decision points, and ordered next actions.",
        )
        result = self._structured(
            [
                {
                    "role": "system",
                    "content": (
                        f"{guidance} Use only supplied evidence, distinguish evidence from hypotheses, preserve owner "
                        "intent, cite source note IDs when applicable, and make tasks small, measurable, and ordered."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"OWNER OBJECTIVE:\n{objective or 'Strengthen this workspace and identify the highest-leverage next work.'}\n\n"
                        f"COMPLETE WORKSPACE:\n{json.dumps(snapshot, default=str)[:150000]}"
                    ),
                },
            ],
            WorkspaceAcceleration,
        ).model_dump()
        for card in result["cards"]:
            metadata = dict(card.get("metadata", {}))
            metadata["source"] = "workspace-accelerator"
            self.library.add_workspace_card(
                project_id,
                collection=card["collection"],
                title=card["title"],
                content=card["content"],
                metadata=metadata,
            )
        for task in result["tasks"]:
            self.library.add_task(
                project_id,
                title=task["title"],
                details=task["details"],
                priority=task["priority"],
                estimate_minutes=task["estimate_minutes"],
                target_date=task["target_date"],
            )
        return {
            **result,
            "workspace_type": kind,
            "workspace": self.library.workspace_snapshot(project_id),
        }
