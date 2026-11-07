﻿"""
The single place that decides which services the agent tools talk to.

Tools do:   from app.agents.gateway import services
and call:   await services.tasks.get("TSK-001")

USE_FAKE_SERVICES=true  -> in-memory fakes (default until Postgres is ready)
USE_FAKE_SERVICES=false -> Aayush's real services in app/services/
"""

from dataclasses import dataclass

from regmind.app.agents.contracts import AuditService, CircularService, ObligationService, TaskService
from regmind.app.core.config import settings


@dataclass
class Services:
    circulars: CircularService
    obligations: ObligationService
    tasks: TaskService
    audit: AuditService


def _build() -> Services:
    if settings.use_fake_services:
        from regmind.app.agents import fakes
        return Services(fakes.circulars, fakes.obligations, fakes.tasks, fakes.audit)

    # Aayush: expose one instance of each service from these modules.
    from regmind.app.services.audit_service import audit_service
    from regmind.app.services.circular_service import circular_service
    from regmind.app.services.obligation_service import obligation_service
    from regmind.app.services.task_service import task_service
    return Services(circular_service, obligation_service, task_service, audit_service)


services = _build()

