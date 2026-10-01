"""Optional live UI test: pip install playwright; playwright install chromium.
Run: python tests/browser_smoke.py (starts an isolated server with temporary data).
Uses real local API and arithmetic, not a simulated UI or model response.
"""

import asyncio, os, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 1000})
        page.set_default_timeout(10000)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.goto("http://127.0.0.1:18000")
        await page.locator("#model-badge").filter(has_text="Ollama").wait_for()
        await page.screenshot(
            path=str(Path(tempfile.gettempdir()) / "laila-desktop.png"), full_page=True
        )
        await page.locator("#prompt").fill("Calculate 25% of 840.")
        await page.locator("#send").click()
        await page.locator(".message.assistant .message-content").filter(
            has_text="210"
        ).wait_for()
        await page.locator("#stop").wait_for(state="hidden")
        await page.locator(".message-actions button").filter(
            has_text="Regenerate"
        ).click()
        await page.locator("#stop").wait_for(state="hidden")
        assert await page.locator(".message.assistant").count() == 1
        await page.locator('[data-page="notes"]').click()
        await page.locator("#add-note").click()
        await page.locator("#editor [name=title]").fill("UI smoke note")
        await page.locator("#editor [name=content]").fill(
            "Stored through the real local API."
        )
        await page.locator("#editor button[type=submit]").click()
        await page.get_by_role("heading", name="UI smoke note").wait_for()
        await page.locator('[data-page="tasks"]').click()
        await page.locator("#add-task").click()
        await page.locator("#editor [name=title]").fill("UI smoke task")
        await page.locator("#editor button[type=submit]").click()
        await page.get_by_text("Mark complete", exact=True).click()
        await page.get_by_text("Reopen", exact=True).wait_for()
        await page.locator('[data-page="memory"]').click()
        await page.locator("#add-memory").click()
        await page.locator("#editor [name=content]").fill("Test memory")
        await page.locator("#editor button[type=submit]").click()
        await page.get_by_text("Test memory", exact=True).wait_for()
        await page.locator('[data-page="settings"]').click()
        await page.locator("#settings-form [name=temperature]").fill("0.3")
        await page.get_by_role("button", name="Save settings", exact=True).click()
        await page.get_by_text("Settings saved", exact=True).wait_for()
        await page.locator('[data-page="documents"]').first.click()
        await page.locator("#file-input").set_input_files(
            {
                "name": "sample.csv",
                "mimeType": "text/csv",
                "buffer": b"team,score\nA,10\nA,20\nB,30",
            }
        )
        await page.get_by_role("heading", name="sample.csv").wait_for()
        await page.get_by_text("Analyze data", exact=True).click()
        await page.locator("#editor [name=group_by]").fill("team")
        await page.locator("#editor [name=value_column]").fill("score")
        await page.locator("#editor button[type=submit]").click()
        await page.get_by_role("heading", name="3 rows · 2 columns").wait_for()
        await page.locator("#chart").wait_for()
        await page.screenshot(
            path=str(Path(tempfile.gettempdir()) / "laila-data.png"), full_page=True
        )
        await page.locator('[data-page="profile"]').click()
        await page.locator('#profile-form [name="goals"]').fill(
            "Build Laila and study Python"
        )
        await page.get_by_role("button", name="Save profile", exact=True).click()
        await page.get_by_text("Profile saved", exact=True).wait_for()
        await page.locator('[data-page="today"]').click()
        await page.locator('#plan-form [name="title"]').fill("Practice Python")
        await page.locator('#plan-form button[type="submit"]').click()
        await page.get_by_role("heading", name="Practice Python", exact=True).wait_for()
        await page.locator("#plan-items").get_by_role(
            "button", name="Mark complete"
        ).click()
        await page.locator("#plan-items").get_by_role(
            "button", name="Reopen"
        ).wait_for()
        await page.locator('#study-form [name="subject"]').fill("Python")
        await page.locator('#study-form [name="topic"]').fill("Loops")
        await page.locator('#study-form button[type="submit"]').click()
        await page.get_by_role("heading", name="Loops", exact=True).wait_for()
        await page.get_by_role("heading", name="25 minutes", exact=True).wait_for()
        await page.locator("#workspace-page").evaluate("e => e.scrollTop = 0")
        await page.screenshot(path="/tmp/laila-personal-desktop.png", full_page=True)
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.screenshot(path="/tmp/laila-personal-mobile.png", full_page=True)
        assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        await page.locator("#menu").click()
        await page.locator('[data-page="desktop"]').click()
        await page.get_by_role(
            "heading", name="Your desktop, with your permission."
        ).wait_for()
        await page.locator("#menu").click()
        await page.locator("#new-chat").click()
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.screenshot(
            path=str(Path(tempfile.gettempdir()) / "laila-mobile.png"), full_page=True
        )
        assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        await page.locator("#menu").click()
        await page.locator(".sidebar.open").wait_for()
        assert not errors, errors
        print(
            "UI smoke passed: chat, regenerate, notes, tasks, memory, settings, upload, dataset chart, profile, planner, study logs, desktop page and mobile layout. No JavaScript errors."
        )
        await browser.close()


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="laila-browser-") as folder:
        server = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "18000",
                "--no-access-log",
            ],
            cwd=Path(__file__).resolve().parents[1],
            env={
                **os.environ,
                "LAILA_DATA_DIR": folder,
                "OLLAMA_BASE_URL": "http://127.0.0.1:19999",
            },
        )
        try:
            for _ in range(100):
                try:
                    urllib.request.urlopen("http://127.0.0.1:18000", timeout=1)
                    break
                except OSError:
                    time.sleep(0.1)
            asyncio.run(main())
        finally:
            server.terminate()
            server.wait(timeout=10)
