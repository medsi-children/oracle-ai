import asyncio
from contextlib import suppress

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import settings
from app.services.scheduler import run_daily_morning_scheduler, run_weekly_reports_scheduler
from app.web.shop import router as shop_router

app = FastAPI(title=settings.app_name, version="0.1.0")
app.include_router(api_router, prefix=settings.api_v1_prefix)
app.include_router(shop_router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
morning_scheduler_task: asyncio.Task | None = None
weekly_reports_scheduler_task: asyncio.Task | None = None


@app.on_event("startup")
async def start_morning_scheduler() -> None:
    global morning_scheduler_task, weekly_reports_scheduler_task
    if settings.daily_morning_scheduler_enabled:
        morning_scheduler_task = asyncio.create_task(run_daily_morning_scheduler())
    if settings.weekly_reports_scheduler_enabled:
        weekly_reports_scheduler_task = asyncio.create_task(run_weekly_reports_scheduler())


@app.on_event("shutdown")
async def stop_morning_scheduler() -> None:
    for task in (morning_scheduler_task, weekly_reports_scheduler_task):
        if task is None:
            continue
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}
