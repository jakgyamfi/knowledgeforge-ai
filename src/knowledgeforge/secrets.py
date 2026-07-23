"""Provider credential boundary with one explicitly selected backend.

Windows desktop installations use Credential Manager (DPAPI-protected for the
signed-in user). Linux, containers, and cloud deployments consume read-only
files injected by their platform. Environment variables are an explicit
compatibility mode, never an implicit fallback.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

SERVICE_NAME = "knowledgeforge-ai"
SAFE_SECRET_NAME = re.compile(r"^[A-Z][A-Z0-9_]{1,127}$")
BACKENDS = {"windows", "file", "environment"}


class SecretStoreError(RuntimeError):
    """Raised when a secure-store operation cannot be completed."""


class ProviderSecrets:
    """Read credentials from exactly one deployment-selected backend."""

    def __init__(self, backend: str | None = None, secrets_dir: Path | None = None) -> None:
        selected = (backend or os.getenv("KF_SECRET_BACKEND", "auto")).strip().lower()
        if selected == "auto":
            selected = "windows" if os.name == "nt" else "file"
        if selected not in BACKENDS:
            raise SecretStoreError(f"KF_SECRET_BACKEND must be one of: {', '.join(sorted(BACKENDS))}.")
        if selected == "windows" and os.name != "nt":
            raise SecretStoreError("The windows secret backend is available only on Windows.")
        self.backend = selected
        configured = os.getenv("KF_SECRETS_DIR", "").strip()
        self.secrets_dir = secrets_dir or Path(configured or "/run/secrets")

    @staticmethod
    def _validate(name: str) -> str:
        clean = name.strip().upper()
        if not SAFE_SECRET_NAME.fullmatch(clean):
            raise SecretStoreError("Secret names must use uppercase letters, numbers, and underscores.")
        return clean

    @property
    def writable(self) -> bool:
        """Only the native Windows backend accepts writes from the local UI."""
        return self.backend == "windows"

    def get(self, name: str) -> str | None:
        clean = self._validate(name)
        if self.backend == "file":
            secret_file = self.secrets_dir / clean
            if not secret_file.is_file():
                return None
            return secret_file.read_text(encoding="utf-8").strip() or None
        if self.backend == "environment":
            return os.getenv(clean) or None
        try:
            import keyring

            return keyring.get_password(SERVICE_NAME, clean)
        except Exception as exc:
            raise SecretStoreError("Windows Credential Manager is unavailable.") from exc

    def set(self, name: str, value: str) -> None:
        clean = self._validate(name)
        if not self.writable:
            raise SecretStoreError(f"The {self.backend} backend is operator-managed and read-only in the app.")
        if not value.strip():
            raise SecretStoreError("The secret value cannot be empty.")
        try:
            import keyring

            keyring.set_password(SERVICE_NAME, clean, value.strip())
        except Exception as exc:
            raise SecretStoreError("Windows Credential Manager could not store this secret.") from exc

    def delete(self, name: str) -> bool:
        clean = self._validate(name)
        if not self.writable:
            raise SecretStoreError(f"The {self.backend} backend is operator-managed and read-only in the app.")
        try:
            import keyring

            if keyring.get_password(SERVICE_NAME, clean) is None:
                return False
            keyring.delete_password(SERVICE_NAME, clean)
            return True
        except Exception as exc:
            raise SecretStoreError("Windows Credential Manager could not delete this secret.") from exc

    def source(self, name: str) -> str:
        """Report only status and backend; never return the credential value."""
        return self.backend if self.get(name) else "not configured"
