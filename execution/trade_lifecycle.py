"""Trade lifecycle manager for complete trade flow."""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from enum import Enum

from core.enums import SignalType, TradeStatus


class TradeLifecycleStage(Enum):
    """Stages in trade lifecycle."""
    SIGNAL_GENERATED = "SIGNAL_GENERATED"
    VALIDATED = "VALIDATED"
    ENTRY_PENDING = "ENTRY_PENDING"
    ENTERED = "ENTERED"
    MONITORING = "MONITORING"
    PARTIAL_EXIT_1 = "PARTIAL_EXIT_1"
    PARTIAL_EXIT_2 = "PARTIAL_EXIT_2"
    TRAILING = "TRAILING"
    EXITED = "EXITED"
    REJECTED = "REJECTED"


class Trade:
    """Represents a complete trade with lifecycle management."""
    
    def __init__(self, trade_id: str, symbol: str, signal_type: SignalType):
        """Initialize trade.
        
        Args:
            trade_id: Unique trade identifier
            symbol: Stock symbol
            signal_type: BUY or SELL
        """
        self.trade_id = trade_id
        self.symbol = symbol
        self.signal_type = signal_type
        self.stage = TradeLifecycleStage.SIGNAL_GENERATED
        
        # Trade parameters
        self.entry_price = 0.0
        self.quantity = 0
        self.stop_loss = 0.0
        self.targets = []
        self.confidence = 0.0
        self.risk_reward = 0.0
        
        # Execution details
        self.entry_time = None
        self.exit_time = None
        self.exit_price = 0.0
        self.exit_reason = ""
        
        # Position tracking
        self.remaining_quantity = 0
        self.booked_quantity = 0
        self.realized_pnl = 0.0
        self.unrealized_pnl = 0.0
        
        # Lifecycle tracking
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.stage_history = [(TradeLifecycleStage.SIGNAL_GENERATED, datetime.now())]
        self.highest_price = 0.0  # For trailing
        self.lowest_price = float('inf')  # For trailing
        
        # Metadata
        self.reasoning = ""
        self.rejection_reason = ""
        self.entry_type = None
        self.indicators = {}
    
    def update_stage(self, new_stage: TradeLifecycleStage, note: str = ""):
        """Update trade lifecycle stage.
        
        Args:
            new_stage: New lifecycle stage
            note: Optional note about the stage change
        """
        self.stage = new_stage
        self.updated_at = datetime.now()
        self.stage_history.append((new_stage, datetime.now(), note))
    
    def enter_trade(self, entry_price: float, quantity: int, stop_loss: float,
                   targets: list, entry_type: str):
        """Record trade entry.
        
        Args:
            entry_price: Actual entry price
            quantity: Shares entered
            stop_loss: Stop-loss price
            targets: List of target prices
            entry_type: Type of entry (PULLBACK, BREAKOUT, etc.)
        """
        self.entry_price = entry_price
        self.quantity = quantity
        self.remaining_quantity = quantity
        self.stop_loss = stop_loss
        self.targets = targets
        self.entry_type = entry_type
        self.entry_time = datetime.now()
        self.highest_price = entry_price
        self.lowest_price = entry_price
        
        self.update_stage(TradeLifecycleStage.ENTERED, f"Entered {quantity} @ ₹{entry_price}")
        self.update_stage(TradeLifecycleStage.MONITORING, "Monitoring position")
    
    def partial_exit(self, exit_price: float, quantity: int, target_level: int):
        """Record partial exit.
        
        Args:
            exit_price: Exit price for partial
            quantity: Shares exited
            target_level: Which  target was hit (1, 2, 3)
        """
        self.booked_quantity += quantity
        self.remaining_quantity -= quantity
        
        # Calculate realized P&L for this partial
        if self.signal_type == SignalType.BUY:
            partial_pnl = (exit_price - self.entry_price) * quantity
        else:
            partial_pnl = (self.entry_price - exit_price) * quantity
        
        self.realized_pnl += partial_pnl
        
        stage_map = {
            1: TradeLifecycleStage.PARTIAL_EXIT_1,
            2: TradeLifecycleStage.PARTIAL_EXIT_2,
            3: TradeLifecycleStage.TRAILING
        }
        
        self.update_stage(
            stage_map.get(target_level, TradeLifecycleStage.PARTIAL_EXIT_1),
            f"Booked {quantity} @ ₹{exit_price} (Target {target_level}), P&L: ₹{partial_pnl:,.2f}"
        )
    
    def final_exit(self, exit_price: float, reason: str):
        """Record final exit.
        
        Args:
            exit_price: Final exit price
            reason: Reason for exit
        """
        if self.remaining_quantity > 0:
            # Calculate final P&L
            if self.signal_type == SignalType.BUY:
                final_pnl = (exit_price - self.entry_price) * self.remaining_quantity
            else:
                final_pnl = (self.entry_price - exit_price) * self.remaining_quantity
            
            self.realized_pnl += final_pnl
            self.booked_quantity += self.remaining_quantity
            self.remaining_quantity = 0
        
        self.exit_price = exit_price
        self.exit_time = datetime.now()
        self.exit_reason = reason
        
        self.update_stage(
            TradeLifecycleStage.EXITED,
            f"Final exit @ ₹{exit_price}, Total P&L: ₹{self.realized_pnl:,.2f}, Reason: {reason}"
        )
    
    def reject(self, reason: str):
        """Reject trade before entry.
        
        Args:
            reason: Rejection reason
        """
        self.rejection_reason = reason
        self.update_stage(TradeLifecycleStage.REJECTED, reason)
    
    def update_current_price(self, current_price: float):
        """Update with current market price for P&L tracking.
        
        Args:
            current_price: Current market price
        """
        if self.stage in [TradeLifecycleStage.MONITORING, 
                         TradeLifecycleStage.PARTIAL_EXIT_1,
                         TradeLifecycleStage.PARTIAL_EXIT_2,
                         TradeLifecycleStage.TRAILING]:
            
            # Update highest/lowest for trailing
            self.highest_price = max(self.highest_price, current_price)
            self.lowest_price = min(self.lowest_price, current_price)
            
            # Calculate unrealized P&L
            if self.remaining_quantity > 0:
                if self.signal_type == SignalType.BUY:
                    self.unrealized_pnl = (current_price - self.entry_price) * self.remaining_quantity
                else:
                    self.unrealized_pnl = (self.entry_price - current_price) * self.remaining_quantity
    
    def get_summary(self) -> Dict[str, Any]:
        """Get trade summary.
        
        Returns:
            Dictionary with trade details
        """
        total_pnl = self.realized_pnl + self.unrealized_pnl
        
        holding_period = None
        if self.entry_time:
            if self.exit_time:
                holding_period = (self.exit_time - self.entry_time).total_seconds() / 3600  # hours
            else:
                holding_period = (datetime.now() - self.entry_time).total_seconds() / 3600
        
        return {
            'trade_id': self.trade_id,
            'symbol': self.symbol,
            'signal_type': self.signal_type.value,
            'stage': self.stage.value,
            'entry_price': self.entry_price,
            'current_stop': self.stop_loss,
            'quantity': self.quantity,
            'remaining_quantity': self.remaining_quantity,
            'booked_quantity': self.booked_quantity,
            'realized_pnl': self.realized_pnl,
            'unrealized_pnl': self.unrealized_pnl,
            'total_pnl': total_pnl,
            'confidence': self.confidence,
            'risk_reward': self.risk_reward,
            'entry_type': self.entry_type,
            'holding_period_hours': holding_period,
            'created_at': self.created_at,
            'entry_time': self.entry_time,
            'exit_time': self.exit_time,
            'exit_reason': self.exit_reason,
            'rejection_reason': self.rejection_reason
        }


