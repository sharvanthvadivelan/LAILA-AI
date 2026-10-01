> Updating an existing Laila installation? Follow **UPGRADE_START_HERE.md** first.

# Start Laila on your Windows laptop

This folder contains **Laila AI v0.1**, a first development release. It includes working application code, not just a design. Model inference and Windows audio still need testing on your machine.

1. Install **64-bit Python 3.11/3.12** and **Ollama**.
2. Open the extracted `LAILA-AI` folder in VS Code.
3. Open a PowerShell terminal in that folder.
4. Run:

```powershell
.\scripts\setup.ps1
ollama pull llama3.2
ollama pull nomic-embed-text
.\scripts\run_laila.ps1
```

5. Open **http://127.0.0.1:8000** after the terminal reports successful startup.
6. Try **“Calculate 25% of 840.”**, then a normal question to test Ollama.

For microphone and speech setup, follow the **Voice setup** section in `README.md`. For blocked scripts, use the equivalent Python commands there.

**21 automated tests and the live browser smoke test passed.** That does not replace testing actual models and Windows audio on your laptop.

- `README.md`: setup, voice, privacy, model choices, troubleshooting.
- `docs/FEATURE_STATUS.md`: what is implemented and what remains.
- `docs/VALIDATION.md`: evidence and your acceptance checklist.
- `docs/ARCHITECTURE.md`: project structure and request flow.

Downloads require internet initially. Normal chat is designed to use only local models after setup. No model weights are included in this archive.
