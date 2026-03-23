from enum import Enum


class RequestType(str, Enum):
    DEEP_DIVE = "deep_dive"
    LITERATURE_REVIEW = "literature_review"
    IDEA_EXPLORATION = "idea_exploration"
    FACT_CHECK = "fact_check"


class RequestStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ReviewAction(str, Enum):
    APPROVE = "approve"
    COMMENT = "comment"
    FOLLOW_UP = "follow_up"
    DELETE = "delete"


class OutputStatus(str, Enum):
    UNCHECKED = "unchecked"
    APPROVED = "approved"
    DELETED = "deleted"
