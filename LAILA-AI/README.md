# Laila 0.3.0 update

Start with **UPGRADE_START_HERE.md** for upgrading your working installation and using the new personal workspace. The original architecture and setup notes follow.

# LAILA AI

**Local Intelligent AI & Learning Assistant · v0.3.0**

A real local web application: a dark chat interface served by FastAPI, Ollama for local model inference, SQLite for personal data, and FAISS retrieval over locally generated embeddings. It does not include a model, require a cloud account, or return canned AI answers.

This is the first runnable development release, not a claim that every item in the master specification is complete. See [feature status](docs/FEATURE_STATUS.md) and [validation](docs/VALIDATION.md) for exact limits.

## Start on Windows 10/11

1. Extract this ZIP into a dedicated folder, for example `C:\Projects\LAILA-AI`. Open that folder in VS Code.
2. Install **64-bit Python 3.11 or 3.12**, including the Python launcher, from <https://www.python.org/downloads/windows/>. Newer versions may work if all binary packages provide compatible wheels.
3. Install **Ollama** from <https://ollama.com/download/windows>. Reopen the VS Code terminal after installation.
4. In the VS Code **PowerShell** terminal, run:

```powershell
.\scripts\setup.ps1
ollama pull llama3.2
ollama pull nomic-embed-text
.\scripts\run_laila.ps1
```

5. Open **<http://127.0.0.1:8000>** in Edge or Chrome after Uvicorn reports that startup is complete. Keep the terminal open. Press Ctrl+C in the terminal to stop the server.

No Node.js, npm, or separate frontend build is needed. The frontend is served by the same Python process. The address above works on **your laptop after starting the server**; it is not a hosted website.

If scripts are blocked by your computer's PowerShell policy, you can run the equivalent commands without changing execution policy:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Do not overwrite an existing `.env` containing your configuration. Model downloads are still required for chat/retrieval.

### First five checks

- Ask **“Calculate 25% of 840.”** This uses the arithmetic tool and works even without Ollama.
- Open **Models & system**. Confirm Ollama is running and choose an installed local chat model.
- Ask **“Explain recursion with a short example.”** Confirm a real model answer streams in.
- Upload a TXT or PDF in **Documents**, wait for indexing, select **Ask about this**, and ask a question. Open the retrieved source excerpts below the answer.
- Ask a tool-capable model to create a note. Inspect the proposed content, then approve it. The note must not exist before approval. Models without tool support can still chat; use the Notes page to create notes manually.

## Model selection and offline behavior

`llama3.2` and `nomic-embed-text` are configurable initial defaults, not guaranteed to fit every machine or task. Model speed and quality depend on RAM, GPU, quantization, context size, and the installed model. Use Models & system to inspect your hardware. Choose a smaller model if generation is slow or runs out of memory.

- The **chat model** and **embedding model** are separate settings.
- A model must support native Ollama **tools** for model-directed tool selection, and **vision** for images.
- Cloud model names and remote model metadata are rejected. Laila only accepts a loopback Ollama URL.
- For defense in depth, set `OLLAMA_NO_CLOUD=1` in the environment of the **Ollama service itself**, then restart Ollama. The launch script sets it for child processes, but cannot change the environment of an already-running Ollama desktop service.
- Initial Python packages, Ollama, chat models, embedding models, and optional voice weights must be downloaded while online. Laila does not download anything during normal startup or inference.
- The UI uses no CDN fonts, scripts, remote images, analytics, or mandatory online services.
- After installation, test with the network disconnected. That on-device acceptance test remains necessary; it was not performed in the development environment.
- `OLLAMA_BASE_URL` defaults to `http://127.0.0.1:11434`. Change initial defaults in `.env`; once settings have been saved, the Settings page is authoritative for model and personality choices.

## Voice setup (optional installation, implemented local adapters)

### Speech to text

