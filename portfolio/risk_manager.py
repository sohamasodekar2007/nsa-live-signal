"""Risk management rules and position sizing."""

import pandas as pd
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from portfolio.state import PortfolioState


class RiskManager:
    """Enforce risk management rules and calculate position sizing."""
    
    def __init__(self, config: Dict[str, Any], portfolio: PortfolioState,
                 logger=None):
        """Initialize risk manager.
        
        Args:
            config: Risk configuration dictionary
            portfolio: Portfolio state instance
            logger: Logger instance
        """
        self.config = config
        self.portfolio = portfolio
        self.logger = logger
        
        # Risk parameters
        self.max_capital_per_trade_pct = config.get('max_capital_per_trade_percent', 10.0)
        self.max_daily_loss_pct = config.get('max_daily_loss_percent', 3.0)
        self.max_open_positions = config.get('max_open_positions', 8)
        self.risk_per_trade_pct = config.get('risk_per_trade_percent', 1.5)
        self.max_trades_per_stock_per_day = config.get('max_trades_per_stock_per_day', 3)
        
        # Track daily metrics
        self.today_start_capital = portfolio.total_capital
        self.today_trades = {}  # symbol -> count
        self.last_reset_date = datetime.now().date()
        self.trading_halted = False
    
    def reset_daily_counters(self):
        """Reset daily counters at start of new day."""
        current_date = datetime.now().date()
        
        if current_date != self.last_reset_date:
            self.today_start_capital = self.portfolio.total_capital
            self.today_trades = {}
            self.last_reset_date = current_date
            self.trading_halted = False
            
            if self.logger:
                self.logger.info("Daily risk counters reset")
    
    def check_daily_loss_limit(self) -> bool:
        """Check if daily loss limit has been breached.                
        Returns:
            True if trading allowed, False if halted
        """
        self.reset_daily_counters()
        
        current_pnl = self.portfolio.total_capital - self.today_start_capital
        daily_loss_pct = (current_pnl / self.today_start_capital) * 100
        
        if daily_loss_pct <= -self.max_daily_loss_pct:
            if not self.trading_halted:
                self.trading_halted = True
                if self.logger:
                    self.logger.log_risk_breach(
                        "MAX_DAILY_LOSS",
                        f"Daily loss of {daily_loss_pct:.2f}% exceeds limit of {self.max_daily_loss_pct}%. Trading halted."
                    )
            return False
        
        return True
    
    def check_max_positions(self) -> bool:
        """Check if maximum open positions limit reached.
        
        Returns:
            True if can open new position, False otherwise
        """
        if len(self.portfolio.positions) >= self.max_open_positions:
            if self.logger:
                self.logger.warning(
                    f"Max open positions ({self.max_open_positions}) reached"
                )
            return False
        return True
    
    def check_stock_trade_frequency(self, symbol: str) -> bool:
        """Check if max trades per stock per day limit reached.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            True if can trade, False otherwise
        """
        self.reset_daily_counters()
        
        trades_today = self.today_trades.get(symbol, 0)
        if trades_today >= self.max_trades_per_stock_per_day:
            if self.logger:
                self.logger.warning(
                    f"Max trades for {symbol} today ({self.max_trades_per_stock_per_day}) reached"
                )
            return False
        
        return True
    
    def calculate_position_size(self, entry_price: float, stop_loss: float,
                               signal_confidence: float) -> Dict[str, Any]:
        """Calculate optimal position size based on ATR and risk rules.
        
        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            signal_confidence: Signal confidence (0-100)
            
        Returns:
            Dictionary with position sizing details
        """
        # Risk amount (per trade)
        total_capital = self.portfolio.total_capital
        risk_amount = total_capital * (self.risk_per_trade_pct / 100)
        
        # Adjust risk based on confidence (higher confidence = more risk)
        confidence_multiplier = 0.5 + (signal_confidence / 100) * 0.5  # 0.5 to 1.0
        adjusted_risk = risk_amount * confidence_multiplier
        
        # Calculate position size based on stop-loss distance
        risk_per_share = abs(entry_price - stop_loss)
        
        if risk_per_share == 0:
            return {
                'quantity': 0,
                'investment': 0,
                'risk_amount': 0,
                'valid': False,
                'reason': 'Invalid stop-loss distance'
            }
        
        quantity = int(adjusted_risk / risk_per_share)
        
        # Apply max capital per trade limit
        max_investment = total_capital * (self.max_capital_per_trade_pct / 100)
        required_investment = quantity * entry_price
        
        if required_investment > max_investment:
            # Scale down quantity
            quantity = int(max_investment / entry_price)
            required_investment = quantity * entry_price
        
        # Check available capital
        if required_investment > self.portfolio.available_capital:
            quantity = int(self.portfolio.available_capital / entry_price)
            required_investment = quantity * entry_price
        
        # Validate quantity
        if quantity <= 0:
            return {
                'quantity': 0,
                'investment': 0,
                'risk_amount': 0,
                'valid': False,
                'reason': 'Insufficient capital'
            }
        
        actual_risk = quantity * risk_per_share
        risk_pct_of_capital = (actual_risk / total_capital) * 100
        
        return {
            'quantity': quantity,
            'investment': required_investment,
            'risk_amount': actual_risk,
            'risk_percent': risk_pct_of_capital,
            'shares_per_percent_risk': quantity / risk_pct_of_capital if risk_pct_of_capital > 0 else 0,
            'valid': True,
            'reason': 'Position sizing calculated'
        }
    
    def validate_trade(self, symbol: str, entry_price: float, 
                      stop_loss: float, confidence: float) -> Dict[str, Any]:
        """Validate if a trade can be executed based on all risk rules.
        
        Args:
            symbol: Stock symbol
            entry_price: Entry price
            stop_loss: Stop loss price
            confidence: Signal confidence
            
        Returns:
            Dictionary with validation result
        """
        # Check daily loss limit
        if not self.check_daily_loss_limit():
            return {
                'allowed': False,
                'reason': 'Daily loss limit breached - trading halted',
                'position_size': None
            }
        
        # Check max positions
        if not self.check_max_positions():
            return {
                'allowed': False,
                'reason': 'Maximum open positions reached',
                'position_size': None
            }
        
        # Check position already exists
        if symbol in self.portfolio.positions:
            return {
                'allowed': False,
                'reason': f'Position already exists for {symbol}',
                'position_size': None
            }
        
        # Check trade frequency for this stock
        if not self.check_stock_trade_frequency(symbol):
            return {
                'allowed': False,
                'reason': f'Max trades per day for {symbol} reached',
                'position_size': None
            }
        
        # Calculate position size
        position_size = self.calculate_position_size(entry_price, stop_loss, confidence)
        
        if not position_size['valid']:
            return {
                'allowed': False,
                'reason': position_size['reason'],
                'position_size': None
            }
        
        return {
            'allowed': True,
            'reason': 'Trade validated - risk within limits',
            'position_size': position_size
        }
    
    def record_trade(self, symbol: str):
        """Record that a trade was executed for tracking.
        
        Args:
            symbol: Stock symbol
        """
        self.reset_daily_counters()
        self.today_trades[symbol] = self.today_trades.get(symbol, 0) + 1
