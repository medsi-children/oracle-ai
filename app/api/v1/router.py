from fastapi import APIRouter

from app.api.v1 import admin, assessments, cases, marketplace, messages, telegram, users

api_router = APIRouter()
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(messages.router, prefix="/messages", tags=["messages"])
api_router.include_router(cases.router, prefix="/cases", tags=["cases"])
api_router.include_router(assessments.router, prefix="/assessments", tags=["assessments"])
api_router.include_router(telegram.router, prefix="/telegram", tags=["telegram"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(marketplace.router, prefix="/marketplace", tags=["marketplace"])
