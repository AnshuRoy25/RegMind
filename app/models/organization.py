import uuid
from enum import StrEnum

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class EmployeeRole(StrEnum):
    ADMIN = "admin"
    COMPLIANCE_OFFICER = "compliance_officer"
    COE_APPROVER = "coe_approver"
    DEPARTMENT_APPROVER = "department_approver"
    ENGINEER = "engineer"
    MEMBER = "member"


class Organization(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    employees: Mapped[list["Employee"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )


class Employee(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "employees"
    __table_args__ = (UniqueConstraint("org_id", "email", name="uq_employees_org_email"),)

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[EmployeeRole] = mapped_column(
        String(32), default=EmployeeRole.MEMBER, nullable=False
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    organization: Mapped["Organization"] = relationship(back_populates="employees")
    identities: Mapped[list["EmployeePlatformIdentity"]] = relationship(
        back_populates="employee", cascade="all, delete-orphan"
    )


class EmployeePlatformIdentity(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "employee_platform_identities"
    __table_args__ = (
        UniqueConstraint("employee_id", "platform", name="uq_identity_employee_platform"),
        UniqueConstraint("platform", "platform_user_id", name="uq_identity_platform_user"),
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(32), default="discord", nullable=False)
    platform_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    username: Mapped[str] = mapped_column(String(200), default="", nullable=False)

    employee: Mapped["Employee"] = relationship(back_populates="identities")

