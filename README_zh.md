# AI-RPG-Engine

[English](./README.md) | [简体中文](./README_zh.md)

一个由大语言模型驱动的模块化RPG引擎，内置RAG持久化记忆。

本引擎专为**任何桌上角色扮演游戏（TTRPG）**设计——所有属性、规则、提示词和机制都由模组定义，前端会根据后端 schema 动态渲染。

### 🎮 不止跑团：视觉小说与Galgame

由于引擎完全**数据驱动（schema-driven）**，它不仅限于传统跑团。只需修改 `module.json` 和提示词，就能无缝变身为动态**视觉小说 / Galgame 引擎**：

## 🎮 在线试玩
无需任何配置，直接在浏览器中体验引擎效果：
👉 **[立即试玩](https://mytools-cyj.pages.dev/vtt)**

## 架构

```
backend/
├── main.py                    # FastAPI 应用入口
├── requirements.txt
├── tools.json                 # LLM 工具调用定义（Gemini / Groq）
├── engine/                    # 核心引擎包
│   ├── models.py              # 模组 schema（属性条、术语等）
│   ├── module_loader.py       # 自动发现并加载 modules/
│   ├── memory.py              # RAG 会话记忆，实体索引
│   ├── providers.py           # 多 AI 提供商抽象层
│   └── dice.py                # 通用骰子（NdM±K）
└── modules/                   # 即插即用 TTRPG 模组
		├── coc_alone_against_flames/
		│   ├── module.json        # 模组元数据、schema、术语
		│   ├── content.md         # 冒险内容（章节、NPC、物品）
		│   └── prompts.md         # 系统提示词、护栏、实体提示词
		└── dnd5e_goblin_cave/
				├── module.json
				├── content.md
				└── prompts.md

frontend/
├── package.json
└── src/
		└── pages/
				└── VTTPage.tsx        # 基于 schema 的 RPG 会话界面
```

## 模组系统

每个模组是 `backend/modules/` 下的一个文件夹，包含：

| 文件 | 作用 |
|------|------|
| `module.json` | ID、名称、系统、术语、游戏 schema（属性条、属性、骰子） |
| `content.md` | 冒险内容，作为 AI 世界知识 |
| `prompts.md` | 提示词模板（如 BASE_SYSTEM_PROMPT、GUARDRAIL_SYSTEM_PROMPT 等） |

### module.json 示例

```json
{
	"id": "my-module-id",
	"name": "我的冒险",
	"system": "我的 TTRPG 系统",
	"description": "模块选择器中的简介。",
	"terminology": {
		"gm_name": "守密人",
		"gm_short": "KP",
		"player_name": "玩家",
		"welcome":           { "zh": "……", "en": "..." },
		"ready":             { "zh": "……", "en": "..." },
		"thinking":          { "zh": "……", "en": "..." },
		"no_response":       { "zh": "……", "en": "..." },
		"input_placeholder": { "zh": "……", "en": "..." },
		"enter_room":        { "zh": "……", "en": "..." },
		"death_message":     { "zh": "……", "en": "..." }
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

### 提示词占位符

prompts.md 模板可用这些占位符（运行时自动替换）：

| 占位符 | 含义 |
|-------------|-------|
| `{language}` | "zh" 或 "en" |
| `{module_name}` | 模组显示名 |
| `{module_content}` | content.md 全文 |
| `{state_format}` | 匹配游戏 schema 的自动生成 JSON 模板 |

## API 接口

| 方法 | 路径 | 说明 |
|--------|------|-------------|
| `GET` | `/api/modules` | 获取所有可用模组 |
| `GET` | `/api/modules/{id}/schema` | 获取完整模组 schema |
| `POST` | `/api/room/create` | 创建房间（user_token, module_id） |
| `POST` | `/api/room/verify` | 验证/重连（返回模组 schema） |
| `POST` | `/api/room/leave` | 离开并销毁房间 |
| `GET` | `/api/room/state` | 获取通用游戏状态 |
| `GET` | `/api/room/history` | 获取对话历史 |
| `GET` | `/api/room/status` | 活跃房间数 |
| `POST` | `/api/chat` | 发送玩家消息 |
| `GET` | `/api/roll` | 投骰子 |
| `POST` | `/api/game/restart` | 重置游戏状态 |
| `POST` | `/api/awaken` | 健康检查/唤醒后端 |

## 快速上手

### 后端

```bash
cd backend
pip install -r requirements.txt
# 设置环境变量（或用 .env 文件）：
#   GEMINI_API_KEY=...
#   GROQ_API_KEY=...
uvicorn main:app --reload
```

### 前端

```bash
cd frontend
npm install
# .env 里设置 VITE_VTT_API_BASE_URL（如 http://localhost:8000）
npm run dev
```

## 添加新模组

1. 新建文件夹：`backend/modules/my_new_module/`
2. 添加 `module.json`，定义 schema（属性条、属性、术语）
3. 添加 `content.md`，写入冒险文本
4. 添加 `prompts.md`，模板可用 `{language}`、`{module_name}`、`{module_content}`、`{state_format}`
5. 重启后端，模组会自动加载并出现在前端选择器

## 已内置模组

| 模组 | 系统 | 简介 |
|--------|--------|-------------|
| Alone Against the Flames | 克苏鲁的呼唤 7版 | 1920 年代 Emberhead 的单人恐怖冒险 |
| The Goblin Cave | 龙与地下城 5e | 剑湾新手地下城探索 |


### 起源
本项目由 mytools-cyj.pages.dev 站点内置的《克苏鲁的呼唤》AI 引擎抽象重构而来。
