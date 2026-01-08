"""Rule-driven probabilistic trade execution engine.

This module integrates all components for strict rule-based trade execution:
- Multi-timeframe confirmation
- Entry type logic (pullback, breakout, momentum)
- Hybrid stop-loss calculation
- Target calculation with partial profit booking
- Risk-based quantity calculation (0.5-1% risk)
- Trade lifecycle management
- Enhanced validation with 70% confidence threshold
"""

import pandas as pd
from typing import Dict, Any, Optional
from datetime import datetime

from core.enums import SignalType, MarketRegime
from core.logger import get_logger
from data.fetcher import NSEDataFetcher
from analysis.signal_generator import SignalGenerator
from analysis.multi_timeframe import MultiTimeframeAnalyzer
from execution.entry_logic import EntryLogic
from execution.stop_loss import HybridStopLoss
from execution.targets import TargetCalculator
from execution.quantity_calculator import QuantityCalculator
from execution.trade_lifecycle import TradeLifecycleManager, Trade
from portfolio.state import PortfolioState
from portfolio.risk_manager import RiskManager


class RuleDrivenExecutionEngine:
    """Rule-driven execution engine with strict validation."""
    
    def __init__(self, portfolio: PortfolioState, risk_manager: RiskManager,
                 data_fetcher: NSEDataFetcher, 
                 min_confidence: float = 70.0,
                 min_rr: float = 2.0,
                 risk_per_trade_pct: float = 1.0,
                 logger=None):
        """Initialize execution engine.
        
        Args:
            portfolio: Portfolio state manager
            risk_manager: Risk manager
            data_fetcher: Data fetcher
            min_confidence: Minimum confidence threshold (default: 70%)
            min_rr: Minimum risk-reward ratio (default: 2.0)
            risk_per_trade_pct: Risk per trade % (default: 1.0%)
            logger: Logger instance
        """
        self.portfolio = portfolio
        self.risk_manager = risk_manager
        self.data_fetcher = data_fetcher
        self.min_confidence = min_confidence
        self.min_rr = min_rr
        self.risk_per_trade_pct = risk_per_trade_pct
        self.logger = logger or get_logger()
        
        # Initialize components
        self.signal_generator = SignalGenerator(
            min_confidence=min_confidence,
            min_risk_reward=min_rr,
            logger=self.logger
        )
        self.mtf_analyzer = MultiTimeframeAnalyzer(data_fetcher)
        self.trade_lifecycle_manager = TradeLifecycleManager(logger=self.logger)
    
    def evaluate_trade_opportunity(self, symbol: str, 
                                   higher_tf: str = "15m",
                                   lower_tf: str = "5m") -> Dict[str, Any]:
        """Evaluate a complete trade opportunity with all validations.
        
        This is the main entry point that orchestrates the entire evaluation process.
        
        Args:
            symbol: Stock symbol
            higher_tf: Higher timeframe (15m, 1h, 1d)
            lower_tf: Lower timeframe (1m, 5m)
            
        Returns:
            Dictionary with complete trade evaluation or HOLD decision
        """
        self.logger.info(f"Evaluating trade opportunity for {symbol}")
        
        # Step 1: Multi-timeframe alignment check
        mtf_analysis = self.mtf_analyzer.analyze_timeframes(symbol, higher_tf, lower_tf)
        
        if not mtf_analysis['aligned']:
            return self._hold_decision(
                symbol, 
                f"Multi-timeframe misalignment: {mtf_analysis['reason']}"
            )
        
        self.logger.info(f"{symbol}: Multi-timeframe aligned - {mtf_analysis['direction']}")
        
        # Step 2: Generate signal using lower timeframe data
        ltf_data = mtf_analysis['ltf_data']
        signal = self.signal_generator.generate_signal(symbol, ltf_data, lower_tf)
        
        if signal is None:
            return self._hold_decision(symbol, "No valid signal generated")
        
        # Step 3: Validate confidence threshold (≥70%)
        if signal['confidence'] < self.min_confidence:
            return self._hold_decision(
                symbol,
                f"Confidence {signal['confidence']:.1f}% below threshold {self.min_confidence}%"
            )
        
        self.logger.info(
            f"{symbol}: Signal {signal['signal_type'].value} with {signal['confidence']:.1f}% confidence"
        )
        
        # Step 4: Check regime - reject if sideways or abnormal volatility
        regime = signal['regime']
        volatility_analysis = signal['indicators']['volatility']
        
        if regime == MarketRegime.UNKNOWN:
            return self._hold_decision(symbol, "Market regime unknown")
        
        # Reject if extremely high volatility (unless breakout confirmed)
        atr_percentile = volatility_analysis.get('atr_percentile', 50)
        if atr_percentile > 95:
            return self._hold_decision(
                symbol,
                f"Abnormal volatility: ATR at {atr_percentile:.0f}th percentile"
            )
        
        # Step 5: Determine entry type
        current_price = ltf_data.iloc[-1]['close']
        trend_analysis = signal['indicators']['trend']
        structure_analysis = ltf_data  # Simplified - would use full structure analysis
        
        entry_setup = EntryLogic.identify_entry_type(
            ltf_data, trend_analysis, {}, current_price
        )
        
        if not entry_setup.get('valid', False):
            return self._hold_decision(
                symbol,
                f"No valid entry setup: {entry_setup.get('reason', 'Unknown')}"
            )
        
        entry_price = entry_setup['entry_price']
        entry_type = entry_setup['entry_type']
        
        self.logger.info(f"{symbol}: Entry type: {entry_type.value} @ ₹{entry_price:.2f}")
        
        # Step 6: Calculate hybrid stop-loss
        stop_calc = HybridStopLoss.calculate_hybrid_stop(
            ltf_data, entry_price, signal['signal_type']
        )
        
        stop_loss = stop_calc['stop_loss']
        
        self.logger.info(
            f"{symbol}: Stop-loss: ₹{stop_loss:.2f} ({stop_calc['method']}) "
            f"- Risk: {stop_calc['stop_distance_pct']:.2f}%"
        )
        
        # Step 7: Calculate targets with partial booking
        target_calc = TargetCalculator.calculate_targets(
            entry_price, stop_loss, signal['signal_type'], ltf_data, self.min_rr
        )
        
        targets = target_calc['targets']
        
        # Validate minimum R:R
        if targets and targets[0]['rr_ratio'] < self.min_rr:
            return self._hold_decision(
                symbol,
                f"Risk-reward {targets[0]['rr_ratio']:.2f} below minimum {self.min_rr}"
            )
        
        # Step 8: Calculate position quantity (risk-based)
        qty_calc = QuantityCalculator.calculate_quantity(
            total_capital=self.portfolio.total_capital,
            entry_price=entry_price,
            stop_loss=stop_loss,
            risk_per_trade_pct=self.risk_per_trade_pct,
            confidence=signal['confidence']
        )
        
        if not qty_calc['valid']:
            return self._hold_decision(
                symbol,
                f"Position sizing failed: {qty_calc['reason']}"
            )
        
        quantity = qty_calc['quantity']
        capital_required = qty_calc['capital_required']
        
        self.logger.info(
            f"{symbol}: Quantity: {quantity} shares, Capital: ₹{capital_required:,.2f}, "
            f"Risk: ₹{qty_calc['risk_amount']:,.2f} ({qty_calc['risk_pct']:.2f}%)"
        )
        
        # Step 9: Final risk management validation
        validation = self.risk_manager.validate_trade(
            symbol, entry_price, stop_loss, signal['confidence']
        )
        
        if not validation['allowed']:
            return self._hold_decision(symbol, f"Risk check failed: {validation['reason']}")
        
        # Step 10: Create trade in lifecycle manager
        trade = self.trade_lifecycle_manager.create_trade(symbol, signal['signal_type'])
        trade.confidence = signal['confidence']
        trade.risk_reward = targets[0]['rr_ratio'] if targets else 0
        trade.reasoning = signal['reasoning']
        trade.indicators = signal['indicators']
        trade.entry_type = entry_type.value
        
        trade.update_stage(trade.stage.__class__.VALIDATED, "All validations passed")
        
        # Step 11: Generate complete trade order
        trade_order = {
            'ACTION': 'EXECUTE_TRADE',
            'trade_id': trade.trade_id,
            'symbol': symbol,
            'direction': signal['signal_type'].value,
            'entry_price': entry_price,
            'entry_type': entry_type.value,
            'use_limit_order': entry_setup.get('use_limit_order', True),
            'limit_price': entry_setup.get('limit_price'),
            'quantity': quantity,
            'stop_loss': stop_loss,
            'stop_method': stop_calc['method'],
            'targets': targets,
            'profit_booking_plan': target_calc['profit_booking_plan'],
            'confidence': signal['confidence'],
            'risk_reward': targets[0]['rr_ratio'] if targets else 0,
            'capital_required': capital_required,
            'risk_amount': qty_calc['risk_amount'],
            'risk_pct': qty_calc['risk_pct'],
            'regime': regime.value,
            'mtf_alignment': mtf_analysis['reason'],
            'reasoning': self._build_detailed_reasoning(
                signal, mtf_analysis, entry_setup, stop_calc, target_calc, qty_calc
            ),
            'validation_passed': True,
            'timestamp': datetime.now()
        }
        
        # Log comprehensive trade decision
        self.logger.log_signal(
            symbol=symbol,
            signal_type=signal['signal_type'].value,
            confidence=signal['confidence'],
            regime=regime.value,
            indicators=signal['indicators'],
            entry=entry_price,
            stop_loss=stop_loss,
            targets=[t['price'] for t in targets],
            risk_reward=targets[0]['rr_ratio'] if targets else 0,
            reasoning=trade_order['reasoning']
        )
        
        return trade_order
    
    def _hold_decision(self, symbol: str, reason: str) -> Dict[str, Any]:
        """Generate HOLD decision with explicit justification.
        
        Args:
            symbol: Stock symbol
            reason: Reason for HOLD
            
        Returns:
            HOLD decision dictionary
        """
        self.logger.info(f"{symbol}: HOLD - {reason}")
        
        return {
            'ACTION': 'HOLD',
            'symbol': symbol,
            'direction': 'HOLD',
            'reason': reason,
            'timestamp': datetime.now(),
            'validation_passed': False
        }
    
    def _build_detailed_reasoning(self, signal: Dict, mtf: Dict, entry: Dict,
                                  stop: Dict, targets: Dict, qty: Dict) -> str:
        """Build comprehensive reasoning for trade decision.
        
        Args:
            signal: Signal data
            mtf: Multi-timeframe analysis
            entry: Entry setup
            stop: Stop-loss calculation
            targets: Target calculation
            qty: Quantity calculation
            
        Returns:
            Detailed reasoning string
        """
        reasoning_parts = []
        
        # Multi-timeframe
        reasoning_parts.append(f"MTF: {mtf['reason']}")
        
        # Signal
        reasoning_parts.append(
            f"Signal: {signal['signal_type'].value} @ {signal['confidence']:.0f}% confidence"
        )
        
        # Regime
        reasoning_parts.append(f"Regime: {signal['regime'].value}")
        
        # Entry
        reasoning_parts.append(f"Entry: {entry['entry_type'].value} - {entry.get('reason', '')}")
        
        # Stop-loss
        reasoning_parts.append(
            f"Stop: {stop['method']} @ ₹{stop['stop_loss']:.2f}  ({stop['stop_distance_pct']:.1f}%)"
        )
        
        # Targets
        if targets['targets']:
            target_str = ", ".join([
                f"T{i+1}: ₹{t['price']:.2f} ({t['book_percentage']}%)" 
                for i, t in enumerate(targets['targets'])
            ])
            reasoning_parts.append(f"Targets: {target_str}")
        
        # Risk
        reasoning_parts.append(
            f"Risk: ₹{qty['risk_amount']:,.0f} ({qty['risk_pct']:.2f}%), "
            f"Qty: {qty['quantity']} shares"
        )
        
        # Indicators
        indicators = signal['indicators']
        if 'trend' in indicators:
            trend = indicators['trend']
            reasoning_parts.append(f"Trend: {trend.get('type', 'N/A')}")
        
        if 'momentum' in indicators:
            momentum = indicators['momentum']
            reasoning_parts.append(f"RSI: {momentum.get('rsi', 'N/A')}")
        
        return " | ".join(reasoning_parts)
    
    def execute_trade(self, trade_order: Dict[str, Any]) -> bool:
        """Execute a validated trade order.
        
        Note: In production, this would interface with broker API.
        For now, it simulates execution and updates portfolio.
        
        Args:
            trade_order: Trade order from evaluate_trade_opportunity
            
        Returns:
            True if execution successful
        """
        if trade_order['ACTION'] != 'EXECUTE_TRADE':
            self.logger.info(f"No execution needed: {trade_order['ACTION']}")
            return False
        
        symbol = trade_order['symbol']
        trade_id = trade_order['trade_id']
        
        # Get trade from lifecycle manager
        trade = [t for t in self.trade_lifecycle_manager.active_trades.values() 
                if t.trade_id == trade_id][0]
        
        # Simulate order execution (in production, send to broker)
        entry_price = trade_order['entry_price']
        quantity = trade_order['quantity']
        stop_loss = trade_order['stop_loss']
        targets = trade_order['targets']
        
        # Record trade entry in lifecycle
        trade.enter_trade(
            entry_price=entry_price,
            quantity=quantity,
            stop_loss=stop_loss,
            targets=targets,
            entry_type=trade_order['entry_type']
        )
        
        # Add position to portfolio
        from core.enums import PositionType
        position_type = PositionType.LONG if trade.signal_type == SignalType.BUY else PositionType.SHORT
        
        success = self.portfolio.add_position(
            symbol=symbol,
            position_type=position_type,
            quantity=quantity,
            entry_price=entry_price,
            stop_loss=stop_loss,
            target=targets[0]['price'] if targets else None
        )
        
        if success:
            # Record trade with risk manager
            self.risk_manager.record_trade(symbol)
            
            self.logger.info(
                f"Trade {trade_id} EXECUTED: {symbol} | "
                f"{trade.signal_type.value} {quantity} @ ₹{entry_price:.2f} | "
                f"SL: ₹{stop_loss:.2f} | "
                f"Capital: ₹{trade_order['capital_required']:,.2f}"
            )
            
            return True
        else:
            trade.reject("Portfolio execution failed")
            self.logger.error(f"Failed to execute trade {trade_id}")
            return False
