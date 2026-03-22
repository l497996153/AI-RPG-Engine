"""
AI-RPG-Engine — A generic, module-driven AI RPG engine.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from engine import (
    ModuleDefinition,
    SessionMemoryStore,
    build_memory_context,
    do_roll,
    store_memory_from_text,
)
from engine.module_loader import get_module, list_modules, load_all_modules, load_tools_config
from engine.providers import (
    build_api_configs,
    extract_entities_with_llm,
    request_provider_text,
)

load_dotenv()
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# ---------------------------------------------------------------------------
# Load modules & tools
# ---------------------------------------------------------------------------
MODULE_REGISTRY = load_all_modules()
tools_config = load_tools_config()
GEMINI_TOOLS = tools_config.get("GEMINI_TOOLS", [])
GROQ_TOOLS = tools_config.get("GROQ_TOOLS", [])

API_CONFIGS = build_api_configs()

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="AI-RPG-Engine")

ALLOWED_ORIGINS = os.getenv(
    "CORS_ORIGINS", "http://localhost:5173"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOWED_ORIGINS],
    allow_origin_regex=r"https://.*\.(app\.)?github\.dev",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Prompt rendering — uses simple string replacement so literal JSON braces
# in prompt templates are left untouched.
# ---------------------------------------------------------------------------
def render_prompt(template: str, **kwargs: str) -> str:
    for key, value in kwargs.items():
        template = template.replace("{" + key + "}", str(value))
    return template


# ---------------------------------------------------------------------------
# Room model — game_state is a generic dict driven by the module schema
# ---------------------------------------------------------------------------
@dataclass
class Room:
    room_id: str
    owner_token: str
    created_ns: int
    last_activity_ns: int
    module_id: str = ""
    player_dead: bool = False
    game_state: dict = field(default_factory=dict)


rooms: dict[str, Room] = {}
rag_memory_db: defaultdict[str, SessionMemoryStore] = defaultdict(SessionMemoryStore)
pending_rolls: dict[str, dict] = {}


def now_ns() -> int:
    return time.time_ns()


# ---------------------------------------------------------------------------
# State parsing — fully generic, reads whatever JSON the AI outputs in
# [STATE] and stores it in room.game_state
# ---------------------------------------------------------------------------
def parse_state(content: str, room: Room, session_id: str | None = None) -> str:
    state_match = re.search(r"\[STATE\]\s*(\{[\s\S]*\})", content)
    if state_match:
        try:
            state_obj = json.loads(state_match.group(1))
            if isinstance(state_obj, dict):
                room.game_state = state_obj
        except Exception as e:
            sid = session_id or "unknown"
            print(f"DEBUG: Failed to parse [STATE] JSON for session {sid}: {e}")
    return re.sub(r"\[STATE\][\s\S]*$", "", content).strip() if isinstance(content, str) else content


def extract_data(content: str, room: Room, session_id: str | None = None) -> dict[str, str | None]:
    if not isinstance(content, str):
        return {"narrative": "", "options": None}
    content = parse_state(content, room, session_id)
    narrative = ""
    options = None

    narrative_match = re.search(
        r"\[NARRATIVE\]([\s\S]*?)(?=\[OPTIONS\]|\[STATE\]|$)", content, re.IGNORECASE
    )
    if narrative_match:
        narrative = narrative_match.group(1).strip()

    options_match = re.search(
        r"\[OPTIONS\]([\s\S]*?)(?=\[STATE\]|$)", content, re.IGNORECASE
    )
    if options_match:
        options = options_match.group(1).strip()

    return {"narrative": narrative, "options": options}


def detect_death_in_text(text: str) -> tuple[bool, str]:
    if not text:
        return False, text
    cleaned = text
    detected = False
    try:
        new_cleaned = re.sub(
            r"(?im)^\s*DEATH_FLAG\s*[:=]\s*true\s*$\n?", "", cleaned
        )
        if new_cleaned != cleaned:
            cleaned = new_cleaned
            detected = True
    except Exception:
        return False, text
    return detected, cleaned


# ---------------------------------------------------------------------------
# Room lifecycle
# ---------------------------------------------------------------------------
INACTIVITY_NS = 10 * 60 * 1_000_000_000
MAX_ROOMS = int(os.getenv("MAX_ROOMS", "3"))


def is_room_expired(room: Room) -> bool:
    return now_ns() - room.last_activity_ns > INACTIVITY_NS


def cleanup_expired_rooms_once() -> None:
    expired = [rid for rid, room in rooms.items() if is_room_expired(room)]
    for rid in expired:
        rag_memory_db.pop(rid, None)
        pending_rolls.pop(rid, None)
        rooms.pop(rid, None)
        if DEBUG:
            print(f"DEBUG: Expired room {rid} removed.")


async def cleanup_expired_rooms_loop() -> None:
    while True:
        try:
            cleanup_expired_rooms_once()
        except Exception as e:
            print(f"ERROR: cleanup loop failed: {e}")
        await asyncio.sleep(30)


@app.on_event("startup")
async def startup_cleanup_task() -> None:
    asyncio.create_task(cleanup_expired_rooms_loop())


# ---------------------------------------------------------------------------
# Guardrail check — module-aware
# ---------------------------------------------------------------------------
async def check_guardrail(
    client: httpx.AsyncClient,
    message: str,
    language: str,
    module_def: ModuleDefinition,
    kp_context: str = "",
) -> tuple[bool, str]:
    guardrail_template = module_def.prompts.get("GUARDRAIL_SYSTEM_PROMPT", "")
    if not guardrail_template:
        return False, ""

    prompt_text = render_prompt(
        guardrail_template,
        language=language,
        module_name=module_def.name,
    )
    user_prompt_text = (
        f"{module_def.terminology.gm_short}'s Last Message: {kp_context}\n\n"
        f"Player's Current Input: {message}"
    )

    for config in API_CONFIGS:
        if not config.get("key"):
            continue
        result = await request_provider_text(
            client=client,
            config=config,
            system_prompt=prompt_text,
            user_prompt=user_prompt_text,
            timeout=10.0,
            temperature=0.0,
        )
        if result:
            upper = result.strip().upper()
            if upper == "PASS":
                return False, ""
            if upper.startswith("ROLL_REQUIRED:"):
                return True, result
            if upper.startswith("REJECT"):
                rejection = re.sub(r"(?i)^REJECT[:：]?\s*", "", result).strip()
                return True, rejection
            return True, result
    return False, ""


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    language: str = Field(default="zh")
    user_token: Optional[str] = Field(default=None)


class RoomRequest(BaseModel):
    user_token: str
    module_id: Optional[str] = Field(default=None)


class RoomActionRequest(BaseModel):
    room_id: str
    user_token: str


# ---------------------------------------------------------------------------
# Module listing & schema endpoints
# ---------------------------------------------------------------------------
@app.get("/api/modules")
async def get_modules():
    return {"status": "ok", "modules": list_modules()}


@app.get("/api/modules/{module_id}/schema")
async def get_module_schema(module_id: str):
    mod = get_module(module_id)
    if mod is None:
        raise HTTPException(status_code=404, detail="Module not found")
    return {
        "status": "ok",
        "module": {
            "id": mod.id,
            "name": mod.name,
            "system": mod.system,
            "description": mod.description,
            "terminology": mod.terminology.model_dump(),
            "game_schema": mod.game_schema.model_dump(),
        },
    }


# ---------------------------------------------------------------------------
# Chat endpoint — module-aware
# ---------------------------------------------------------------------------
@app.post("/api/chat")
async def chat(req: ChatRequest):
    session_id = req.session_id
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    room = rooms.get(session_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found. Please (re)join.")

    module_def = get_module(room.module_id)
    if module_def is None:
        raise HTTPException(status_code=500, detail="Module not found for this room.")

    term = module_def.terminology

    if getattr(room, "player_dead", False):
        death_msg = f"[NARRATIVE]\n{term.death_message.get(req.language)}"
        return {"content": death_msg}

    if is_room_expired(room):
        rag_memory_db.pop(session_id, None)
        rooms.pop(session_id, None)
        raise HTTPException(status_code=410, detail="Room expired due to inactivity.")

    if not req.user_token or req.user_token != room.owner_token:
        raise HTTPException(status_code=403, detail="You are not authorized for this room.")

    room.last_activity_ns = now_ns()

    session_memory = rag_memory_db[session_id]

    # Build system prompt from module prompts
    base_template = module_def.prompts.get("BASE_SYSTEM_PROMPT", "")
    state_format = module_def.generate_state_template()
    system_prompt = render_prompt(
        base_template,
        language=req.language,
        module_name=module_def.name,
        module_content=module_def.content,
        state_format=state_format,
    )
    state_text = module_def.generate_current_state_text(room.game_state)
    system_prompt += state_text

    async with httpx.AsyncClient() as client:
        recent_msgs = await session_memory.get_recent_messages(limit=1)
        last_kp_msg = ""
        for msg in reversed(recent_msgs):
            if msg["role"] == "assistant":
                last_kp_msg = msg["content"]
                break

        is_rejected, rejection_response = await check_guardrail(
            client, req.message, req.language, module_def, last_kp_msg
        )
        check = "Null"
        if is_rejected:
            if re.search(r"ROLL_REQUIRED", rejection_response, re.IGNORECASE):
                m = re.search(r"ROLL_REQUIRED\s*:?\s*(.*)", rejection_response, re.IGNORECASE)
                main_part = m.group(1).strip() if m else ""
                if "|" in main_part:
                    check, formula = [p.strip() for p in main_part.split("|", 1)]
                else:
                    check, formula = (main_part.strip() or "Check", module_def.game_schema.default_dice)

                roll_obj = do_roll(formula)
                if not roll_obj.get("error"):
                    pending_rolls[session_id] = roll_obj
                if session_id in rooms:
                    rooms[session_id].last_activity_ns = now_ns()
                if DEBUG:
                    print(f"DEBUG: ROLL_REQUIRED for session {session_id}: {rejection_response}")
            else:
                narrative = rejection_response
                await store_memory_from_text(client, session_memory, "user", req.message, [])
                await store_memory_from_text(client, session_memory, "assistant", narrative, [])
                if session_id in rooms:
                    rooms[session_id].last_activity_ns = now_ns()
                return {"narrative": narrative, "options": ""}

        if DEBUG:
            print(f"DEBUG: Message passed guardrail for session {session_id}")

        full_messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt}
        ]

        for msg in await session_memory.get_recent_messages(limit=10):
            full_messages.append({"role": msg["role"], "content": msg["content"]})

        current_user_msg = {"role": "user", "content": req.message}
        full_messages.append(current_user_msg)

        pending = pending_rolls.pop(session_id, None)
        if DEBUG:
            print(f"DEBUG: Pending roll for session {session_id}: {pending}")
        if pending:
            try:
                roll_json = json.dumps(pending, ensure_ascii=False)
            except Exception:
                roll_json = str(pending)
            full_messages.append({
                "role": "user",
                "content": (
                    f"CRITICAL UPDATE: A {check} check was rolled for the player's action. "
                    f"Result: {roll_json}. Use this result to resolve the action and continue."
                ),
            })
            await store_memory_from_text(client, session_memory, "system", f"Attached roll: {roll_json}", [])

        MAX_ITERATIONS = 100
        narrative = ""
        options = ""

        groq_model = None
        for c in API_CONFIGS:
            if c["name"] == "Groq":
                groq_model = c.get("model")
                break

        for config in API_CONFIGS:
            if not config.get("key"):
                continue
            try:
                content = ""
                for _itr in range(MAX_ITERATIONS):
                    headers: dict[str, str] = {}
                    if config["name"] == "Groq":
                        headers["Authorization"] = f"Bearer {config['key']}"

                    if config["name"] == "Gemini":
                        payload = {
                            "system_instruction": {
                                "parts": [
                                    {
                                        "text": (
                                            full_messages[0]["content"]
                                            if full_messages and full_messages[0]["role"] == "system"
                                            else system_prompt
                                        )
                                    }
                                ]
                            },
                            "contents": [
                                {
                                    "role": "user" if m["role"] == "user" else "model",
                                    "parts": [{"text": m["content"]}],
                                }
                                for m in full_messages
                                if m["role"] in ("user", "assistant")
                            ],
                            "tools": GEMINI_TOOLS,
                        }
                    elif config["name"] == "Groq":
                        payload = {
                            "model": groq_model or "llama-3.3-70b-versatile",
                            "messages": full_messages,
                            "tools": GROQ_TOOLS,
                            "tool_choice": "auto",
                        }
                    else:
                        payload = {
                            "model": config.get("model", "llama3.1"),
                            "messages": full_messages,
                            "tools": GROQ_TOOLS,
                            "tool_choice": "auto",
                        }

                    resp = await client.post(
                        config["url"],
                        headers=headers,
                        json=payload,
                        timeout=30.0,
                    )
                    if resp.status_code != 200:
                        print(f"WARN: {config['name']} returned {resp.status_code}: {resp.text[:200]}")
                        break

                    resp_json = resp.json()

                    if config["name"] == "Gemini":
                        part = resp_json["candidates"][0]["content"]["parts"][0]
                        if "functionCall" in part:
                            func_call = part["functionCall"]
                            tool_result_text = ""
                            if func_call["name"] == "store_memory_from_text":
                                parsed = extract_data(func_call["args"]["content"], room, session_id)
                                narrative = parsed.get("narrative") or func_call["args"]["content"]
                                options = parsed.get("options") or ""
                                await store_memory_from_text(
                                    client, session_memory, "assistant",
                                    narrative, func_call["args"].get("entities", []),
                                )
                                tool_result_text = "Memory stored successfully."
                            elif func_call["name"] == "retrieve_memories_by_entities":
                                entity_matching = module_def.prompts.get("ENTITY_MATCHING_PROMPT", "")
                                retrieved = await session_memory.retrieve_memories_by_entities(
                                    client,
                                    func_call["args"].get("entities", []),
                                    func_call["args"].get("limit", 6),
                                    entity_matching_prompt=entity_matching,
                                    request_fn=request_provider_text,
                                    api_configs=API_CONFIGS,
                                )
                                tool_result_text = build_memory_context(retrieved) or "No relevant memories found."
                            full_messages.append({"role": "assistant", "content": f"(I called tool {func_call['name']})"})
                            full_messages.append({"role": "user", "content": f"[tool execution result] {tool_result_text}\nPlease use the information above to continue the conversation."})
                            continue
                        elif "text" in part:
                            content = part["text"]
                            await store_memory_from_text(client, session_memory, "user", req.message, [])
                            parsed = extract_data(content, room, session_id)
                            narrative = parsed.get("narrative") or content
                            options = parsed.get("options") or ""
                            await store_memory_from_text(client, session_memory, "assistant", narrative, [])
                            break
                    else:
                        message = resp_json["choices"][0]["message"]
                        if message.get("tool_calls"):
                            func_call = message["tool_calls"][0]["function"]
                            args = json.loads(func_call["arguments"])
                            tool_result_text = ""
                            if func_call["name"] == "store_memory_from_text":
                                parsed = extract_data(args["content"], room, session_id)
                                narrative = parsed.get("narrative") or args["content"]
                                options = parsed.get("options") or ""
                                await store_memory_from_text(
                                    client, session_memory, "assistant",
                                    narrative, args.get("entities", []),
                                )
                                tool_result_text = "Memory stored successfully."
                            elif func_call["name"] == "retrieve_memories_by_entities":
                                entity_matching = module_def.prompts.get("ENTITY_MATCHING_PROMPT", "")
                                mems = await session_memory.retrieve_memories_by_entities(
                                    client,
                                    args.get("entities", []),
                                    args.get("limit", 6),
                                    entity_matching_prompt=entity_matching,
                                    request_fn=request_provider_text,
                                    api_configs=API_CONFIGS,
                                )
                                tool_result_text = build_memory_context(mems) if mems else "No relevant memories found."
                            full_messages.append({"role": "assistant", "content": f"(I called tool {func_call['name']})"})
                            full_messages.append({"role": "user", "content": f"[tool execution result] {tool_result_text}\nPlease use the information above to continue the conversation."})
                            continue
                        elif message.get("content"):
                            content = message["content"]
                            await store_memory_from_text(client, session_memory, "user", req.message, [])
                            parsed = extract_data(content, room, session_id)
                            narrative = parsed.get("narrative") or content
                            options = parsed.get("options") or ""
                            await store_memory_from_text(client, session_memory, "assistant", narrative, [])
                            break

                if session_id not in rooms:
                    return {"narrative": narrative, "options": options}
                if not content:
                    print(f"WARN: {config['name']} exhausted iterations without text response.")
                    continue

                detected, cleaned_content = detect_death_in_text(content)
                if detected:
                    rooms[session_id].player_dead = True
                    if DEBUG:
                        print(f"DEBUG: Marked room {session_id} as player_dead.")

                rooms[session_id].last_activity_ns = now_ns()
                return {"narrative": narrative, "options": options}
            except Exception as e:
                print(f"Provider {config['name']} failed: {e}")
                continue

    raise HTTPException(
        status_code=503,
        detail="All AI services are currently unavailable. Please try again later.",
    )


# ---------------------------------------------------------------------------
# Room management endpoints
# ---------------------------------------------------------------------------
@app.get("/api/room/state")
async def room_state(room_id: str, user_token: str) -> dict:
    cleanup_expired_rooms_once()
    room = rooms.get(room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.owner_token != user_token:
        raise HTTPException(status_code=403, detail="You are not authorized for this room")
    room.last_activity_ns = now_ns()

    return {
        "status": "ok",
        "room_id": room_id,
        "module_id": room.module_id,
        "state": room.game_state,
    }


@app.get("/api/room/history")
async def room_history(room_id: str, user_token: str) -> dict:
    cleanup_expired_rooms_once()
    room = rooms.get(room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.owner_token != user_token:
        raise HTTPException(status_code=403, detail="You are not authorized for this room")
    room.last_activity_ns = now_ns()

    sess = rag_memory_db.get(room_id)
    messages = []
    if sess is not None:
        async with sess.lock:
            for ts in sorted(sess.timeline.keys()):
                entry = sess.timeline[ts]
                messages.append({"role": entry.role, "content": entry.content})
    return {"status": "ok", "room_id": room_id, "messages": messages}


@app.get("/api/room/status")
async def room_status() -> dict[str, str]:
    cleanup_expired_rooms_once()
    active = len(rooms)
    return {
        "status": "ok",
        "active_rooms": str(active),
        "slots_remaining": str(MAX_ROOMS - active),
    }


@app.post("/api/room/create")
async def create_room(req: RoomRequest) -> dict:
    if DEBUG:
        print(f"DEBUG: Creating room for token {req.user_token}, module {req.module_id}")
    cleanup_expired_rooms_once()

    if len(rooms) >= MAX_ROOMS:
        raise HTTPException(
            status_code=429,
            detail=f"Maximum active rooms reached ({MAX_ROOMS}). Please try again later.",
        )

    module_id = req.module_id
    if not module_id:
        available = list(MODULE_REGISTRY.keys())
        module_id = available[0] if available else None
    if not module_id or get_module(module_id) is None:
        raise HTTPException(status_code=400, detail="Invalid or missing module_id")

    mod = get_module(module_id)
    room_id = uuid.uuid4().hex
    ts = now_ns()
    rooms[room_id] = Room(
        room_id=room_id,
        owner_token=req.user_token,
        created_ns=ts,
        last_activity_ns=ts,
        module_id=module_id,
    )
    _ = rag_memory_db[room_id]

    remain = str(MAX_ROOMS - len(rooms))
    return {
        "status": "ok",
        "room_id": room_id,
        "module_id": module_id,
        "slots_remaining": remain,
        "module_schema": {
            "id": mod.id,
            "name": mod.name,
            "system": mod.system,
            "description": mod.description,
            "terminology": mod.terminology.model_dump(),
            "game_schema": mod.game_schema.model_dump(),
        },
    }


@app.post("/api/room/leave")
async def leave_room(req: RoomActionRequest) -> dict[str, str]:
    room = rooms.get(req.room_id)
    if not room:
        return {"status": "ok", "message": "Room already closed."}
    if room.owner_token != req.user_token:
        raise HTTPException(status_code=403, detail="You are not authorized to leave this room.")
    rag_memory_db.pop(req.room_id, None)
    pending_rolls.pop(req.room_id, None)
    rooms.pop(req.room_id, None)
    if DEBUG:
        print(f"DEBUG: Room {req.room_id} left and cleared.")
    return {"status": "ok", "message": "Left room and cleared memory."}


@app.post("/api/room/verify")
async def verify_room(req: RoomActionRequest) -> dict:
    room = rooms.get(req.room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.owner_token != req.user_token:
        raise HTTPException(status_code=403, detail="Token does not match room owner")
    if is_room_expired(room):
        rag_memory_db.pop(req.room_id, None)
        rooms.pop(req.room_id, None)
        raise HTTPException(status_code=410, detail="Room expired")
    room.last_activity_ns = now_ns()

    mod = get_module(room.module_id)
    schema_data = None
    if mod:
        schema_data = {
            "id": mod.id,
            "name": mod.name,
            "system": mod.system,
            "description": mod.description,
            "terminology": mod.terminology.model_dump(),
            "game_schema": mod.game_schema.model_dump(),
        }
    return {
        "status": "ok",
        "message": "Room valid",
        "module_id": room.module_id,
        "module_schema": schema_data,
    }


@app.post("/api/game/restart")
async def restart_game(req: RoomActionRequest) -> dict[str, str]:
    room = rooms.get(req.room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.owner_token != req.user_token:
        raise HTTPException(status_code=403, detail="You are not authorized to restart this room.")
    if req.room_id in rag_memory_db:
        await rag_memory_db[req.room_id].reset()
    room.player_dead = False
    room.game_state = {}
    if DEBUG:
        print("DEBUG: Game restarted; memories cleared.")
    return {"status": "ok", "message": "Game restarted; memories cleared."}


# ---------------------------------------------------------------------------
# Dice roll endpoint
# ---------------------------------------------------------------------------
@app.get("/api/roll")
async def roll_dice(
    formula: str = "1d20",
    room_id: Optional[str] = None,
    user_token: Optional[str] = None,
):
    roll_obj = do_roll(formula)
    if "error" in roll_obj:
        return roll_obj
    if room_id:
        room = rooms.get(room_id)
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")
        if not user_token or user_token != room.owner_token:
            raise HTTPException(status_code=403, detail="Not authorized")
        if room_id in pending_rolls:
            existing = pending_rolls[room_id]
            return {"status": "ok", "total": existing.get("total"), "existing": True}
        pending_rolls[room_id] = roll_obj
        rooms[room_id].last_activity_ns = now_ns()
        return {"status": "ok", "total": roll_obj["total"]}
    return roll_obj


# ---------------------------------------------------------------------------
# Health / wake-up endpoint
# ---------------------------------------------------------------------------
@app.post("/api/awaken")
async def awaken_backend() -> dict[str, str]:
    if DEBUG:
        print("DEBUG: Backend awakened.")
    return {"status": "ok", "message": "Backend awakened successfully."}
