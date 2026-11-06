"""
Allowed values used everywhere: database, API, agent tools.
This is the single source of truth. Change a value here and it changes everywhere.
"""

from enum import Enum


class CircularKind(str, Enum):
    master = "master"
    amendment = "amendment"


class ObligationCategory(str, Enum):
    technical = "technical"
    business = "business"
    prohibitive = "prohibitive"
    governance = "governance"
    informational = "informational"


class UrgencyTier(str, Enum):
    urgent = "urgent"
    recurring = "recurring"
    conditional = "conditional"


class TaskStatus(str, Enum):
    open = "open"
    ongoing = "ongoing"
    paused = "paused"
    done = "done"
    complete = "complete"
    deprecated = "deprecated"