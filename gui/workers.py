"""Background workers for zero-lag GUI updates - Using yfinance for reliable prices."""

import time
import yfinance as yf
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
from PyQt6.QtCore import QThread, pyqtSignal, QObject

from data.snapshot_store import get_snapshot_store, StockSnapshot


@dataclass 
class QuoteData:
    """Simple quote data."""
    symbol: str
    ltp: float = 0.0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    prev_close: float = 0.0
    change: float = 0.0
    change_pct: float = 0.0
    volume: int = 0


class PriceWorker(QThread):
    """
    Background worker for continuous price updates.
    Uses yfinance for reliable data fetching.
    """
    
    prices_updated = pyqtSignal(dict)  # {symbol: StockSnapshot}
    error_occurred = pyqtSignal(str)
    
    def __init__(self, symbols: List[str] = None, interval_ms: int = 3000):
        super().__init__()
        self._symbols = symbols or []
        self._interval = interval_ms / 1000.0
        self._running = True
        self._store = get_snapshot_store()
    
    def set_symbols(self, symbols: List[str]):
        """Update the symbols to track."""
        self._symbols = symbols.copy()
    
    def add_symbol(self, symbol: str):
        """Add a symbol to track."""
        if symbol not in self._symbols:
            self._symbols.append(symbol)
    
    def run(self):
        """Main worker loop - fetch prices continuously."""
        while self._running:
            try:
                if self._symbols:
                    snapshots = self._fetch_prices_batch()
                    if snapshots:
                        self.prices_updated.emit(snapshots)
                
            except Exception as e:
                self.error_occurred.emit(str(e))
            
            time.sleep(self._interval)
    
    def _fetch_prices_batch(self) -> Dict[str, StockSnapshot]:
        """Fetch prices for all symbols using yfinance."""
        snapshots = {}
        
        try:
            # Batch fetch with yfinance
            symbols_str = " ".join(self._symbols)
            tickers = yf.Tickers(symbols_str)
            
            for symbol in self._symbols:
                try:
                    ticker = tickers.tickers.get(symbol)
                    if ticker:
                        info = ticker.fast_info
                        
                        ltp = info.last_price if hasattr(info, 'last_price') else 0
                        prev_close = info.previous_close if hasattr(info, 'previous_close') else 0
                        
                        if ltp and ltp > 0:
                            change = ltp - prev_close if prev_close else 0
                            change_pct = (change / prev_close * 100) if prev_close else 0
                            
                            # Update store
                            self._store.update(
                                symbol,
                                ltp=ltp,
                                prev_close=prev_close,
                                change=change,
                                change_pct=change_pct
                            )
                            
                            snap = self._store.get(symbol)
                            if snap:
                                snapshots[symbol] = snap
                except:
                    pass
                    
        except Exception:
            # Fallback: fetch one by one
            for symbol in self._symbols:
                try:
                    ticker = yf.Ticker(symbol)
                    info = ticker.fast_info
                    
                    ltp = info.last_price if hasattr(info, 'last_price') else 0
                    prev_close = info.previous_close if hasattr(info, 'previous_close') else 0
                    
                    if ltp and ltp > 0:
                        change = ltp - prev_close if prev_close else 0
                        change_pct = (change / prev_close * 100) if prev_close else 0
                        
                        self._store.update(
                            symbol,
                            ltp=ltp,
                            prev_close=prev_close,
                            change=change,
                            change_pct=change_pct
                        )
                        
                        snap = self._store.get(symbol)
                        if snap:
                            snapshots[symbol] = snap
                except:
                    pass
        
        return snapshots
    
    def stop(self):
        """Stop the worker."""
        self._running = False


class SignalWorker(QThread):
    """Background worker for signal generation."""
    
    signals_found = pyqtSignal(list)
    scan_complete = pyqtSignal()
    
    def __init__(self, engine=None):
        super().__init__()
        self._engine = engine
        self._running = True
        self._scan_requested = False
        self._symbols_to_scan: List[str] = []
    
    def request_scan(self, symbols: List[str]):
        """Request a market scan."""
        self._symbols_to_scan = symbols.copy()
        self._scan_requested = True
    
    def run(self):
        """Main worker loop."""
        while self._running:
            if self._scan_requested and self._engine:
                self._scan_requested = False
                signals = []
                
                for symbol in self._symbols_to_scan:
                    try:
                        result = self._engine.evaluate_trade_opportunity(symbol)
                        if result.get('ACTION') == 'EXECUTE_TRADE':
                            signals.append(result)
                    except:
                        pass
                
                if signals:
                    self.signals_found.emit(signals)
                
                self.scan_complete.emit()
            
            time.sleep(0.1)
    
    def stop(self):
        """Stop the worker."""
        self._running = False


class DataBridge(QObject):
    """Bridge between workers and UI for thread-safe updates."""
    
    price_update = pyqtSignal(str, float, float)
    signal_update = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        self._price_worker: Optional[PriceWorker] = None
        self._signal_worker: Optional[SignalWorker] = None
    
    def start_price_streaming(self, symbols: List[str], interval_ms: int = 3000):
        """Start background price updates."""
        if self._price_worker:
            self._price_worker.stop()
            self._price_worker.wait()
        
        self._price_worker = PriceWorker(symbols, interval_ms)
        self._price_worker.prices_updated.connect(self._on_prices)
        self._price_worker.start()
    
    def _on_prices(self, snapshots: Dict[str, StockSnapshot]):
        """Handle price updates from worker."""
        for symbol, snap in snapshots.items():
            self.price_update.emit(symbol, snap.ltp, snap.change_pct)
    
    def start_signal_scanning(self, engine):
        """Start background signal scanner."""
        if self._signal_worker:
            self._signal_worker.stop()
            self._signal_worker.wait()
        
        self._signal_worker = SignalWorker(engine)
        self._signal_worker.signals_found.connect(self._on_signals)
        self._signal_worker.start()
    
    def _on_signals(self, signals: list):
        """Handle signals from worker."""
        for sig in signals:
            self.signal_update.emit(sig)
    
    def request_scan(self, symbols: List[str]):
        """Request a market scan."""
        if self._signal_worker:
            self._signal_worker.request_scan(symbols)
    
    def add_symbol(self, symbol: str):
        """Add symbol to price tracking."""
        if self._price_worker:
            self._price_worker.add_symbol(symbol)
    
    def shutdown(self):
        """Clean shutdown of all workers."""
        if self._price_worker:
            self._price_worker.stop()
            self._price_worker.wait()
        
        if self._signal_worker:
            self._signal_worker.stop()
            self._signal_worker.wait()
