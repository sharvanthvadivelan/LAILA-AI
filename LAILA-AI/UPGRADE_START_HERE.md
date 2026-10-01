# Laila 0.2 — your personal workspace

This update is built from the ZIP you supplied. It adds About me, My day, study logs, revision dates, and approved Windows launches. No model or private data is bundled.

## Install into your existing working Laila

1. Stop Laila's running server with Ctrl+C. Close the browser tab.
2. Make a backup copy of your entire current LAILA-AI folder while the server is stopped. Keep that copy outside the folder you are updating. If you use LAILA_DATA_DIR, back up that data location too.
3. Extract this ZIP to a temporary folder. Copy the CONTENTS of its LAILA-AI folder into your existing inner LAILA-AI folder (the one containing app and frontend). Allow replacement of code files. This package contains no .env, data or .venv folder, so it does not replace those. Keep the existing project location: uploaded document paths may be absolute.
4. In PowerShell, from that existing inner LAILA-AI folder, run:

```powershell
$LailaPython = @('.\.venv\Scripts\python.exe', '..\.venv\Scripts\python.exe') | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $LailaPython) { throw 'No project virtual environment found. Run .\scripts\setup.ps1 first.' }
& $LailaPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Do not start until this is resolved.' }
& $LailaPython -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

5. Open http://127.0.0.1:8000 and refresh the page. Existing conversations, notes, tasks, memories and settings remain in your local database. The update adds new tables without rewriting existing records.

Fresh install: run `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup.ps1` first. An existing Ollama installation and llama3.2 model can be reused; do not download the model again just for this update.

## First five minutes

- Open **About me**. Check the name/timezone and save your goals, subjects, routine and preferences. These fields are blank until you fill them. Laila has not imported a biography or assumed your college hours.
- Open **My day**. Add one dated study block and your real tasks. Date/time input uses the browser's local timezone; saved times include an offset and the planner groups them by the profile timezone.
- After studying, log your topic, minutes and confidence. Optionally choose a revision date. The seven-day total uses your logged work, not an estimate of your activity.
- Use **Quiz me**, **Morning check-in**, or **Evening review**. They open a new chat and prepare a message; press Send when ready. The model can use your profile and relevant planning data when both profile use and Settings > Memory are enabled.
- Enable **Gentle reminders** if wanted. Keep this tab open and the laptop awake. A dismissible in-app banner appears during a scheduled block. Timing depends on browser throttling. This is not a background Windows alarm, push notification, or reliable closed-app reminder.

Profile edits and deletion do not remove profile information already quoted in saved conversations; delete those conversations separately if needed. Settings > Export personal data includes the new records. Profile and planner data are stored locally and unencrypted, like existing Laila data.

## Desktop actions

In **Desktop**, add a trusted installed application's full .exe path, or a local folder path. Do not include command arguments. You can use File Explorer's Copy as path, removing surrounding quote characters before pasting.

Use **Request launch**, then review and approve in Chat. Or say `Open <exact saved target name>` in Chat: this proposes the launch directly without waiting for the language model. A launch approval is single-use. Removed or changed targets cannot be launched with a stale approval. Laila reports that Windows accepted a launch request; it does not pretend to have verified the application window.

This version does not click or type inside other apps, run generated shell commands, send messages, delete user files, or control Android apps. It runs with your normal Windows account; do not start it as administrator.

Optional desktop shortcut, from the project folder:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\create_desktop_shortcut.ps1
```

Double-click the resulting Laila shortcut to start the server. Open http://127.0.0.1:8000 in your browser. Keep the server window open; Ctrl+C stops it. The shortcut points to this installation; do not move it afterward. An existing Laila shortcut is not overwritten.

## Voice

Existing push-to-talk and Windows speech features are retained. They require the optional voice package, a locally downloaded faster-whisper model, and microphone permission. See START_HERE.md and scripts/download_voice_model.py. Settings shows whether the package and model folder exist. This update does not install a microphone driver, download a voice model, or add an always-listening wake word.

## Phone — status

This release remains loopback-only on the laptop. A mobile-size layout does NOT mean phone connectivity is installed. Do not expose port 8000 or Ollama's port to the public internet. Secure remote access, device authentication, and an Android companion are separate unfinished features. Laptop-hosted inference requires the laptop awake; independent offline Android inference requires its own runtime and model.

## What changed for responses

Ordinary explanations and code questions no longer receive every tool schema. Calculator syntax errors are recoverable. Irrelevant old tool observations are no longer re-injected into every prompt. Exact configured desktop launch requests use a direct approval path. No measured model-speed improvement is claimed: this release was tested without a live Ollama model.

## Rollback

Stop the updated server. Restore your pre-update code AND data backup to the same location. Do not delete your current data or overwrite it while the server is running.

## Validation

See docs/VALIDATION.md for tests actually run and platform limitations. Windows application launching, microphone recording, local speech models and real Ollama inference require validation on your laptop.
