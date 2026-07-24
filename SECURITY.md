# Security Policy

KnowledgeForge is a security-first project, but “local-first” does not mean “risk-free.” It processes private source material, invokes native media tools, and can send extracted content to configured AI providers. Those boundaries must remain visible.

## Supported version

Security fixes are applied to the latest release on the default branch.

## Reporting a vulnerability

Do not open a public issue containing recordings, transcripts, credentials, private paths, personal information, or exploit details. Contact the repository owner privately through the security-reporting method configured on GitHub.

Include the affected version, impact, reproducible steps, and a safe proof of concept. Remove real private content before sharing logs or screenshots.

## Data and trust boundaries

- Original media, transcripts, generated workspaces, databases, and logs stay on the configured host unless the owner deliberately moves them.
- Whisper transcription runs locally.
- Selecting a cloud AI provider creates an external data-egress boundary. Relevant transcript or document text is sent to that provider for analysis. Review its retention, training, residency, and contractual controls before use.
- Selecting Ollama keeps model inference local when Ollama itself is local and no remote endpoint is configured.
- Imported files and their contents are untrusted input. Extracted text may contain prompt-injection instructions; it must be treated as source data, not system authority.
- FFmpeg, Whisper, document parsers, model SDKs, and their transitive dependencies are part of the software supply-chain boundary.

## Local deployment baseline

- Bind to `127.0.0.1` unless remote access has been intentionally secured.
- The local application has no authentication. Do not expose it directly to the internet or an untrusted LAN.
- Store native Windows provider keys through KnowledgeForge's Credential Manager/DPAPI backend. Use the separate read-only file backend in Linux, containers, and cloud deployments.
- Keep compatibility `.env` and `.env.providers` files outside Git and restrict their filesystem permissions.
- Never commit `Inbox`, recordings, transcripts, summaries, personal or business material, databases, or logs.
- Uploaded CVs and extracted profile text are private runtime data under the ignored imports/database paths.
- Opportunity web validation is owner-initiated. Search queries use only the opportunity title and profile location, not the CV or private source text.
- Review staged files and generated archives before every push or release.
- Keep Windows, Python, FFmpeg, Whisper, model runtimes, and dependencies patched.
- Back up private workspaces separately from the public source repository.

## Remote or container deployment baseline

Before deployment beyond localhost, add TLS, authentication, authorization, least-privilege service accounts, encrypted storage, managed secrets, network restrictions, upload limits, malware scanning, rate limits, audit events, backups, and recovery testing. Multi-user deployment additionally requires tenant isolation and deletion/export controls.

Run containers as a non-root user, mount only required directories, use read-only filesystems where possible, pin and scan images, and do not expose Ollama or other model runtimes publicly.

See [docs/CLOUD-SAAS-RUNBOOK.md](docs/CLOUD-SAAS-RUNBOOK.md) for the production path.

## Current limitations

- No built-in user authentication or authorization.
- No malware scanning or hardened public-upload boundary.
- No tenant isolation.
- No formal content-level encryption inside the application.
- Provider behavior remains subject to each provider’s service and data-handling terms.

These limitations are deployment constraints, not optional warnings.
