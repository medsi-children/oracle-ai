import json
from datetime import UTC, datetime
from html import escape
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.assessment import Assessment
from app.models.case import Case
from app.models.message import Message
from app.models.news import NewsItem
from app.models.session import ConversationSession
from app.models.token import TokenLedgerEntry
from app.models.user import User
from app.schemas.message import ChatAnimationStep, InlineKeyboardButton, InlineKeyboardMarkup
from app.services.admin_tools import (
    format_admin_help,
    format_admin_success,
)
from app.services.admins import is_admin
from app.services.assessment import (
    analyze_implicit_signals,
    assessment_average_score,
    calculate_onboarding_initial_score,
    calculate_status,
    create_assessment,
)
from app.services.ai_agent import generate_ai_agent_reply
from app.services.battles import (
    BATTLE_ENTRY_OPTIONS,
    choose_battle_entry_fee,
    create_battle,
    finish_active_battle,
    generate_battle_topic,
    get_battle_by_id,
    get_latest_battle,
    join_waiting_battle,
)
from app.services.cases import create_custom_case, get_random_case
from app.services.daily_tasks import process_morning_case_response
from app.services.group_discussions import (
    DISCUSSION_ENTRY_OPTIONS,
    create_case_discussion,
    create_news_discussion,
    finish_discussion,
    format_discussion_prompt,
    get_discussion_by_id,
    get_latest_discussion,
    join_discussion,
)
from app.services.llm import SUPPORT_SYSTEM_PROMPT, clean_generated_text, openrouter_chat
from app.services.marketplace import buy_item, format_shop, user_owns_item_type
from app.services.news import create_custom_news_case, get_or_create_news_case
from app.services.phrasing import psycoins

ONBOARDING_CASE_COUNT = 7
GROUP_CHAT_TYPES = {"group", "supergroup"}
GAMEPLAY_COMMANDS = {
    "/battle",
    "/battlefee",
    "/joinbattle",
    "/finishbattle",
    "/case",
    "/news",
    "/finishdiscussion",
    "/finishcase",
    "/finishnews",
    "/stake",
    "/cancel",
    "/buy",
}
GAMEPLAY_CALLBACK_PREFIXES = (
    "playmode:",
    "stake:",
    "stake_other",
    "confirm:",
    "playcancel",
    "bfee:",
    "bfee_other:",
    "bjoin:",
    "bfinish:",
    "djoin:",
    "dfinish:",
)
GAME_ACTION_LABELS = {
    "battle": "баттл",
    "case": "разбор кейса",
    "news": "разбор новости",
}
GAME_MODE_LABELS = {
    "ai": "с ИИ-агентом",
    "human": "с человеком",
}
SOLO_RESULT_WIN_THRESHOLD = 62
