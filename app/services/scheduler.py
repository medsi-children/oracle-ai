from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.config import settings
from app.services.daily_tasks import send_morning_case_to_all_users
from app.services.weekly import send_weekly_reports_to_all_users

logger = logging.getLogger(__name__)


def morning_timezone() -> ZoneInfo:
    try:
        return ZoneInfo(settings.daily_morning_timezone)
    except ZoneInfoNotFoundError:
        logger.warning("Unknown daily morning timezone: %s", settings.daily_morning_timezone)
        return ZoneInfo("UTC")


def seconds_until_next_morning_run(now: datetime | None = None) -> float:
    tz = morning_timezone()
    current = now.astimezone(tz) if now is not None else datetime.now(tz)
    target = current.replace(
        hour=settings.daily_morning_hour,
        minute=settings.daily_morning_minute,
        second=0,
        microsecond=0,
    )
    if target <= current:
        target += timedelta(days=1)
    return max(1.0, (target - current).total_seconds())


def seconds_until_next_weekly_report(now: datetime | None = None) -> float:
    tz = morning_timezone()
    current = now.astimezone(tz) if now is not None else datetime.now(tz)
    weekday = max(0, min(6, settings.weekly_reports_weekday))
    target = current.replace(
        hour=settings.weekly_reports_hour,
        minute=settings.weekly_reports_minute,
        second=0,
        microsecond=0,
    )
    days_ahead = (weekday - current.weekday()) % 7
    if days_ahead:
        target += timedelta(days=days_ahead)
    if target <= current:
        target += timedelta(days=7)
    return max(1.0, (target - current).total_seconds())


async def run_daily_morning_scheduler() -> None:
    while True:
        await asyncio.sleep(seconds_until_next_morning_run())
        try:
            sent = await send_morning_case_to_all_users()
            logger.info("Daily morning question sent to %s users", sent)
        except Exception:
            logger.exception("Daily morning question failed")


async def run_weekly_reports_scheduler() -> None:
    while True:
        await asyncio.sleep(seconds_until_next_weekly_report())
        try:
            sent = await send_weekly_reports_to_all_users()
            logger.info("Weekly ETHOS reports sent to %s users", sent)
        except Exception:
            logger.exception("Weekly ETHOS reports failed")
