"""Command-line entry point for verification, batch work, watcher, and web UI."""

from __future__ import annotations

import argparse
import getpass
import json
import logging
import shutil
import sys
from pathlib import Path

from .config import Settings
from .library import Library
from .pipeline import TranscriptionPipeline
from .secrets import ProviderSecrets, SecretStoreError


def _provider_secret(settings: Settings, provider: str) -> str:
    """Resolve a friendly provider ID to its configured credential name."""
    catalog = json.loads(settings.provider_catalog.read_text(encoding="utf-8"))
    item = next((item for item in catalog["providers"] if item["id"] == provider.lower()), None)
    if not item or not item.get("api_key_env"):
        raise SecretStoreError(f"Provider '{provider}' has no API-key entry in the provider catalog.")
    return str(item["api_key_env"])


def manage_secrets(settings: Settings, action: str, provider: str | None) -> int:
    """Manage credentials without accepting values in command history."""
    store = ProviderSecrets()
    if action == "list":
        catalog = json.loads(settings.provider_catalog.read_text(encoding="utf-8"))
        for item in catalog["providers"]:
            if name := item.get("api_key_env"):
                print(f"{item['id']}: {store.source(name)}")
        return 0
    if not provider:
        raise SecretStoreError("A provider is required for set or delete.")
    name = _provider_secret(settings, provider)
    if action == "set":
        value = getpass.getpass(f"Enter {provider} API key (input hidden): ")
        confirmation = getpass.getpass("Enter it again: ")
        if value != confirmation:
            raise SecretStoreError("The two values did not match; nothing was saved.")
        store.set(name, value)
        print(f"Stored {provider} in the OS credential manager.")
        return 0
    deleted = store.delete(name)
    print(f"Deleted {provider}." if deleted else f"No OS-stored secret exists for {provider}.")
    return 0


def configure_logging(settings: Settings, verbose: bool = False) -> None:
    """Log to both the terminal and a private rotating-ready file location."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(settings.logs / "knowledgeforge.log", encoding="utf-8"),
        ],
        force=True,
    )


def verify(settings: Settings) -> int:
    """Print actionable dependency and privacy-path diagnostics."""
    problems: list[str] = []
    print(f"Python: {sys.version.split()[0]} ({sys.executable})")
    ffmpeg = shutil.which("ffmpeg")
    print(f"FFmpeg: {ffmpeg or 'NOT FOUND'}")
    if not ffmpeg:
        problems.append("FFmpeg is not on PATH")
    try:
        import whisper

        print(f"Whisper: installed ({Path(whisper.__file__).parent})")
    except ImportError:
        print("Whisper: NOT INSTALLED in this Python environment")
        problems.append("Whisper is missing")
    try:
        import fastapi

        print(f"FastAPI: installed ({fastapi.__version__})")
    except ImportError:
        print("FastAPI: NOT INSTALLED in this Python environment")
        problems.append("Web dependencies are missing")
    for label, path in (
        ("Inbox", settings.inbox),
        ("Recordings", settings.recordings),
        ("Transcripts", settings.transcripts),
        ("Database", settings.database),
    ):
        print(f"{label}: {path}")
    print("\nVerification passed." if not problems else "\nNeeds attention: " + "; ".join(problems))
    return 0 if not problems else 1


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="KnowledgeForge private voice-to-knowledge application.")
    root.add_argument("--verbose", action="store_true")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("verify", help="Check dependencies and configured folders.")
    batch = commands.add_parser("batch", help="Process recordings once.")
    batch.add_argument("--overwrite", action="store_true")
    commands.add_parser("watch", help="Run the foreground folder watcher.")
    commands.add_parser("serve", help="Run the web app and watcher together.")
    secrets = commands.add_parser("secrets", help="Manage provider keys in LLM Secrets.")
    secrets.add_argument("action", choices=("set", "list", "delete"))
    secrets.add_argument("provider", nargs="?", help="Provider ID, such as openai or anthropic.")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    settings = Settings.load()
    configure_logging(settings, args.verbose)
    if args.command == "secrets":
        try:
            return manage_secrets(settings, args.action, args.provider)
        except SecretStoreError as exc:
            print(f"Secret operation failed: {exc}", file=sys.stderr)
            return 2
    if args.command == "verify":
        return verify(settings)
    pipeline = TranscriptionPipeline(settings, Library(settings.database))
    if args.command == "batch":
        result = pipeline.run_once(overwrite=args.overwrite)
        print(f"Completed: {result['completed']}; failed: {result['failed']}")
        return 1 if result["failed"] else 0
    if args.command == "watch":
        try:
            pipeline.watch()
        except KeyboardInterrupt:
            logging.info("Watcher stopped by user.")
        return 0

    # Import web-only dependencies lazily so batch/verification failures remain
    # understandable even when the optional web stack has not been installed.
    import uvicorn

    uvicorn.run("knowledgeforge.web:create_app", factory=True, host=settings.web_host, port=settings.web_port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
