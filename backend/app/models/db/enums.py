from enum import StrEnum


class RiskProfile(StrEnum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


class AssetClass(StrEnum):
    IPO = "ipo"
    ESTABLISHED = "established"
    PRIVATE = "private"


class ResearchSignal(StrEnum):
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"


class AgentRunFlow(StrEnum):
    RESEARCH = "research"
    PORTFOLIO = "portfolio"


class AgentRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class PendingPositionStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class RebalanceTriggerKind(StrEnum):
    MACRO_EVENT = "macro_event"
    LOCKUP_EXPIRY = "lockup_expiry"
    EARNINGS_DATE = "earnings_date"
    DRIFT_THRESHOLD = "drift_threshold"
    CUSTOM = "custom"


class NotificationKind(StrEnum):
    REBALANCE_TRIGGER = "rebalance_trigger"
    RUN_COMPLETE = "run_complete"
    OTHER = "other"
