from enum import StrEnum


class RegistrationStatus(StrEnum):
    YES = "yes"
    NO = "no"
    LIKELY = "likely"
    UNKNOWN = "unknown"


class ExtractionStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIAL = "partial"


class SourceType(StrEnum):
    URL = "url"
    PASTED_TEXT = "pasted_text"
    MANUAL = "manual"


class SourceStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ComparisonStatus(StrEnum):
    DRAFT = "draft"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ScoreDetailStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class PropertyType(StrEnum):
    WG_ROOM = "wg_room"
    APARTMENT = "apartment"
    STUDIO = "studio"
    HOUSE = "house"
    OTHER = "other"
