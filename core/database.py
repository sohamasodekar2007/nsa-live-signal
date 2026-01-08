"""Time-series database handler for OHLCV data and trading records."""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional, Dict
import pandas as pd
from contextlib import contextmanager

from core.enums import SignalType, TradeStatus


class TradingDatabase:
    """SQLite database handler optimized for time-series trading data."""
    
    def __init__(self, db_path: str = "data_storage/trading_engine.db"):
        """Initialize the database.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True, parents=True)
        self._initialize_tables()
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def _initialize_tables(self):
        """Create database tables if they don't exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # OHLCV data table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ohlcv_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume INTEGER NOT NULL,
                    UNIQUE(symbol, timeframe, timestamp)
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_timeframe 
                ON ohlcv_data(symbol, timeframe, timestamp DESC)
            """)
            
            # Signals table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    signal_type TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    regime TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    stop_loss REAL NOT NULL,
                    target1 REAL,
                    target2 REAL,
                    risk_reward REAL NOT NULL,
                    reasoning TEXT,
                    indicators_json TEXT
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_signals_symbol 
                ON signals(symbol, timestamp DESC)
            """)
            
            # Trades table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_id INTEGER,
                    symbol TEXT NOT NULL,
                    entry_timestamp DATETIME NOT NULL,
                    exit_timestamp DATETIME,
                    position_type TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL,
                    stop_loss REAL NOT NULL,
                    target REAL,
                    status TEXT NOT NULL,
                    pnl REAL,
                    pnl_percent REAL,
                    FOREIGN KEY(signal_id) REFERENCES signals(id)
                )
            """)
            
            # Portfolio state table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    total_capital REAL NOT NULL,
                    invested_capital REAL NOT NULL,
                    available_capital REAL NOT NULL,
                    unrealized_pnl REAL NOT NULL,
                    realized_pnl REAL NOT NULL,
                    total_pnl REAL NOT NULL,
                    drawdown_percent REAL NOT NULL,
                    open_positions INTEGER NOT NULL
                )
            """)
    
    def insert_ohlcv_bulk(self, symbol: str, timeframe: str, 
                          df: pd.DataFrame) -> int:
        """Insert OHLCV data in bulk.
        
        Args:
            symbol: Stock symbol
            timeframe: Timeframe (e.g., '1d', '5m')
            df: DataFrame with OHLCV data (columns: timestamp, open, high, low, close, volume)
            
        Returns:
            Number of rows inserted
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            records = []
            for _, row in df.iterrows():
                records.append((
                    symbol,
                    timeframe,
                    row['timestamp'] if isinstance(row['timestamp'], str) else row['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                    float(row['open']),
                    float(row['high']),
                    float(row['low']),
                    float(row['close']),
                    int(row['volume'])
                ))
            
            cursor.executemany("""
                INSERT OR REPLACE INTO ohlcv_data 
                (symbol, timeframe, timestamp, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, records)
            
            return len(records)
    
    def get_ohlcv(self, symbol: str, timeframe: str, 
                  limit: Optional[int] = None,
                  start_date: Optional[datetime] = None,
                  end_date: Optional[datetime] = None) -> pd.DataFrame:
        """Retrieve OHLCV data.
        
        Args:
            symbol: Stock symbol
            timeframe: Timeframe
            limit: Maximum number of records (most recent)
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            DataFrame with OHLCV data
        """
        with self._get_connection() as conn:
            query = """
                SELECT timestamp, open, high, low, close, volume
                FROM ohlcv_data
                WHERE symbol = ? AND timeframe = ?
            """
            params = [symbol, timeframe]
            
            if start_date:
                query += " AND timestamp >= ?"
                params.append(start_date.strftime('%Y-%m-%d %H:%M:%S'))
            
            if end_date:
                query += " AND timestamp <= ?"
                params.append(end_date.strftime('%Y-%m-%d %H:%M:%S'))
            
            query += " ORDER BY timestamp DESC"
            
            if limit:
                query += f" LIMIT {limit}"
            
            df = pd.read_sql_query(query, conn, params=params)
            
            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df = df.sort_values('timestamp').reset_index(drop=True)
            
            return df
    
    def insert_signal(self, symbol: str, timeframe: str, signal_type: SignalType,
                     confidence: float, regime: str, entry_price: float,
                     stop_loss: float, targets: List[float], risk_reward: float,
                     reasoning: str = "", indicators_json: str = "") -> int:
        """Insert a trading signal.
        
        Args:
            symbol: Stock symbol
            timeframe: Timeframe
            signal_type: BUY/SELL/HOLD
            confidence: Confidence percentage
            regime: Market regime
            entry_price: Entry price
            stop_loss: Stop loss price
            targets: List of target prices
            risk_reward: Risk-reward ratio
            reasoning: Signal reasoning
            indicators_json: JSON string of indicator values
            
        Returns:
            Signal ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO signals 
                (symbol, timeframe, timestamp, signal_type, confidence, regime,
                 entry_price, stop_loss, target1, target2, risk_reward, 
                 reasoning, indicators_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol, timeframe, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                signal_type.value, confidence, regime, entry_price, stop_loss,
                targets[0] if len(targets) > 0 else None,
                targets[1] if len(targets) > 1 else None,
                risk_reward, reasoning, indicators_json
            ))
            
            return cursor.lastrowid
    
    def insert_trade(self, signal_id: Optional[int], symbol: str, 
                    position_type: str, quantity: int, entry_price: float,
                    stop_loss: float, target: Optional[float] = None) -> int:
        """Insert a new trade.
        
        Args:
            signal_id: Associated signal ID (if any)
            symbol: Stock symbol
            position_type: LONG/SHORT
            quantity: Number of shares
            entry_price: Entry price
            stop_loss: Stop loss price
            target: Target price
            
        Returns:
            Trade ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO trades 
                (signal_id, symbol, entry_timestamp, position_type, quantity,
                 entry_price, stop_loss, target, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal_id, symbol, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                position_type, quantity, entry_price, stop_loss, target,
                TradeStatus.OPEN.value
            ))
            
            return cursor.lastrowid
    
    def update_trade_exit(self, trade_id: int, exit_price: float, 
                         status: TradeStatus):
        """Update trade with exit information.
        
        Args:
            trade_id: Trade ID
            exit_price: Exit price
            status: New trade status
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Get trade details
            cursor.execute("SELECT entry_price, quantity FROM trades WHERE id = ?", 
                         (trade_id,))
            row = cursor.fetchone()
            entry_price = row['entry_price']
            quantity = row['quantity']
            
            # Calculate P&L
            pnl = (exit_price - entry_price) * quantity
            pnl_percent = ((exit_price - entry_price) / entry_price) * 100
            
            cursor.execute("""
                UPDATE trades
                SET exit_timestamp = ?,
                    exit_price = ?,
                    status = ?,
                    pnl = ?,
                    pnl_percent = ?
                WHERE id = ?
            """, (
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                exit_price, status.value, pnl, pnl_percent, trade_id
            ))
    
    def get_open_trades(self, symbol: Optional[str] = None) -> pd.DataFrame:
        """Get all open trades.
        
        Args:
            symbol: Filter by symbol (optional)
            
        Returns:
            DataFrame with open trades
        """
        with self._get_connection() as conn:
            query = "SELECT * FROM trades WHERE status = 'OPEN'"
            params = []
            
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
            
            query += " ORDER BY entry_timestamp DESC"
            
            return pd.read_sql_query(query, conn, params=params if params else None)
    
    def insert_portfolio_snapshot(self, total_capital: float, invested: float,
                                 available: float, unrealized_pnl: float,
                                 realized_pnl: float, total_pnl: float,
                                 drawdown: float, open_positions: int):
        """Insert a portfolio snapshot.
        
        Args:
            total_capital: Total portfolio value
            invested: Invested capital
            available: Available capital
            unrealized_pnl: Unrealized P&L
            realized_pnl: Realized P&L
            total_pnl: Total P&L
            drawdown: Drawdown percentage
            open_positions: Number of open positions
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO portfolio_snapshots
                (timestamp, total_capital, invested_capital, available_capital,
                 unrealized_pnl, realized_pnl, total_pnl, drawdown_percent,
                 open_positions)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                total_capital, invested, available, unrealized_pnl,
                realized_pnl, total_pnl, drawdown, open_positions
            ))
