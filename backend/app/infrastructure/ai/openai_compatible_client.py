import asyncio
import logging
from typing import Any

import httpx

from app.config.settings import Settings
from app.domain.errors import AiClientError, AiContextLengthError, AiNotConfiguredError

logger = logging.getLogger(__name__)


class OpenAiCompatibleClient:
    """Low-level client for an OpenAI compatible chat completions API."""

    _CONTEXT_MARKERS = ("context", "maximum", "too long", "token limit", "reduce the length")

    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._client = client

    async def complete_json(self, system_prompt: str, user_prompt: str) -> str:
        if not self._settings.ai_configured:
            raise AiNotConfiguredError("AI provider is not configured: set AI_BASE_URL, AI_API_KEY and AI_MODEL")

        url = f"{self._settings.ai_base_url.rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {self._settings.ai_api_key}"}
        payload: dict[str, Any] = {
            "model": self._settings.ai_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        if self._settings.ai_provider == "deepseek":
            payload["thinking"] = {"type": "enabled" if self._settings.ai_thinking else "disabled"}

        last_error = ""
        for attempt in range(1, self._settings.ai_max_retries + 1):
            try:
                response = await self._client.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=self._settings.ai_timeout,
                )
            except httpx.TimeoutException:
                last_error = "timeout"
                logger.warning("ai request timed out", extra={"attempt": attempt})
                await self._sleep(attempt)
                continue
            except httpx.HTTPError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                logger.warning("ai request failed", extra={"attempt": attempt, "error": last_error})
                await self._sleep(attempt)
                continue

            if response.status_code == httpx.codes.OK:
                return self._content(response)

            body = response.text[:500]
            if response.status_code in (httpx.codes.UNAUTHORIZED, httpx.codes.FORBIDDEN):
                raise AiClientError(f"AI provider rejected credentials (HTTP {response.status_code})")
            if self._is_context_error(response, body):
                raise AiContextLengthError(f"AI provider context limit exceeded (HTTP {response.status_code})")
            if response.status_code == httpx.codes.TOO_MANY_REQUESTS or response.status_code >= 500:
                last_error = f"HTTP {response.status_code}: {body}"
                logger.warning("ai provider is busy", extra={"attempt": attempt, "status": response.status_code})
                await self._sleep(attempt)
                continue
            raise AiClientError(f"AI provider returned HTTP {response.status_code}: {body}")

        raise AiClientError(f"AI request failed after retries: {last_error}")

    def _content(self, response: httpx.Response) -> str:
        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise AiClientError(f"AI provider returned unexpected payload: {exc}") from exc
        if not isinstance(content, str) or not content.strip():
            raise AiClientError("AI provider returned empty content")
        return content

    def _is_context_error(self, response: httpx.Response, body: str) -> bool:
        if response.status_code not in (httpx.codes.BAD_REQUEST, httpx.codes.REQUEST_ENTITY_TOO_LARGE, 422):
            return False
        lowered = body.lower()
        return any(marker in lowered for marker in self._CONTEXT_MARKERS)

    async def _sleep(self, attempt: int) -> None:
        await asyncio.sleep(min(2 ** (attempt - 1), 8))
