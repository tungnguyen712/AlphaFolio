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
    BACKTEST = "backtest"


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
    # Price-watch triggers (fires_at IS NULL — evaluated by the price-polling loop)
    PRICE_BELOW = "price_below"
    PRICE_ABOVE = "price_above"
    # Fires the day after an earnings_date trigger to check actual vs estimate
    EARNINGS_BEAT_CHECK = "earnings_beat_check"


class NotificationKind(StrEnum):
    REBALANCE_TRIGGER = "rebalance_trigger"
    RUN_COMPLETE = "run_complete"
    OTHER = "other"
    PRICE_ALERT = "price_alert"
    EARNINGS_RESULT = "earnings_result"
    WATCH_REMINDER = "watch_reminder"