While online, install and download once:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-voice.txt
.\.venv\Scripts\python.exe scripts\download_voice_model.py --size base
```

The download script prints a local folder path. Paste it into **Settings → Local faster-whisper model folder** and save. The runtime uses CPU/int8 and `local_files_only=True`; it cannot silently fetch a missing model.

Click **Talk to Laila**, allow microphone access, speak, then click **Stop recording**. Transcription runs locally, inserts the text, sends it, and attempts to speak the response. **Cancel recording** discards the recording. Recording is limited to 60 seconds. Temporary uploaded audio is removed after transcription.

### Speech output

This release uses installed **Windows System.Speech voices**, rather than bundling a neural voice engine. There is no browser/cloud speech recognition fallback. The fixed PowerShell adapter receives JSON through stdin; user text is never interpolated into executable script code.

Choose a voice, speed, volume, and automatic speech in Settings. Each answer also has a **Speak** button, with **Stop speaking** during playback. Output is generated into a temporary local WAV, returned to the local browser, and removed from disk. Long answers are limited to the first 6,000 characters for speech.

Windows voice quality and language availability depend on installed voices. Windows audio and microphone behavior need testing on your own machine. Wake-word recognition is an interface only, not an active feature.

## Working with files and documents

**Documents** accepts PDF, DOCX, TXT, MD, CSV, JSON, and XLSX, up to 10 MB each. Text extraction preserves PDF page numbers and XLSX sheet names when available; DOCX pagination is not invented. Scanned PDFs require external OCR first.

Upload saves a local copy and attempts indexing. If the embedding model is missing, the upload stays available with an error status. Install/select the embedding model, then click **Index locally**. Changing the embedding model requires reindexing. Indexing limits include 500 PDF pages, 2 million extracted characters, and 2,000 chunks per document.

Retrieval uses overlapping chunks, embeddings generated by Ollama, and a FAISS cosine-similarity index. SQLite retains the vectors and metadata; FAISS is rebuilt in memory for a search. This favors simple, recoverable local storage over large-corpus performance. Similarity scores are **not confidence probabilities**. Retrieved excerpts are displayed for inspection even if a model fails to cite them accurately. The model can still misinterpret a source.

To let the agent find/read your existing files, add **dedicated folders** under **Settings → Approved folders**, one absolute path per line, for example `D:\LailaWorkspace`. File tools are read-only. Whole drives, home folders, system folders, credential stores, common secret files, and paths escaping approved roots are blocked. Reading a file does not automatically add it to the document index.

## Personal features

- **Conversations:** new, search, rename, pin, clear, delete, timestamps, streaming, stop, regenerate, continue, edit user message, copy, and Markdown/code rendering.
- Editing a user message removes later messages. Completed tool side effects such as notes are not undone.
- Regeneration may propose a fresh tool action. Read the approval details; completed actions are not rolled back.
- Image bytes are used for the current request and are **not stored** in history. Reattach an image to regenerate its response.
- **Study/Coding modes:** configurable model instructions. Ask for 2/8/16-mark answers, quizzes, flashcards, explanations, debugging, tests, or complexity. Their quality depends on the model; they are not separate trained models or a guaranteed grading engine.
- **Notes:** create, edit, search, delete.
- **Tasks:** create, edit, complete/reopen, delete, priority, due date. Due dates do not trigger notifications in v0.1.
- **Memory:** explicitly entered preferences only; view, edit, delete, clear, disable. No silent extraction of long-term preferences. Conversation history is saved separately.
- **Data analysis:** CSV, record-array JSON, and first-sheet XLSX; up to 50,000 rows/200 columns (XLSX also has the extraction row limit). Row preview, missing values, numeric statistics, exact-value filtering, grouping, aggregation, sorting, correlations, and a local canvas bar chart. No generated code execution, arbitrary query language, or ML training.

## Security and privacy boundaries

Laila binds to `127.0.0.1` and checks loopback peers, Host, Origin, cross-site fetch metadata, and a per-process token for mutations. It serves no permissive CORS policy. The UI disables raw Markdown HTML and remote image rendering. These controls are not a replacement for OS account security: another process running as you can access your local files and local server.

Agent tools use validated input schemas, a maximum of four model turns and six tool calls per turn. Read-only tools run automatically inside approved boundaries. Note/task creation pauses for approval, tied to stored arguments; replaying an approval cannot execute it twice. Dangerous tools and host code execution are disabled. There is no hidden terminal command feature.

Data is **not encrypted by Laila**. Protect your Windows account and use device/disk encryption when needed. The `data/` directory contains chats, notes, tasks, explicit memories, uploaded documents, vectors, and tool audit records. Tool audit records may contain private arguments and results; they are local application data, not telemetry. Deleting a chat also deletes its tool records, but leaves separately created notes/tasks intact. Deleting a document removes its original and index; excerpts already saved in chats remain until those chats are removed. SQLite/OS deletion is not guaranteed forensic erasure.

**Back up:** stop Laila and copy the complete `data/` directory. The Settings export downloads chat/notes/tasks/memory JSON, not uploaded originals, vectors, or a full restorable backup. Image/audio input is not retained. Never share your populated `data/` folder casually.

## Development and testing

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Tests use temporary databases. Ollama fixtures are confined to `tests/`; production always uses the real local HTTP provider. See `docs/VALIDATION.md` for what was actually tested. `requirements-tested.txt` records the development environment's resolved package versions for reproducibility, not a universal Windows lockfile.

Optional browser test (starts an isolated local server on port 18000 with disposable data):

```powershell
.\.venv\Scripts\python.exe -m pip install playwright
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe tests\browser_smoke.py
```

Select the `.venv` Python interpreter in VS Code. The included launch configuration supports the Python debugger. Production/local use should launch a **single worker**; in-memory generation cancellation and approval activity are scoped to one process.

## Troubleshooting

| Symptom | What to check |
|---|---|
| Ollama offline | Open Ollama or run `ollama serve`; verify `ollama list`. |
| Selected model missing | Pull the model while online, then choose it in Models & system. |
| Document indexing error | Check embedding model, disk/RAM, file encoding and extracted text; retry indexing. |
| Model doesn't call tools | Choose a model whose Ollama metadata advertises tools; manual Notes/Tasks still work. |
| Image unsupported | Choose an installed vision-capable model; a text-only model cannot inspect images. |
| No extractable PDF text | OCR the scanned PDF externally, then upload the searchable copy. |
| Slow responses or timeouts | Use a smaller local model, close other apps, shorten input, reduce context. |
| Microphone denied | Allow microphone for `http://127.0.0.1:8000` in browser/site settings. |
| Voice setup unavailable | Install optional STT dependencies/weights; use Windows for the System.Speech adapter. |
| Port 8000 already used | Stop the other Laila process, or run Uvicorn with another loopback port and open that URL. |
| Settings rejected | Correct invalid paths/numbers; wait for ongoing chat/indexing to finish. |
| Dependency installation fails | Use 64-bit Python 3.11/3.12, check network and wheel availability. |

## Architecture and next increments

`frontend → FastAPI API → Agent → LLMProvider/OllamaProvider`, with modular local tools, SQLite memory and FAISS retrieval. See [architecture](docs/ARCHITECTURE.md). Planned increments are explicit in [feature status](docs/FEATURE_STATUS.md): semantic long-term memory, interactive learning widgets, sandboxed execution, reminders, improved vision continuity, Piper voices, and wake-word detection.

## References

Implementation references checked during development:

- Ollama chat API: <https://docs.ollama.com/api/chat>
- Ollama embeddings API: <https://docs.ollama.com/api/embed>
- FastAPI lifespan: <https://fastapi.tiangolo.com/advanced/events/>
- FastAPI streaming: <https://fastapi.tiangolo.com/advanced/stream-data/>
- faster-whisper local inference: <https://github.com/SYSTRAN/faster-whisper>
- Ollama cloud-disable setting: <https://github.com/ollama/ollama/blob/main/envconfig/config.go>
- Windows local WAV synthesis: <https://learn.microsoft.com/en-us/dotnet/api/system.speech.synthesis.speechsynthesizer.setoutputtowavefile?view=netframework-4.8.1>

MIT license for this source code. Third-party software and model weights retain their own licenses. No model weights are included in this ZIP.
