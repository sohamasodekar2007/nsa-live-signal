"""Core data models using dataclasses for type safety."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from core.enums import SignalType, PositionType, MarketRegime


@dataclass
class Tick:
    """Real-time tick data."""
    symbol: str
    ltp: float
    volume: int = 0
    bid: float = 0.0
    ask: float = 0.0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    prev_close: float = 0.0
    change: float = 0.0
    change_pct: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def spread(self) -> float:
        return self.ask - self.bid if self.bid > 0 else 0.0


@dataclass
class Candle:
    """OHLCV candle data."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    
    @property
    def body_size(self) -> float:
        return abs(self.close - self.open)
    
    @property
    def is_bullish(self) -> bool:
        return self.close > self.open


@dataclass
class Signal:
    """Trading signal with full context."""
    symbol: str
    signal_type: SignalType
    confidence: float
    entry_price: float
    stop_loss: float
    targets: List[float] = field(default_factory=list)
    regime: MarketRegime = MarketRegime.UNKNOWN
    reasoning: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def risk_reward(self) -> float:
        if not self.targets or self.stop_loss == self.entry_price:
            return 0.0
        risk = abs(self.entry_price - self.stop_loss)
        reward = abs(self.targets[0] - self.entry_price)
        return reward / risk if risk > 0 else 0.0


@dataclass 
class Position:
    """Active position tracking."""
    symbol: str
    position_type: PositionType
    quantity: int
    entry_price: float
    current_price: float
    stop_loss: float
    target: Optional[float] = None
    unrealized_pnl: float = 0.0
    entry_time: datetime = field(default_factory=datetime.now)
    
    def update_price(self, price: float):
        self.current_price = price
        if self.position_type == PositionType.LONG:
            self.unrealized_pnl = (price - self.entry_price) * self.quantity
        else:
            self.unrealized_pnl = (self.entry_price - price) * self.quantity


@dataclass
class MarketSnapshot:
    """Full market state for a symbol."""
    symbol: str
    tick: Optional[Tick] = None
    candles_1m: List[Candle] = field(default_factory=list)
    candles_5m: List[Candle] = field(default_factory=list)
    last_update: datetime = field(default_factory=datetime.now)