class TradeLifecycleManager:
    """Manage complete trade lifecycle."""
    
    def __init__(self, logger=None):
        """Initialize lifecycle manager.
        
        Args:
            logger: Logger instance
        """
        self.logger = logger
        self.active_trades = {}  # trade_id -> Trade
        self.completed_trades = []
        self.next_trade_id = 1
    
    def create_trade(self, symbol: str, signal_type: SignalType) -> Trade:
        """Create a new trade.
        
        Args:
            symbol: Stock symbol
            signal_type: BUY or SELL
            
        Returns:
            Trade instance
        """
        trade_id = f"T{self.next_trade_id:05d}"
        self.next_trade_id += 1
        
        trade = Trade(trade_id, symbol, signal_type)
        self.active_trades[trade_id] = trade
        
        if self.logger:
            self.logger.info(f"Created trade {trade_id} for {symbol} ({signal_type.value})")
        
        return trade
    
    def get_active_trades(self, symbol: Optional[str] = None) -> list:
        """Get active trades, optionally filtered by symbol.
        
        Args:
            symbol: Optional symbol filter
            
        Returns:
            List of active Trade instances
        """
        if symbol:
            return [t for t in self.active_trades.values() if t.symbol == symbol]
        return list(self.active_trades.values())
    
    def close_trade(self, trade_id: str):
        """Move trade from active to completed.
        
        Args:
            trade_id: Trade ID to close
        """
        if trade_id in self.active_trades:
            trade = self.active_trades.pop(trade_id)
            self.completed_trades.append(trade)
            
            if self.logger:
                summary = trade.get_summary()
                self.logger.info(
                    f"Closed trade {trade_id}: {trade.symbol} | "
                    f"P&L: ₹{summary['total_pnl']:,.2f} | "
                    f"Reason: {trade.exit_reason}"
                )
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary of all completed trades.
        
        Returns:
            Dictionary with performance metrics
        """
        if not self.completed_trades:
            return {'total_trades': 0}
        
        total_pnl = sum(t.realized_pnl for t in self.completed_trades)
        winning_trades = [t for t in self.completed_trades if t.realized_pnl > 0]
        losing_trades = [t for t in self.completed_trades if t.realized_pnl < 0]
        
        win_rate = (len(winning_trades) / len(self.completed_trades)) * 100
        
        avg_win = sum(t.realized_pnl for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(t.realized_pnl for t in losing_trades) / len(losing_trades) if losing_trades else 0
        
        return {
            'total_trades': len(self.completed_trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'best_trade': max(self.completed_trades, key=lambda t: t.realized_pnl).realized_pnl if self.completed_trades else 0,
            'worst_trade': min(self.completed_trades, key=lambda t: t.realized_pnl).realized_pnl if self.completed_trades else 0
        }
