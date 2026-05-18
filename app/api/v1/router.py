from fastapi import APIRouter

from app.api.v1 import (
    admin,
    assessments,
    cases,
    marketplace,
    messages,
    telegram,
    users,
)

api_router = APIRouter()

api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(assessments.router, prefix="/assessments", tags=["assessments"])
api_router.include_router(cases.router, prefix="/cases", tags=["cases"])
api_router.include_router(marketplace.router, prefix="/marketplace", tags=["marketplace"])
api_router.include_router(messages.router, prefix="/messages", tags=["messages"])
api_router.include_router(telegram.router, prefix="/telegram", tags=["telegram"])
api_router.include_router(users.router, prefix="/users", tags=["users"])

@api_router.post("/daily/send-morning-case", tags=["daily"])
async def trigger_morning_case():
    """Trigger the daily morning question manually; the app scheduler runs it at 10:00."""
    from app.services.daily_tasks import send_morning_case_to_all_users
    result = await send_morning_case_to_all_users()
    return {"status": "ok", "sent_to": result}


@api_router.post("/weekly/send-reports", tags=["weekly"])
async def trigger_weekly_reports():
    """Trigger weekly ETHOS reports manually."""
    from app.services.weekly import send_weekly_reports_to_all_users

    result = await send_weekly_reports_to_all_users()
    return {"status": "ok", "sent_to": result}
