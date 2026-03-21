from __future__ import annotations

from pydantic import BaseModel, Field


class LocalizedText(BaseModel):
    """A text value with per-language variants."""
    zh: str = ""
    en: str = ""

    def get(self, language: str) -> str:
        return getattr(self, language, None) or self.en


class BarDefinition(BaseModel):
    """A numeric stat rendered as a progress bar (HP, SAN, MP …)."""
    key: str
    max_key: str
    label: str
    color: str = "#4caf50"


class Terminology(BaseModel):
    """UI labels & narrative names that vary by game system."""
    gm_name: str = "Game Master"
    gm_short: str = "GM"
    player_name: str = "Player"
    welcome: LocalizedText = Field(default_factory=lambda: LocalizedText(zh="欢迎", en="Welcome"))
    ready: LocalizedText = Field(default_factory=lambda: LocalizedText(zh="准备就绪", en="Ready"))
    thinking: LocalizedText = Field(default_factory=lambda: LocalizedText(zh="思考中", en="Thinking"))
    no_response: LocalizedText = Field(default_factory=lambda: LocalizedText(zh="没有回应", en="No response"))
    input_placeholder: LocalizedText = Field(default_factory=lambda: LocalizedText(zh="你要做什么？", en="What will you do?"))
    enter_room: LocalizedText = Field(default_factory=lambda: LocalizedText(zh="进入房间", en="Enter Room"))
    death_message: LocalizedText = Field(default_factory=lambda: LocalizedText(
        zh="你的角色已经死亡。请重新开始游戏。",
        en="Your character has died. Please restart the game.",
    ))


class GameSchema(BaseModel):
    """Defines the stat-sheet structure for a TTRPG module."""
    bars: list[BarDefinition] = Field(default_factory=list)
    attributes: list[str] = Field(default_factory=list)
    has_inventory: bool = True
    default_dice: str = "1d20"


class ModuleDefinition(BaseModel):
    """Complete definition of a loadable TTRPG module."""
    id: str
    name: str
    system: str
    description: str = ""
    terminology: Terminology = Field(default_factory=Terminology)
    game_schema: GameSchema = Field(default_factory=GameSchema)
    content: str = ""
    prompts: dict[str, str] = Field(default_factory=dict)

    def generate_state_template(self) -> str:
        """Build the JSON template the AI should output in [STATE] blocks."""
        parts: list[str] = []
        for bar in self.game_schema.bars:
            parts.append(f'"{bar.key}": number')
            parts.append(f'"{bar.max_key}": number')
        if self.game_schema.attributes:
            attr_parts = ", ".join(f'"{a}": number' for a in self.game_schema.attributes)
            parts.append(f'"attributes": {{ {attr_parts} }}')
        if self.game_schema.has_inventory:
            parts.append('"inventory": ["item1", "item2"]')
        return "{ " + ", ".join(parts) + " }"

    def generate_current_state_text(self, game_state: dict) -> str:
        """Build the [Current State] line injected into the system prompt."""
        if not game_state:
            return ""
        parts: list[str] = []
        for bar in self.game_schema.bars:
            val = game_state.get(bar.key, "--")
            max_val = game_state.get(bar.max_key, "--")
            parts.append(f"{bar.label}: {val}/{max_val}")
        attrs = game_state.get("attributes", {})
        if attrs and self.game_schema.attributes:
            attr_strs = [f"{a}: {attrs.get(a, '--')}" for a in self.game_schema.attributes]
            parts.append("Attrs(" + ", ".join(attr_strs) + ")")
        if self.game_schema.has_inventory:
            inv = game_state.get("inventory", [])
            parts.append(f"Inventory: {inv}")
        return "\n[Current State] " + ", ".join(parts) if parts else ""
