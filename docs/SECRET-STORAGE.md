# Secret Storage

KnowledgeForge uses one credential backend per deployment. Backends do not cascade or operate together.

## Native Windows: Credential Manager and DPAPI

The default on Windows is `KF_SECRET_BACKEND=windows`. Open **Add or manage API keys** in the local application, paste a provider key, and choose **Save securely**.

The key travels only over the loopback connection to the local KnowledgeForge process. The password input disables autocomplete and is cleared immediately after the request. The server sends it directly to Windows Credential Manager through the Python keyring adapter. Windows protects the credential for the signed-in user with its credential-protection mechanisms, including DPAPI-backed protection.

KnowledgeForge does not store the key in SQLite, source files, browser storage, logs, or API responses. In-app writes are rejected unless the server binds to loopback.

```powershell
knowledgeforge secrets set openai
knowledgeforge secrets list
knowledgeforge secrets delete openai
```

## Linux, Docker, and cloud: mounted files

Set `KF_SECRET_BACKEND=file`. KnowledgeForge reads one read-only file per credential from `KF_SECRETS_DIR`, defaulting to `/run/secrets`:

```text
/run/secrets/OPENAI_API_KEY
/run/secrets/ANTHROPIC_API_KEY
```

The included Docker Compose configuration selects this backend and mounts `./secrets` read-only. The host directory is gitignored. The web interface reports status but does not accept secret writes.

Cloud services should inject or synchronize credentials into this mount using AWS Secrets Manager, Azure Key Vault, Google Secret Manager, Kubernetes External Secrets/Secrets Store CSI, Docker Swarm secrets, or Vault Agent. This keeps cloud SDKs and long-lived cloud credentials out of KnowledgeForge.

## Compatibility: environment variables

Set `KF_SECRET_BACKEND=environment` only when the platform intentionally injects environment variables. KnowledgeForge then reads names such as `OPENAI_API_KEY` directly from its process environment. It will not consult Windows Credential Manager or mounted files.

## Security limits

Secure storage protects credentials at rest and reduces accidental disclosure. A compromised process running as the same user can still use credentials available to that process. Apply provider spending limits, separate development and production keys, rotation, usage alerts, least privilege, dependency patching, and host isolation.
