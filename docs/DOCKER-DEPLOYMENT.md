# Docker Deployment Guide

KnowledgeForge includes a `Dockerfile` and `docker-compose.yml`. The image contains the application, FFmpeg, Python dependencies, web interface, and local Whisper runtime. Model files and private application data are mounted outside the container so upgrades do not erase them.

## Important iCloud limitation

- **Windows host or Windows VM:** iCloud for Windows can sync the phone Inbox. Docker Desktop can mount that host folder into the container.
- **Linux VM:** Apple does not provide an official iCloud Drive sync client for Linux. Use KnowledgeForge's browser recording/upload over HTTPS, or operate a separate trusted bridge that sends files to the VM.
- Do not design a production Linux deployment around an unofficial iCloud client without separately assessing its security and reliability.

## Option A: Local Docker on Windows with iCloud Inbox

### 1. Install prerequisites

Install Docker Desktop and ensure Linux containers are enabled. Confirm:

```powershell
docker version
docker compose version
```

### 2. Create a local override

At the repository root, create `docker-compose.override.yml`:

```yaml
services:
  knowledgeforge:
    volumes:
      - ./runtime:/data
      - B:/iCloud/iCloudDrive/KnowledgeForge/Inbox:/data/inbox
      - whisper-models:/home/knowledgeforge/.cache/whisper
```

Docker Desktop must be allowed to access the `B:` drive. In File Explorer, mark the iCloud Inbox **Always keep on this device**.

The override file can contain machine-specific paths and should not be committed if customized.

### 3. Build and start

```powershell
docker compose up --build -d
docker compose logs -f knowledgeforge
```

Open `http://127.0.0.1:8765`.

### 4. Stop and restart

```powershell
docker compose stop
docker compose start
```

To remove the container without deleting private mounted data:

```powershell
docker compose down
```

Do not add `--volumes` unless you deliberately intend to delete named model volumes.

## Option B: Private Linux VM

### 1. Prepare the VM

Use a supported Linux distribution, install Docker Engine with the Compose plugin, enable security updates, and restrict SSH through the firewall/security group.

```bash
docker version
docker compose version
```

### 2. Obtain the repository

```bash
git clone https://github.com/YOUR-ACCOUNT/knowledgeforge-ai.git
cd knowledgeforge-ai
```

Replace the placeholder URL with the published repository URL.

### 3. Configure runtime settings

```bash
cp .env.example .env
```

For Docker, the Compose file maps private data to `/data`. Keep container paths at their Docker defaults. Change the Whisper model or language only if needed.

### 4. Start privately

```bash
mkdir -p runtime
docker compose up --build -d
docker compose ps
docker compose logs -f knowledgeforge
```

The default port mapping uses `127.0.0.1:8765`, so it is reachable only from the VM itself. Test on the VM:

```bash
curl http://127.0.0.1:8765/health
```

### 5. Add secure remote access

Before allowing other devices to connect:

1. Add authentication.
2. Put the service behind Caddy, Nginx, Traefik, or an AWS load balancer.
3. Enable HTTPS with a valid certificate.
4. Keep port 8765 private; expose only HTTPS.
5. Restrict firewall/security-group rules.
6. Configure backups for `runtime/`.

Browser microphone recording from another device requires HTTPS. Do not expose the current unauthenticated application directly to the internet.

### 6. Ingest recordings

Without iCloud on Linux, choose one:

- Record or upload through the KnowledgeForge web interface after HTTPS is configured.
- Upload through a future authenticated API/mobile integration.
- Sync from the Windows iCloud computer through a private VPN and authenticated transfer job.
- Mount a supported private storage service into `/data/inbox`.

### 7. Upgrade

```bash
git pull --ff-only
docker compose build --pull
docker compose up -d
docker compose ps
curl http://127.0.0.1:8765/health
```

Back up private data before upgrades. Pin tagged releases in production rather than deploying an unreviewed moving branch.

## Data locations

```text
runtime/inbox/         uploaded or externally delivered audio
runtime/recordings/    local archive copies
runtime/transcripts/   text and metadata output
runtime/summaries/     future generated artifacts
runtime/database/      SQLite library
runtime/logs/          application logs
```

All are excluded from Git and the Docker build context.

## Validation

```bash
docker compose ps
docker compose logs --tail=100 knowledgeforge
curl http://127.0.0.1:8765/health
docker inspect --format='{{json .State.Health}}' knowledgeforge-ai-knowledgeforge-1
```

The exact container name can vary by project-directory name; use `docker compose ps` to find it.

## Troubleshooting

- **Container exits:** run `docker compose logs knowledgeforge`.
- **Model download is slow:** the first transcription downloads the selected Whisper model into the named model volume.
- **Permission denied under `runtime/`:** make the host directory writable by container UID `10001`, or configure an appropriate ownership strategy for the host.
- **Browser cannot connect:** confirm the container is healthy and remember that the default bind is localhost-only.
- **Phone microphone unavailable:** configure HTTPS; browsers require a secure context for microphone access outside localhost.
- **iCloud files remain online-only:** hydrate/pin them on the Windows host before the container reads them.
