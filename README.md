# AI-RPG-Engine

[English](./README.md) | [简体中文](./README_zh.md)

A modular AI-driven RPG engine powered by LLMs, featuring RAG-based consistent memory

Designed to support **any Tabletop RPG** — stats, attributes, prompts, and game mechanics are defined per-module, and the frontend dynamically renders based on the backend's schema.

### 🎮 Beyond TTRPGs: Visual Novels & Galgames

Because the engine is entirely **schema-driven**, it is not limited to traditional tabletop RPGs. By simply modifying the `module.json` and prompts, the engine seamlessly transforms into a dynamic **Visual Novel / Galgame Engine**:


## Architecture

```
backend/
├── main.py                    # FastAPI application entry point
├── requirements.txt
├── tools.json                 # LLM tool-calling definitions (Gemini / Groq)
├── engine/                    # Core engine package
│   ├── models.py              # Module schema (attributes, terminology, …)
│   ├── module_loader.py       # Discovers and loads modules from modules/
│   ├── memory.py              # RAG-based session memory with entity indexing
│   ├── providers.py           # Multi-provider AI abstraction (support Gemini, Groq for now)
│   └── dice.py                # Generic dice roller (NdM±K)
└── modules/                   # Drop-in module definitions
    ├── coc_alone_against_flames/
    │   ├── module.json        # Module metadata, schema & terminology
    │   ├── content.md         # Adventure content (sections, NPCs, items)
    │   └── prompts.md         # System prompt, guardrail & entity prompts
    └── dnd5e_goblin_cave/
        ├── module.json
        ├── content.md
        └── prompts.md

frontend/
├── package.json
└── src/
    └── pages/
        └── VTTPage.tsx        # Schema-driven RPG session UI
```

## Module System

Each module is a folder under `backend/modules/` containing:

| File | Purpose |
|------|---------|
| `module.json` | ID, name, system, terminology, game schema (bars, attributes, dice) |
| `content.md` | Adventure content fed to the AI as world knowledge |
| `prompts.md` | Prompt templates (`BASE_SYSTEM_PROMPT`, `GUARDRAIL_SYSTEM_PROMPT`, etc.) |

### module.json Schema

```json
{
  "id": "my-module-id",
  "name": "My Adventure",
  "system": "My TTRPG System",
  "description": "A short description shown in the module picker.",
  "terminology": {
    "gm_name": "Game Master",
    "gm_short": "GM",
    "player_name": "Player",
    "welcome":           { "zh": "…", "en": "…" },
    "ready":             { "zh": "…", "en": "…" },
    "thinking":          { "zh": "…", "en": "…" },
    "no_response":       { "zh": "…", "en": "…" },
    "input_placeholder": { "zh": "…", "en": "…" },
    "enter_room":        { "zh": "…", "en": "…" },
    "death_message":     { "zh": "…", "en": "…" }
  },
  "game_schema": {
    "bars": [
      { "key": "hp", "max_key": "max_hp", "label": "HP", "color": "#4caf50" }
    ],
    "attributes": ["STR", "DEX", "CON", "INT", "WIS", "CHA"],
    "has_inventory": true,
    "default_dice": "1d20"
  }
}
```

### Prompt Placeholders

Prompt templates in `prompts.md` can use these placeholders:

| Placeholder | Value |
|-------------|-------|
| `{language}` | `"zh"` or `"en"` |
| `{module_name}` | Module display name |
| `{module_content}` | Full content.md text |
| `{state_format}` | Auto-generated JSON template matching the game schema |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/modules` | List available modules |
| `GET` | `/api/modules/{id}/schema` | Get full module schema |
| `POST` | `/api/room/create` | Create room (`user_token`, `module_id`) |
| `POST` | `/api/room/verify` | Verify & reconnect (returns module schema) |
| `POST` | `/api/room/leave` | Leave and destroy room |
| `GET` | `/api/room/state` | Get generic game state |
| `GET` | `/api/room/history` | Get conversation history |
| `GET` | `/api/room/status` | Active room count |
| `POST` | `/api/chat` | Send player message |
| `GET` | `/api/roll` | Roll dice |
| `POST` | `/api/game/restart` | Reset game state |
| `POST` | `/api/awaken` | Health check / wake backend |

## Quick Start

### Backend

```bash
cd backend
pip install -r requirements.txt
# Set environment variables (or use a .env file):
#   GEMINI_API_KEY=...
#   GROQ_API_KEY=...
uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
# Set VITE_VTT_API_BASE_URL in .env (e.g. http://localhost:8000)
npm run dev
```

## Adding a New Module

1. Create a folder: `backend/modules/my_new_module/`
2. Add `module.json` with your system's schema (bars, attributes, terminology).
3. Add `content.md` with the adventure text.
4. Add `prompts.md` with prompt templates using `{language}`, `{module_name}`, `{module_content}`, and `{state_format}`.
5. Restart the backend — the module auto-loads and appears in the frontend module picker.

## Included Modules

| Module | System | Description |
|--------|--------|-------------|
| Alone Against the Flames | Call of Cthulhu 7e | Solo horror adventure in 1920s Emberhead |
| The Goblin Cave | D&D 5th Edition | Introductory dungeon crawl on the Sword Coast |


### Origin

This project is a modular generalization of the Call of Cthulhu (CoC) AI engine originally featured on mytools-cyj.pages.dev/vtt. It strips away hardcoded rules to provide a universal, schema-driven framework for any narrative RPG.