"""Core enums and constants for the trading engine."""

from enum import Enum


class SignalType(Enum):
    """Trading signal types."""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class MarketRegime(Enum):
    """Market regime classifications."""
    TREND = "TREND"
    RANGE = "RANGE"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    UNKNOWN = "UNKNOWN"


class TimeFrame(Enum):
    """Supported timeframes."""
    ONE_MIN = "1m"
    FIVE_MIN = "5m"
    FIFTEEN_MIN = "15m"
    THIRTY_MIN = "30m"
    ONE_HOUR = "1h"
    ONE_DAY = "1d"


class PositionType(Enum):
    """Position types."""
    LONG = "LONG"
    SHORT = "SHORT"
    CLOSED = "CLOSED"


class TradeStatus(Enum):
    """Trade execution status."""
    PENDING = "PENDING"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"
