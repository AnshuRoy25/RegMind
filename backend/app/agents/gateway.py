"""
Gives the agent tools access to the database services.

Tools do:   from app.agents.gateway import services
and call:   await services.tasks.get("TSK-001")
"""

from dataclasses import dataclass

from app.agents.contracts import AuditService, CircularService, ObligationService, TaskService
from app.services.audit_service import audit_service
from app.services.circular_service import circular_service
from app.services.obligation_service import obligation_service
from app.services.task_service import task_service


@dataclass
class Services:
    circulars: CircularService
    obligations: ObligationService
    tasks: TaskService
    audit: AuditService


services = Services(circular_service, obligation_service, task_service, audit_service)