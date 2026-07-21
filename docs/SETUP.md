# Windows setup and verification

KnowledgeForge processes audio locally. iCloud only delivers files placed in the synced folders; recordings and generated transcripts are excluded from Git.

After successful processing, audio is copied from the synced Inbox into the local `recordings` archive. Transcripts are stored directly under local `transcripts`; any nested Inbox folders are preserved. Cloud files are not deleted automatically because iCloud deletion can block the worker.

## 1. Install Python

Install Python 3.10 or newer. During installation, enable **Add Python to PATH**. Then open a new PowerShell window and run:

```powershell
python --version
```

## 2. Install FFmpeg

Whisper uses FFmpeg to read audio. Install FFmpeg with one of these Windows package managers:

```powershell
winget install --id Gyan.FFmpeg.Shared --exact
```

or:

```powershell
choco install ffmpeg
```

Open a new PowerShell window and verify:

```powershell
ffmpeg -version
```

## 3. Create the project environment

From `B:\iCloud\KnowledgeForge`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
```

If PowerShell blocks activation for this window, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## 4. Configure and verify

Defaults already match the repository folders. Optional overrides:

```powershell
Copy-Item .env.example .env
```

Then verify the complete environment:

```powershell
knowledgeforge verify
```

The first transcription downloads the selected Whisper model into the local model cache. The default `base` model is a practical starting point; `tiny` is faster and less accurate, while `small` and larger models require more time and memory.

## Troubleshooting

- **Whisper missing:** confirm the virtual environment is active, then run `python -m pip install -r requirements.txt`.
- **FFmpeg not found:** reopen PowerShell after installation and run `ffmpeg -version`.
- **Python opens the Microsoft Store:** install Python from python.org or with `winget install Python.Python.3.12`, then reopen PowerShell.
- **Slow transcription:** set `KF_WHISPER_MODEL=tiny` in `.env` for a quick test.
- **iCloud file unavailable:** wait until the audio file is fully downloaded locally before processing.
- **iCloud shows “Available when online”:** right-click the KnowledgeForge `Inbox` in File Explorer and choose **Always keep on this device**. Restart the watcher after changing this setting.
