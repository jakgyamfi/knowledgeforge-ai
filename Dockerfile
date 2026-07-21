# syntax=docker/dockerfile:1
FROM python:3.12-slim

# FFmpeg is the only required operating-system dependency for Whisper audio
# decoding.  The unprivileged user limits damage from an application defect.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 knowledgeforge

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir .

RUN mkdir -p /data/inbox /data/recordings /data/transcripts /data/summaries /data/logs /data/database \
    && chown -R knowledgeforge:knowledgeforge /data /app
USER knowledgeforge

ENV KF_INBOX_DIR=/data/inbox \
    KF_RECORDINGS_DIR=/data/recordings \
    KF_TRANSCRIPTS_DIR=/data/transcripts \
    KF_SUMMARIES_DIR=/data/summaries \
    KF_LOG_DIR=/data/logs \
    KF_DATABASE_PATH=/data/database/knowledgeforge.db \
    KF_WEB_HOST=0.0.0.0 \
    KF_WEB_PORT=8765

VOLUME ["/data"]
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/health', timeout=3)"
CMD ["knowledgeforge", "serve"]
