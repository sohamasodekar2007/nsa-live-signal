"""Comprehensive logging system for the trading engine."""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any


class TradingLogger:
    """Enhanced logger for trading decisions and system events."""
    
    def __init__(self, log_dir: str = "logs", level: str = "INFO"):
        """Initialize the trading logger.
        
        Args:
            log_dir: Directory to store log files
            level: Logging level (DEBUG, INFO, WARNING, ERROR)
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Create date-specific log file
        today = datetime.now().strftime("%Y-%m-%d")
        self.log_file = self.log_dir / f"trading_{today}.log"
        
        # Configure root logger
        self.logger = logging.getLogger("TradingEngine")
        self.logger.setLevel(getattr(logging, level.upper()))
        
        # File handler
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, level.upper()))
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Add handlers
        if not self.logger.handlers:
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)
    
    def log_signal(self, symbol: str, signal_type: str, confidence: float, 
                   regime: str, indicators: Dict[str, Any], 
                   entry: float, stop_loss: float, targets: list, 
                   risk_reward: float, reasoning: str = ""):
        """Log a trading signal with full details.
        
        Args:
            symbol: Stock symbol
            signal_type: BUY/SELL/HOLD
            confidence: Signal confidence (0-100)
            regime: Market regime
            indicators: Dictionary of indicator values
            entry: Entry price
            stop_loss: Stop loss price
            targets: List of target prices
            risk_reward: Risk-reward ratio
            reasoning: Additional reasoning text
        """
        separator = "=" * 80
        self.logger.info(f"\n{separator}")
        self.logger.info(f"SIGNAL GENERATED: {symbol}")
        self.logger.info(separator)
        self.logger.info(f"Type: {signal_type} | Confidence: {confidence:.1f}% | Regime: {regime}")
        self.logger.info(f"Entry: ₹{entry:.2f} | Stop Loss: ₹{stop_loss:.2f}")
        self.logger.info(f"Targets: {' | '.join([f'T{i+1}: ₹{t:.2f}' for i, t in enumerate(targets)])}")
        self.logger.info(f"Risk-Reward: {risk_reward:.2f}")
        
        if indicators:
            self.logger.info("\nIndicator Values:")
            for name, value in indicators.items():
                self.logger.info(f"  • {name}: {value}")
        
        if reasoning:
            self.logger.info(f"\nReasoning: {reasoning}")
        
        self.logger.info(separator + "\n")
    
    def log_trade(self, symbol: str, action: str, quantity: int, price: float, 
                  reason: str = ""):
        """Log a trade execution.
        
        Args:
            symbol: Stock symbol
            action: BUY/SELL
            quantity: Number of shares
            price: Execution price
            reason: Reason for the trade
        """
        self.logger.info(f"TRADE EXECUTED: {action} {quantity} x {symbol} @ ₹{price:.2f}")
        if reason:
            self.logger.info(f"Reason: {reason}")
    
    def log_portfolio_update(self, total_capital: float, invested: float, 
                            unrealized_pnl: float, realized_pnl: float, 
                            drawdown: float):
        """Log portfolio state update.
        
        Args:
            total_capital: Total portfolio value
            invested: Currently invested capital
            unrealized_pnl: Unrealized profit/loss
            realized_pnl: Realized profit/loss
            drawdown: Current drawdown percentage
        """
        self.logger.info(f"PORTFOLIO UPDATE:")
        self.logger.info(f"  Total: ₹{total_capital:,.2f} | Invested: ₹{invested:,.2f}")
        self.logger.info(f"  Unrealized P&L: ₹{unrealized_pnl:,.2f} | Realized P&L: ₹{realized_pnl:,.2f}")
        self.logger.info(f"  Drawdown: {drawdown:.2f}%")
    
    def log_risk_breach(self, rule: str, detail: str):
        """Log risk management rule breach.
        
        Args:
            rule: Rule that was breached
            detail: Details of the breach
        """
        self.logger.warning(f"RISK BREACH: {rule}")
        self.logger.warning(f"Detail: {detail}")
    
    def info(self, message: str):
        """Log info message."""
        self.logger.info(message)
    
    def warning(self, message: str):
        """Log warning message."""
        self.logger.warning(message)
    
    def error(self, message: str):
        """Log error message."""
        self.logger.error(message)
    
    def debug(self, message: str):
        """Log debug message."""
        self.logger.debug(message)


# Global logger instance
_logger_instance = None


def get_logger(log_dir: str = "logs", level: str = "INFO") -> TradingLogger:
    """Get or create the global logger instance.
    
    Args:
        log_dir: Directory to store log files
        level: Logging level
        
    Returns:
        TradingLogger instance
    """
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = TradingLogger(log_dir, level)
    return _logger_instance
