import json
import httpx
from app.core.config import OLLAMA_URL
from app.llm.base import LLMProvider, LLMError


class OllamaProvider(LLMProvider):
    def __init__(self, base_url=OLLAMA_URL, transport=None):
        self.base_url, self.transport = base_url, transport

    def client(self, timeout=180):
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout, connect=4),
            trust_env=False,
            transport=self.transport,
        )

    async def request(self, method, path, body=None, timeout=180):
        try:
            async with self.client(timeout) as client:
                r = await client.request(method, path, json=body)
                r.raise_for_status()
                data = r.json()
                if data.get("error"):
                    raise LLMError(str(data["error"])[:500])
                return data
        except httpx.ConnectError as exc:
            raise LLMError(
                "Please start Ollama to use Laila’s local AI engine."
            ) from exc
        except httpx.TimeoutException as exc:
            raise LLMError(
                "Ollama timed out. Try a smaller model or shorter context."
            ) from exc
        except httpx.HTTPStatusError as exc:
            try:
                detail = exc.response.json().get("error", "Ollama request failed")
            except ValueError:
                detail = "Ollama request failed"
            raise LLMError(str(detail)[:500]) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMError("Invalid response from the local Ollama service.") from exc

    async def models(self):
        return (await self.request("GET", "/api/tags", timeout=5)).get("models", [])

    async def show(self, model):
        info = await self.request("POST", "/api/show", {"model": model}, timeout=15)
        if info.get("remote_host") or info.get("remote_model"):
            raise LLMError(
                "Cloud models are disabled. Select a locally installed model."
            )
        return info

    async def complete(self, model, messages, options, tools=None):
        body = {
            "model": model,
            "messages": messages,
            "options": options,
            "stream": False,
        }
        if tools:
            body["tools"] = tools
        return await self.request("POST", "/api/chat", body)

    async def stream(self, model, messages, options, tools=None):
        body = {
            "model": model,
            "messages": messages,
            "options": options,
            "stream": True,
        }
        if tools:
            body["tools"] = tools
        try:
            async with self.client() as client:
                async with client.stream("POST", "/api/chat", json=body) as r:
                    if r.is_error:
                        await r.aread()
                        try:
                            detail = r.json().get("error", "Ollama request failed")
                        except ValueError:
                            detail = "Ollama request failed"
                        raise LLMError(str(detail)[:500])
                    async for line in r.aiter_lines():
                        if not line.strip():
                            continue
                        event = json.loads(line)
                        if event.get("error"):
                            raise LLMError(str(event["error"])[:500])
                        yield event
        except httpx.ConnectError as exc:
            raise LLMError(
                "Please start Ollama to use Laila’s local AI engine."
            ) from exc
        except httpx.TimeoutException as exc:
            raise LLMError(
                "Ollama timed out. Try a smaller model or shorter context."
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMError("The local model connection was interrupted.") from exc

    async def embed(self, model, texts):
        await self.show(model)
        return (
            await self.request(
                "POST",
                "/api/embed",
                {"model": model, "input": texts, "truncate": False},
            )
        )["embeddings"]
