from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field

import httpx


@dataclass
class MemoryEntry:
    timestamp: int
    role: str
    content: str
    entities: list[str] = field(default_factory=list)


@dataclass
class SessionMemoryStore:
    timeline: dict[int, MemoryEntry] = field(default_factory=dict)
    entity_index: defaultdict[str, list[int]] = field(
        default_factory=lambda: defaultdict(list)
    )
    ordered_timestamps: list[int] = field(default_factory=list)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def add_memory(
        self, role: str, content: str, entities: list[str] | None = None
    ) -> int:
        memory_timestamp = time.time_ns()
        normalized = [e.strip().lower() for e in (entities or []) if e.strip()]
        entry = MemoryEntry(
            timestamp=memory_timestamp,
            role=role,
            content=content,
            entities=normalized,
        )
        async with self.lock:
            self.timeline[memory_timestamp] = entry
            self.ordered_timestamps.append(memory_timestamp)
            for entity in normalized:
                self.entity_index[entity].append(memory_timestamp)
        return memory_timestamp

    async def get_recent_messages(self, limit: int = 10) -> list[dict[str, str]]:
        async with self.lock:
            recent = self.ordered_timestamps[-limit:] if self.ordered_timestamps else []
            return [
                {"role": self.timeline[ts].role, "content": self.timeline[ts].content}
                for ts in recent
            ]

    async def match_keys_with_llm(
        self,
        client: httpx.AsyncClient,
        queried_entities: list[str],
        available_keys: list[str],
        *,
        entity_matching_prompt: str,
        request_fn,
        api_configs: list[dict],
    ) -> list[str]:
        if not available_keys or not queried_entities:
            return []

        prompt = entity_matching_prompt.replace(
            "{queried_entities}", str(queried_entities)
        ).replace("{available_keys}", str(available_keys))
        system_prompt = (
            "You are a precise entity matching system. "
            "Return a comma-separated list only."
        )

        for config in api_configs:
            if not config.get("key"):
                continue
            raw = await request_fn(
                client=client,
                config=config,
                system_prompt=system_prompt,
                user_prompt=prompt,
                timeout=10.0,
                temperature=0.0,
            )
            if raw:
                if raw.strip().upper() == "NONE":
                    return []
                matched = [k.strip().lower() for k in raw.split(",")]
                return [k for k in matched if k in available_keys]
        return []

    async def retrieve_memories_by_entities(
        self,
        client: httpx.AsyncClient,
        entities: list[str],
        limit: int = 6,
        *,
        entity_matching_prompt: str = "",
        request_fn=None,
        api_configs: list[dict] | None = None,
    ) -> list[MemoryEntry]:
        normalized = [e.strip().lower() for e in entities if e.strip()]
        if not normalized:
            return []

        async with self.lock:
            available_keys = list(self.entity_index.keys())

        ai_matched: list[str] = []
        if entity_matching_prompt and request_fn and api_configs:
            ai_matched = await self.match_keys_with_llm(
                client,
                normalized,
                available_keys,
                entity_matching_prompt=entity_matching_prompt,
                request_fn=request_fn,
                api_configs=api_configs,
            )

        final_keys = set(normalized + ai_matched)
        async with self.lock:
            matched_ts: set[int] = set()
            for entity in final_keys:
                matched_ts.update(self.entity_index.get(entity, []))
            sorted_ts = sorted(matched_ts)
            return [self.timeline[ts] for ts in sorted_ts[-limit:]]

    async def reset(self) -> None:
        async with self.lock:
            self.timeline.clear()
            self.entity_index.clear()
            self.ordered_timestamps.clear()


def build_memory_context(memories: list[MemoryEntry]) -> str:
    if not memories:
        return ""
    lines = [f"- [{m.role}] {m.content}" for m in memories]
    return "# Relevant Memories\n" + "\n".join(lines)


async def store_memory_from_text(
    client: httpx.AsyncClient,
    session_memory: SessionMemoryStore,
    role: str,
    content: str,
    entities: list[str] | None = None,
) -> int:
    return await session_memory.add_memory(role=role, content=content, entities=entities)
