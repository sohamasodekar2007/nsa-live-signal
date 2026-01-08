"""Thread-safe snapshot store for real-time market data."""

import threading
from datetime import datetime
from typing import Dict, Optional, List
from dataclasses import dataclass, field


@dataclass
class StockSnapshot:
    """Immutable snapshot of stock state."""
    symbol: str
    ltp: float = 0.0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    prev_close: float = 0.0
    volume: int = 0
    change: float = 0.0
    change_pct: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


class SnapshotStore:
    """Thread-safe store for latest market snapshots."""
    
    def __init__(self):
        self._store: Dict[str, StockSnapshot] = {}
        self._lock = threading.RLock()
    
    def update(self, symbol: str, **kwargs) -> None:
        """Update snapshot for a symbol (thread-safe write)."""
        with self._lock:
            existing = self._store.get(symbol)
            if existing:
                # Merge updates
                data = {
                    'symbol': symbol,
                    'ltp': kwargs.get('ltp', existing.ltp),
                    'open': kwargs.get('open', existing.open),
                    'high': kwargs.get('high', existing.high),
                    'low': kwargs.get('low', existing.low),
                    'prev_close': kwargs.get('prev_close', existing.prev_close),
                    'volume': kwargs.get('volume', existing.volume),
                    'change': kwargs.get('change', existing.change),
                    'change_pct': kwargs.get('change_pct', existing.change_pct),
                    'bid': kwargs.get('bid', existing.bid),
                    'ask': kwargs.get('ask', existing.ask),
                    'timestamp': datetime.now()
                }
            else:
                data = {'symbol': symbol, 'timestamp': datetime.now(), **kwargs}
            
            self._store[symbol] = StockSnapshot(**data)
    
    def get(self, symbol: str) -> Optional[StockSnapshot]:
        """Get snapshot (lock-free read)."""
        return self._store.get(symbol)
    
    def get_ltp(self, symbol: str) -> float:
        """Quick LTP access."""
        snap = self._store.get(symbol)
        return snap.ltp if snap else 0.0
    
    def get_all(self) -> Dict[str, StockSnapshot]:
        """Get copy of all snapshots."""
        return self._store.copy()
    
    def get_symbols(self) -> List[str]:
        """Get all tracked symbols."""
        return list(self._store.keys())
    
    def bulk_update(self, updates: Dict[str, Dict]) -> None:
        """Batch update multiple symbols."""
        with self._lock:
            for symbol, data in updates.items():
                self.update(symbol, **data)


# Singleton
_store: Optional[SnapshotStore] = None

def get_snapshot_store() -> SnapshotStore:
    global _store
    if _store is None:
        _store = SnapshotStore()
    return _store
