from __future__ import annotations

import os
import re
from dataclasses import dataclass

import httpx


@dataclass
class APIConfig:
    name: str
    url: str
    key: str | None
    model: str | None = None


def build_api_configs(
    gemini_model: str | None = None,
    groq_model: str | None = None,
    ollama_model: str | None = None,
) -> list[dict]:
    gemini_key = os.getenv("GEMINI_API_KEY")
    groq_key = os.getenv("GROQ_API_KEY")
    ollama_url = os.getenv("OLLAMA_API_URL")
    g_model = gemini_model or os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite-preview")
    q_model = groq_model or os.getenv("GROQ_MODEL", "moonshotai/kimi-k2-instruct-0905")
    o_model = ollama_model or os.getenv("OLLAMA_MODEL", "llama3.1")

    configs: list[dict] = []
    if gemini_key:
        configs.append(
            {
                "name": "Gemini",
                "url": (
                    f"https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{g_model}:generateContent?key={gemini_key}"
                ),
                "key": gemini_key,
                "model": g_model,
            }
        )
    if groq_key:
        configs.append(
            {
                "name": "Groq",
                "url": "https://api.groq.com/openai/v1/chat/completions",
                "key": groq_key,
                "model": q_model,
            }
        )
    if ollama_url:
        configs.append(
            {
                "name": "Ollama",
                "url": f"{ollama_url}/v1/chat/completions",
                "key": "ollama",
                "model": o_model,
            }
        )
    return configs


async def request_provider_text(
    client: httpx.AsyncClient,
    config: dict,
    system_prompt: str,
    user_prompt: str,
    timeout: float = 15.0,
    temperature: float | None = None,
) -> str | None:
    try:
        if config["name"] == "Gemini":
            resp = await client.post(
                config["url"],
                json={
                    "system_instruction": {"parts": [{"text": system_prompt}]},
                    "contents": [
                        {"role": "user", "parts": [{"text": user_prompt}]}
                    ],
                },
                timeout=timeout,
            )
        else:
            payload: dict = {
                "model": config.get("model", "llama-3.3-70b-versatile"),
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }
            if temperature is not None:
                payload["temperature"] = temperature
            resp = await client.post(
                config["url"],
                headers={"Authorization": f"Bearer {config['key']}"},
                json=payload,
                timeout=timeout,
            )

        if resp.status_code != 200:
            return None

        if config["name"] == "Gemini":
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as err:
        print(f"Provider {config['name']} request failed: {err}")
        return None


def parse_entity_csv(raw_text: str, source_text: str) -> list[str]:
    normalized_source = source_text.lower()
    candidates = re.split(r"[,，\n]", raw_text.strip())
    cleaned: list[str] = []
    seen: set[str] = set()
    for entity in candidates:
        c = entity.strip().lower()
        if not c or c == "none":
            continue
        if c not in normalized_source:
            continue
        if c in seen:
            continue
        cleaned.append(c)
        seen.add(c)
    return cleaned


async def extract_entities_with_llm(
    client: httpx.AsyncClient,
    text: str,
    *,
    extraction_prompt_template: str,
    api_configs: list[dict],
) -> list[str]:
    prompt = extraction_prompt_template.replace("{text}", text)
    sys_prompt = (
        "You extract literal entities from text and return a comma-separated list only."
    )
    for config in api_configs:
        if not config.get("key"):
            continue
        raw = await request_provider_text(
            client=client,
            config=config,
            system_prompt=sys_prompt,
            user_prompt=prompt,
            timeout=15.0,
            temperature=0,
        )
        if not raw:
            continue
        try:
            parsed = parse_entity_csv(raw, text)
            if parsed:
                return parsed
        except Exception as err:
            print(f"Entity extraction via {config['name']} failed: {err}")
            continue
    return []
