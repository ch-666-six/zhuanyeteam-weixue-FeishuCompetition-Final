from fastapi import APIRouter

from app.modules.assignments.api import management_router, router as assignments_router
from app.modules.growth.api import router as growth_router
from app.modules.identity.api import router as identity_router
from app.modules.sessions.api import router as sessions_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(identity_router)
api_router.include_router(assignments_router)
api_router.include_router(management_router)
api_router.include_router(growth_router)
api_router.include_router(sessions_router)
