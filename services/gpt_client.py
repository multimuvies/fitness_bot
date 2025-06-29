"""services/gpt_client.py — единая точка работы с OpenAI ChatCompletion"""

from __future__ import annotations

import asyncio
import openai
from typing import Any, Mapping

from config import settings

openai.api_key = settings.OPENAI_API_KEY


async def chat_json(prompt: str, temperature: float = 0.2, *, timeout: int | None = None) -> dict | None:
    """Отправляет `prompt` модели GPT и пытается распарсить JSON-ответ.

    Возвращает dict или None при ошибке.
    """
    try:
        resp = await openai.ChatCompletion.acreate(
            model=settings.GPT_MODEL,
            temperature=temperature,
            timeout=timeout or settings.GPT_TIMEOUT,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        return resp.choices[0].message.json_loads()
    except Exception:
        return None


async def chat_text(prompt: str, *, temperature: float = 0.6, timeout: int | None = None) -> str:
    """Отправляет `prompt` и возвращает текстовый ответ модели (str)."""
    resp = await openai.ChatCompletion.acreate(
        model=settings.GPT_MODEL,
        temperature=temperature,
        timeout=timeout or settings.GPT_TIMEOUT,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content.strip()
