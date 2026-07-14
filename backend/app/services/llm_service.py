"""Unified LLM service abstraction layer.

Supports two backends:
- Claude (Anthropic Messages API)
- Tongyi/Qwen (DashScope OpenAI-compatible endpoint)
"""
import json
import re
import asyncio
from typing import Optional
import httpx
from app.config import settings
from app.utils.helpers import logger

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds
REQUEST_TIMEOUT = 60.0  # seconds


class LLMService:
    """Unified async client for LLM providers."""

    def __init__(self):
        self.provider = settings.LLM_PROVIDER.lower()
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def chat(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.3,
    ) -> str:
        """Send a prompt to the configured LLM and return the text response."""
        if self.provider == "claude":
            return await self._call_claude(prompt, system_prompt, temperature)
        elif self.provider == "tongyi":
            return await self._call_tongyi(prompt, system_prompt, temperature)
        else:
            raise ValueError(f"Unknown LLM provider: {self.provider}")

    async def chat_json(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.3,
    ) -> dict:
        """Send a prompt and parse the response as JSON.

        Handles markdown-fenced JSON blocks and retries on parse failure.
        """
        response_text = await self.chat(prompt, system_prompt, temperature)
        return self._extract_json(response_text)

    # ------------------------------------------------------------------
    # Claude backend
    # ------------------------------------------------------------------
    async def _call_claude(
        self, prompt: str, system_prompt: str, temperature: float
    ) -> str:
        """Call Anthropic Messages API."""
        if not settings.CLAUDE_API_KEY:
            raise RuntimeError("CLAUDE_API_KEY is not configured")

        client = await self._get_client()
        headers = {
            "x-api-key": settings.CLAUDE_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        body = {
            "model": settings.CLAUDE_MODEL,
            "max_tokens": 4096,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            body["system"] = system_prompt

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=body,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data["content"][0]["text"]
                elif resp.status_code == 429:
                    last_error = f"Claude rate-limited (429)"
                    logger.warning(last_error)
                elif resp.status_code >= 500:
                    last_error = f"Claude server error ({resp.status_code})"
                    logger.warning(last_error)
                else:
                    last_error = f"Claude API error ({resp.status_code}): {resp.text}"
                    logger.error(last_error)
                    raise RuntimeError(last_error)
            except httpx.TimeoutException:
                last_error = "Claude request timed out"
                logger.warning(last_error)

            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                await asyncio.sleep(delay)

        raise RuntimeError(f"Claude API call failed after {MAX_RETRIES} retries: {last_error}")

    # ------------------------------------------------------------------
    # Tongyi / DashScope backend (OpenAI-compatible)
    # ------------------------------------------------------------------
    async def _call_tongyi(
        self, prompt: str, system_prompt: str, temperature: float
    ) -> str:
        """Call Tongyi/Qwen via DashScope OpenAI-compatible endpoint."""
        if not settings.TONGYI_API_KEY:
            raise RuntimeError("TONGYI_API_KEY is not configured")

        client = await self._get_client()
        headers = {
            "Authorization": f"Bearer {settings.TONGYI_API_KEY}",
            "Content-Type": "application/json",
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        body = {
            "model": settings.TONGYI_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 4096,
        }

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = await client.post(
                    "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                    headers=headers,
                    json=body,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data["choices"][0]["message"]["content"]
                elif resp.status_code == 429:
                    last_error = "Tongyi rate-limited (429)"
                    logger.warning(last_error)
                elif resp.status_code >= 500:
                    last_error = f"Tongyi server error ({resp.status_code})"
                    logger.warning(last_error)
                else:
                    last_error = f"Tongyi API error ({resp.status_code}): {resp.text}"
                    logger.error(last_error)
                    raise RuntimeError(last_error)
            except httpx.TimeoutException:
                last_error = "Tongyi request timed out"
                logger.warning(last_error)

            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                await asyncio.sleep(delay)

        raise RuntimeError(f"Tongyi API call failed after {MAX_RETRIES} retries: {last_error}")

    # ------------------------------------------------------------------
    # JSON extraction helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_json(text: str) -> dict:
        """Extract a JSON object from LLM response text.

        Handles:
        - Pure JSON
        - Markdown-fenced JSON blocks (```json ... ```)
        - Leading/trailing text
        """
        if not text:
            raise ValueError("Empty response from LLM")

        text = text.strip()

        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code fence
        fence_patterns = [
            r"```json\s*([\s\S]*?)\s*```",
            r"```\s*([\s\S]*?)\s*```",
        ]
        for pattern in fence_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    return json.loads(match.group(1).strip())
                except json.JSONDecodeError:
                    continue

        # Try to find the outermost {...} as a last resort
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start != -1 and brace_end > brace_start:
            try:
                return json.loads(text[brace_start: brace_end + 1])
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Failed to parse JSON from LLM response: {text[:200]}...")


# Singleton instance
llm_service = LLMService()
