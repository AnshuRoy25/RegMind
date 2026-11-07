import uuid
from enum import StrEnum

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class SwitchAgentRole(StrEnum):
    INTAKE = "intake"
    PARSER = "parser"
    SPEC = "spec"
    ROUTER = "router"
    AUDITOR = "auditor"
    DEPARTMENT = "department"


class SwitchConnectionStatus(StrEnum):
    PENDING = "pending"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class SwitchWorkspace(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "switch_workspaces"

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    switch_tenant_id: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    switch_workspace_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    agents: Mapped[list["SwitchAgent"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    rooms: Mapped[list["SwitchRoom"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )


class SwitchRoom(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "switch_rooms"
    __table_args__ = (UniqueConstraint("org_id", "name", name="uq_switch_rooms_org_name"),)

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("switch_workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    switch_room_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    discord_channel_id: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), default="general", nullable=False)
    purpose: Mapped[str] = mapped_column(Text, default="", nullable=False)

    workspace: Mapped["SwitchWorkspace"] = relationship(back_populates="rooms")


class SwitchAgent(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "switch_agents"

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("switch_workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    switch_agent_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    role: Mapped[SwitchAgentRole] = mapped_column(String(32), nullable=False)
    chat_name: Mapped[str] = mapped_column(String(100), nullable=False)
    api_key_enc: Mapped[str] = mapped_column(Text, default="", nullable=False)
    connection_status: Mapped[SwitchConnectionStatus] = mapped_column(
        String(32), default=SwitchConnectionStatus.PENDING, nullable=False
    )
    addressing_policy: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    last_connected_at: Mapped[str] = mapped_column(String(64), default="", nullable=False)

    workspace: Mapped["SwitchWorkspace"] = relationship(back_populates="agents")


class SwitchEvent(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "switch_events"

    org_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    switch_agent_id: Mapped[str] = mapped_column(String(128), default="", nullable=False, index=True)
    room_id: Mapped[str] = mapped_column(String(128), default="", nullable=False, index=True)
    message_id: Mapped[str] = mapped_column(String(128), default="", nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    sender: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

