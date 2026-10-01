# Laila 0.2.0 validation

Date: 2026-09-29. Environment: Linux, Python 3.12. Windows is the delivery target.

## Completed

27 backend tests passed against isolated temporary databases. This includes the original 21 tests and six new tests covering profile persistence/opt-out/deletion/export, timezone grouping, planner completion, study totals and review dates, narrow tool routing, calculator validation, desktop approval/replay/revocation, plan approval, and direct desktop launch proposals without model inference.

Live Chromium browser smoke testing against a real local server passed for calculator chat and regeneration; notes, tasks, memory, settings, upload and dataset analysis; profile save; planner add/complete; study log and totals; desktop page rendering; mobile viewport without horizontal overflow. No JavaScript page errors were observed. Desktop and mobile screenshots were inspected. Reminder controls were adjusted to stack on small screens.

Python compilation and JavaScript syntax checks passed. The application uses actual local database and API paths in these tests. Model calls use explicit test fixtures, and Windows launch tests replace the OS-launch function. Production code does not import these fixtures.

## Limits

- No real Ollama model inference or speed benchmark was run here.
- Windows app launching, desktop shortcut creation, microphone recording, faster-whisper and Windows speech require testing on the user's laptop.
- Browser reminders are opt-in and require an open tab and awake laptop. Browser scheduling can delay them. Background delivery, phone connectivity/control and independent Android inference are not implemented.
- No full security audit, Windows installer certification, or long-running load test was performed.
- The test client emitted one httpx deprecation warning; all tests passed.

## Check on the laptop

1. Back up while stopped, update in place, install requirements, and restart using UPGRADE_START_HERE.md.
2. Check old chats still exist. Save About me, restart, and check it persists.
3. Ask a profile-related question, then disable profile use and verify the next new conversation is no longer supplied that profile. Old chat messages can still contain previously shared information.
4. Add a block a few minutes ahead. Opt in to reminders, keep the tab open, and check its in-app banner.
5. Add a trusted app target. Request a launch, reject it, and verify it does not launch. Request again and approve. Verify a duplicate approval does not launch twice.
6. Ask an ordinary explanation, request Python addition code, calculate 25% of 840, and stop a long answer.
7. Test existing voice controls if the optional package and model are configured.

See tests/test_personal.py and tests/browser_smoke.py for executable checks.
