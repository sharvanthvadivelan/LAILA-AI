# Added in 0.2.0

- Explicit editable profile with chat opt-out.
- Dated planner, completion tracking, study logs, confidence and revision dates.
- Weekly totals based on recorded sessions; morning/evening chat prompts.
- Optional reminders inside an open browser tab only.
- Windows app/folder target list and single-use launch approvals.
- Direct exact-name desktop launch proposal without model inference.
- Desktop shortcut and inner/outer virtual-environment detection.
- Narrow tool routing and recoverable calculator errors.

Phone access/control, native background reminders and always-listening voice are not implemented.

## Original 0.1.0 feature notes

# Feature status — v0.1.0

“Implemented” means code and an accessible workflow exist. It does not mean every external dependency, Windows behavior, or real model output has been verified. Consult VALIDATION.md.

| Master-prompt area | This release |
|---|---|
| Local-first Windows app | FastAPI + same-origin HTML/CSS/JS; PowerShell setup/start scripts; no mandatory cloud. Windows execution needs on-device validation. |
| Ollama/provider abstraction | Model listing/selection, service check, local-model check, streaming and normal completion, options, timeouts and errors. Installation detection is PATH-based and reports uncertainty. |
| Personality | Editable system prompt; hidden `thinking` field is neither displayed nor stored. |
| Chat | Persistent history/search/pin/rename/delete/clear, timestamps, edit/truncate, regenerate, continue, stop, copy. |
| Response rendering | Local Markdown tables/lists/headings/quotes, Pygments syntax highlighting, language label and code copy. Math is plain model-provided notation; no dedicated math typesetter yet. |
| Voice input | Local faster-whisper adapter, microphone start/stop/cancel, temporary file cleanup, settings/download script. Requires optional packages/model; hardware untested here. |
| Voice output | Windows System.Speech adapter, voice/rate/volume, automatic/manual speech, playback stop. Windows-only in v0.1; no bundled Piper voice. |
| Wake word | Abstract interface only. No active wake-word listener. |
| Conversation/session memory | SQLite history; recent conversation context with a conservative character budget. No exact model tokenizer or automatic summarization. |
| Long-term memory | Explicit preference editor and disable/clear/delete controls. No automatic extraction or semantic preference index yet. |
| Semantic retrieval | Ollama local embeddings + FAISS over documents; durable vectors in SQLite. |
| Document formats | PDF/DOCX/TXT/MD/CSV/JSON/XLSX extraction, chunking, indexing, search, error status/retry/delete. Scanned-image OCR is not included. |
| Citations | Real retrieved snippets with filename/page/location. Model is instructed to use source labels; citation correctness is not guaranteed by the model. |
| Study/coding | Dedicated prompt modes; model can provide requested explanations, quizzes, code, tests and exam-answer formats. No deterministic grading, stored flashcard scheduler, or code runner. |
| Safe execution | Disabled-by-default executor extension point; no host Python/shell tool. A real sandbox is future work. |
| Tools | Validated modular registry for arithmetic, date/time, system info, file search/read/list, document search, notes/tasks and data analysis. Output schemas currently describe generic objects. |
| Agent orchestration | Route/activity classification, attached-document retrieval, bounded native tool-call/observation loop, re-evaluation, final response. Native tools require model capability. No durable multi-day plans. |
| Permissions | SAFE reads; stored CONFIRM proposals for note/task creation; atomic approval claim; DANGEROUS disabled. |
| Vision | PNG/JPEG/WEBP validation, size limits, model capability check, actual image bytes sent to Ollama. Image bytes not persisted. Real vision-model inference untested here. |
| Data analysis | Actual local descriptive statistics, missing values, exact filters, group/aggregate/sort, correlations and canvas chart. No general ML analysis/training yet. |
| Personal assistant | Notes/tasks CRUD, due dates, priorities, completion. No background reminders or notifications. No combined Today dashboard yet. |
| File assistant | Dedicated approved directory mechanism, read-only supported files, filename/limited text search, symlink boundary checks. No file organization/mutations. |
| System info | OS/CPU/RAM/Python/version/Ollama/models; NVIDIA GPU detection via fixed `nvidia-smi` invocation when available. Other GPUs may show not detected. |
| Database | Versioned schema initialization, SQLite transactions/WAL, relational cascades. Single local user; no login/users table needed. Future upgrades need explicit migrations. |
| Settings/privacy | Loopback-only networking, same-origin token protection, restricted uploads/paths, no CDN/telemetry, explicit memory, JSON export, local delete. At-rest encryption relies on OS. |
| Packaging | Source, tests, Windows scripts, VS Code launch config, README, environment example and MIT license. No binary installer or bundled model weights. |

## Recommended next increment

First validate this release on the target laptop: Ollama chat, indexing one real PDF, microphone transcription and Windows speech. Record RAM/GPU/model and timing. Fix any platform issues before adding more features. Then improve persistent attachments and semantic long-term memory, followed by interactive study features. Wake word, reminders and sandbox execution are independent future modules.
