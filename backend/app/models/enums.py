import enum


class ComplaintStatus(str, enum.Enum):
    pending_triage = "pending_triage"
    ready_to_commit = "ready_to_commit"
    committed = "committed"


class SeverityLevel(str, enum.Enum):
    critical = "Critical"
    major = "Major"
    minor = "Minor"
    not_assessed = "Not Assessed"


class PriorityLevel(str, enum.Enum):
    high = "High"
    medium = "Medium"
    low = "Low"
    not_assessed = "Not Assessed"


class ComplaintSource(str, enum.Enum):
    pharmacy = "Pharmacy"
    email = "Email"
    distributor = "Distributor"
    phone = "Phone"
    portal = "Portal"
    other = "Other"


class AuditActor(str, enum.Enum):
    ai = "ai"
    user = "user"


class ChatRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"
