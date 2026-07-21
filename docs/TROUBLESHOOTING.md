# Troubleshooting

## Watcher appears frozen

Check `logs/knowledgeforge.log`. Older releases attempted to move files from iCloud and could block inside the provider. The current release copies audio locally and never deletes cloud sources. If an old process is still stuck, close its terminal or terminate only that KnowledgeForge Python process, then restart.

## “Available when online”

Right-click the iCloud Inbox and choose **Always keep on this device**. Wait for the green checkmark. The worker can request hydration, but pinning is more reliable.

## FFmpeg not found

Install FFmpeg, open a new terminal, and run `ffmpeg -version`. Then activate `.venv` and run `knowledgeforge verify`.

## Whisper or web dependencies missing

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## Browser microphone unavailable

Use `http://127.0.0.1:8765`, grant microphone permission, and avoid accessing the local app through an insecure non-localhost address. Remote VM access should use HTTPS.

## Transcript does not appear immediately

The first run downloads and loads the selected Whisper model. CPU transcription can take time. Review the terminal and private log, then refresh the library.

## Port already in use

Set `KF_WEB_PORT` to another value in `.env`, restart, and browse to that port.
