"""Portfolio state management and tracking."""

import pandas as pd
from typing import Dict, List, Optional, Any
from datetime import datetime

from core.enums import PositionType, TradeStatus
from core.database import TradingDatabase


class PortfolioState:
    """Track portfolio state including positions, capital, and P&L."""
    
    def __init__(self, initial_capital: float, database: TradingDatabase,
                 logger=None):
        """Initialize portfolio state.
        
        Args:
            initial_capital: Starting capital
            database: Database instance
            logger: Logger instance
        """
        self.initial_capital = initial_capital
        self.total_capital = initial_capital
        self.invested_capital = 0.0
        self.available_capital = initial_capital
        self.unrealized_pnl = 0.0
        self.realized_pnl = 0.0
        
        self.positions = {}  # symbol -> position dict
        self.db = database
        self.logger = logger
        
        # Track peak capital for drawdown
        self.peak_capital = initial_capital
        self.current_drawdown = 0.0
        self.max_drawdown = 0.0
        
        self._load_from_db()

    def _load_from_db(self):
        """Load open positions from database."""
        try:
            open_trades = self.db.get_open_trades()
            if not open_trades.empty:
                for _, trade in open_trades.iterrows():
                    symbol = trade['symbol']
                    self.positions[symbol] = {
                        'trade_id': trade['id'],
                        'symbol': symbol,
                        'position_type': PositionType(trade['position_type']),
                        'quantity': trade['quantity'],
                        'entry_price': trade['entry_price'],
                        'current_price': trade['entry_price'],
                        'stop_loss': trade['stop_loss'],
                        'target': trade['target'],
                        'investment': trade['entry_price'] * trade['quantity'],
                        'unrealized_pnl': 0.0,
                        'entry_time': pd.to_datetime(trade['entry_timestamp'])
                    }
                    self.invested_capital += (trade['entry_price'] * trade['quantity'])
                    self.available_capital -= (trade['entry_price'] * trade['quantity'])
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to load positions from DB: {e}")

    def add_position(self, symbol: str, position_type: PositionType,
                    quantity: int, entry_price: float, stop_loss: float,
                    target: Optional[float] = None) -> bool:
        """Add a new position to the portfolio.
        
        Args:
            symbol: Stock symbol
            position_type: LONG or SHORT
            quantity: Number of shares
            entry_price: Entry price
            stop_loss: Stop loss price
            target: Target price
            
        Returns:
            True if position added successfully
        """
        if symbol in self.positions:
            if self.logger:
                self.logger.warning(f"Position already exists for {symbol}")
            return False
        
        # Calculate investment amount
        investment = quantity * entry_price
        
        if investment > self.available_capital:
            if self.logger:
                self.logger.error(f"Insufficient capital for {symbol} position")
            return False
        
        # Persist to DB first
        try:
            trade_id = self.db.insert_trade(
                signal_id=None,
                symbol=symbol,
                position_type=position_type.value,
                quantity=quantity,
                entry_price=entry_price,
                stop_loss=stop_loss,
                target=target
            )
        except Exception as e:
            if self.logger:
                self.logger.error(f"DB Error adding position: {e}")
            return False

        # Create position
        position = {
            'trade_id': trade_id,
            'symbol': symbol,
            'position_type': position_type,
            'quantity': quantity,
            'entry_price': entry_price,
            'current_price': entry_price,
            'stop_loss': stop_loss,
            'target': target,
            'investment': investment,
            'unrealized_pnl': 0.0,
            'entry_time': datetime.now()
        }
        
        self.positions[symbol] = position
        
        # Update capital
        self.available_capital -= investment
        self.invested_capital += investment
        
        if self.logger:
            self.logger.info(f"Added position: {position_type.value} {quantity} x {symbol} @ ₹{entry_price:.2f}")
        
        return True
    
    def update_position_price(self, symbol: str, current_price: float):
        """Update current price, P&L, and manage Trailing Stop Loss.
        
        Args:
            symbol: Stock symbol
            current_price: Current market price
        """
        if symbol not in self.positions:
            return
        
        position = self.positions[symbol]
        position['current_price'] = current_price
        
        # Calculate unrealized P&L
        if position['position_type'] == PositionType.LONG:
            pnl = (current_price - position['entry_price']) * position['quantity']
        else:  # SHORT
            pnl = (position['entry_price'] - current_price) * position['quantity']
        
        position['unrealized_pnl'] = pnl
        
        # --- TRAILING STOP LOSS LOGIC ---
        sl = position.get('stop_loss')
        target1 = position.get('target') # Assuming target is Target 1
        
        if sl:
            if position['position_type'] == PositionType.LONG:
                # 1. Break-Even: If price hits Target 1, move SL to Entry Price
                if target1 and current_price >= target1 and sl < position['entry_price']:
                    position['stop_loss'] = position['entry_price']
                    if self.logger:
                        self.logger.info(f"TSL: Moved SL to Breakeven for {symbol} @ {position['entry_price']}")
                
                # 2. Dynamic Trailing: If price moves up 1%, move SL up by 0.5% (to lock profit)
                # Keep SL at a fixed distance if price moves significantly in favor
                # Logic: If current price > entry + 2%, Trail SL to (Current Price - 1.5%)
                pct_gain = (current_price - position['entry_price']) / position['entry_price'] * 100
                if pct_gain > 2.0:
                    new_sl = current_price * 0.985 # 1.5% below current price
                    if new_sl > sl:
                        position['stop_loss'] = round(new_sl, 2)
                        # Optional: Log TSL update (reduce verbosity in real-time)
                        
            else: # SHORT
                # 1. Break-Even
                if target1 and current_price <= target1 and sl > position['entry_price']:
                    position['stop_loss'] = position['entry_price']
                    if self.logger:
                        self.logger.info(f"TSL: Moved SL to Breakeven for {symbol} @ {position['entry_price']}")
                
                # 2. Dynamic Trailing
                pct_gain = (position['entry_price'] - current_price) / position['entry_price'] * 100
                if pct_gain > 2.0:
                    new_sl = current_price * 1.015 # 1.5% above current price
                    if new_sl < sl:
                        position['stop_loss'] = round(new_sl, 2)
    
    def close_position(self, symbol: str, exit_price: float, 
                      reason: str = "Manual") -> Optional[Dict[str, Any]]:
        """Close an existing position.
        
        Args:
            symbol: Stock symbol
            exit_price: Exit price
            reason: Reason for closing
            
        Returns:
            Dictionary with trade results or None
        """
        if symbol not in self.positions:
            if self.logger:
                self.logger.warning(f"No position found for {symbol}")
            return None
        
        position = self.positions[symbol]
        
        # Update DB
        if 'trade_id' in position:
            try:
                self.db.update_trade_exit(
                    trade_id=position['trade_id'],
                    exit_price=exit_price,
                    status=TradeStatus.CLOSED
                )
            except Exception as e:
                if self.logger:
                    self.logger.error(f"DB Error closing position: {e}")
        
        # Calculate final P&L
        if position['position_type'] == PositionType.LONG:
            pnl = (exit_price - position['entry_price']) * position['quantity']
        else:  # SHORT
            pnl = (position['entry_price'] - exit_price) * position['quantity']
        
        pnl_percent = (pnl / position['investment']) * 100
        
        # Update capital
        proceeds = position['investment'] + pnl
        self.available_capital += proceeds
        self.invested_capital -= position['investment']
        self.realized_pnl += pnl
        
        # Log trade
        trade_result = {
            'symbol': symbol,
            'position_type': position['position_type'],
            'quantity': position['quantity'],
            'entry_price': position['entry_price'],
            'exit_price': exit_price,
            'pnl': pnl,
            'pnl_percent': pnl_percent,
            'holding_period': datetime.now() - position['entry_time'],
            'reason': reason
        }
        
        # Remove position
        del self.positions[symbol]
        
        if self.logger:
            self.logger.log_trade(
                symbol, "CLOSE", position['quantity'], exit_price,
                f"P&L: ₹{pnl:,.2f} ({pnl_percent:+.2f}%) - {reason}"
            )
        
        return trade_result
    
    def update_all_positions(self, price_data: Dict[str, float]):
        """Update all positions with current prices.
        
        Args:
            price_data: Dictionary mapping symbol -> current price
        """
        for symbol in list(self.positions.keys()):
            if symbol in price_data:
                self.update_position_price(symbol, price_data[symbol])
    
    def calculate_totals(self):
        """Calculate total P&L and portfolio value."""
        # Calculate total unrealized P&L
        self.unrealized_pnl = sum(
            pos['unrealized_pnl'] for pos in self.positions.values()
        )
        
        # Total portfolio value
        self.total_capital = self.available_capital + self.invested_capital + self.unrealized_pnl
        
        # Update drawdown
        if self.total_capital > self.peak_capital:
            self.peak_capital = self.total_capital
        
        if self.peak_capital > 0:
            self.current_drawdown = ((self.peak_capital - self.total_capital) / 
                                    self.peak_capital * 100)
            self.max_drawdown = max(self.max_drawdown, self.current_drawdown)
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get current portfolio summary.
        
        Returns:
            Dictionary with portfolio metrics
        """
        self.calculate_totals()
        
        total_pnl = self.realized_pnl + self.unrealized_pnl
        total_return_pct = (total_pnl / self.initial_capital) * 100
        
        return {
            'total_capital': self.total_capital,
            'initial_capital': self.initial_capital,
            'available_capital': self.available_capital,
            'invested_capital': self.invested_capital,
            'unrealized_pnl': self.unrealized_pnl,
            'realized_pnl': self.realized_pnl,
            'total_pnl': total_pnl,
            'total_return_pct': total_return_pct,
            'current_drawdown': self.current_drawdown,
            'max_drawdown': self.max_drawdown,
            'open_positions': len(self.positions),
            'positions': list(self.positions.values())
        }
    
    def save_snapshot(self):
        """Save current portfolio state to database."""
        self.calculate_totals()
        
        self.db.insert_portfolio_snapshot(
            total_capital=self.total_capital,
            invested=self.invested_capital,
            available=self.available_capital,
            unrealized_pnl=self.unrealized_pnl,
            realized_pnl=self.realized_pnl,
            total_pnl=self.realized_pnl + self.unrealized_pnl,
            drawdown=self.current_drawdown,
            open_positions=len(self.positions)
        )
