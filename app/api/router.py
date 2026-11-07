from fastapi import APIRouter

from regmind.app.api.routes import (
    tasks,
)
from regmind.app.api.routes import audit, changes, circulars, departments, health, obligations, policy, switch

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(circulars.router)
api_router.include_router(obligations.router)
api_router.include_router(tasks.router)
api_router.include_router(departments.router)
api_router.include_router(policy.router)
api_router.include_router(changes.router)
api_router.include_router(audit.router)
api_router.include_router(switch.router)

__all__ = ["api_router"]
