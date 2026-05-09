from uuid import UUID

from pydantic import BaseModel, Field, computed_field


class MessageCreate(BaseModel):
    telegram_id: int
    username: str | None = None
    first_name: str | None = None
    text: str = Field(min_length=1)
    source: str = "telegram"


class InlineKeyboardButton(BaseModel):
    text: str
    callback_data: str


class InlineKeyboardMarkup(BaseModel):
    inline_keyboard: list[list[InlineKeyboardButton]]


class ChatAnimationStep(BaseModel):
    text: str
    duration_ms: int = 2200
    parse_mode: str = "HTML"


class MessageResponse(BaseModel):
    user_id: UUID
    session_id: UUID
    reply: str
    mode: str = "support"
    token_delta: int = 0
    subjectivity_score: int | None = None
    reply_markup: InlineKeyboardMarkup | None = None
    intro_animation: list[ChatAnimationStep] | None = None

    @computed_field
    @property
    def reply_markup_json(self) -> str | None:
        if self.reply_markup is None:
            return None
        return self.reply_markup.model_dump_json()
