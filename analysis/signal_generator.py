"""Probabilistic signal generation engine."""

import pandas as pd
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from core.enums import SignalType, MarketRegime
from indicators.trend import TrendIndicators
from indicators.momentum import MomentumIndicators
from indicators.volatility import VolatilityIndicators
from indicators.structure import StructureAnalysis
from analysis.regime_detector import RegimeDetector
from analysis.confluence import ConfluenceCalculator


class SignalGenerator:
    """Generate probabilistic trading signals with confidence and R:R ratios."""
    
    def __init__(self, min_confidence: float = 60.0, min_risk_reward: float = 1.5,
                 logger=None):
        """Initialize signal generator.
        
        Args:
            min_confidence: Minimum confidence threshold for signals (%)
            min_risk_reward: Minimum risk-reward ratio
            logger: Logger instance
        """
        self.min_confidence = min_confidence
        self.min_risk_reward = min_risk_reward
        self.logger = logger
        
        self.regime_detector = RegimeDetector()
        self.confluence_calculator = ConfluenceCalculator()
        
        # Track last signal time per symbol (for cooldown)
        self.last_signal_time = {}
    
    def calculate_all_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all technical indicators on the dataframe.
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            DataFrame with all indicators calculated
        """
        # Trend indicators
        df = TrendIndicators.calculate_ema(df)
        df = TrendIndicators.calculate_vwap(df)
        
        # Momentum indicators
        df = MomentumIndicators.calculate_rsi(df)
        df = MomentumIndicators.calculate_macd(df)
        df = MomentumIndicators.calculate_stochastic(df)
        
        # Volatility indicators
        df = VolatilityIndicators.calculate_atr(df)
        df = VolatilityIndicators.calculate_bollinger_bands(df)
        
        # Regime detection (adds ADX)
        df = self.regime_detector.calculate_adx(df)
        
        return df
    
    def generate_signal(self, symbol: str, df: pd.DataFrame, 
                       timeframe: str = '1d',
                       cooldown_minutes: int = 60) -> Optional[Dict[str, Any]]:
        """Generate a trading signal for a symbol.
        
        Args:
            symbol: Stock symbol
            df: DataFrame with OHLCV data
            timeframe: Timeframe for the signal
            cooldown_minutes: Minimum minutes between signals for this symbol
            
        Returns:
            Signal dictionary or None if no signal
        """
        if df.empty or len(df) < 200:
            if self.logger:
                self.logger.warning(f"Insufficient data for {symbol}: {len(df)} candles")
            return None
        
        # Check cooldown
        cooldown_key = f"{symbol}_{timeframe}"
        if cooldown_key in self.last_signal_time:
            time_since_last = datetime.now() - self.last_signal_time[cooldown_key]
            if time_since_last < timedelta(minutes=cooldown_minutes):
                if self.logger:
                    self.logger.debug(f"Signal cooldown active for {symbol}")
                return None
        
        # Calculate all indicators
        df = self.calculate_all_indicators(df)
        
        # Analyze each layer
        trend_analysis = TrendIndicators.analyze_trend(df)
        momentum_analysis = MomentumIndicators.analyze_momentum(df)
        volatility_analysis = VolatilityIndicators.analyze_volatility(df)
        structure_analysis = StructureAnalysis.analyze_structure(df)
        
        # Detect market regime
        regime_info = self.regime_detector.detect_regime(
            df, trend_analysis, volatility_analysis
        )
        
        # Calculate layer scores
        current_price = df.iloc[-1]['close']
        layer_scores = self.confluence_calculator.calculate_layer_scores(
            trend_analysis, momentum_analysis, volatility_analysis,
            structure_analysis, current_price
        )
        
        # Calculate confluence
        confluence = self.confluence_calculator.calculate_confluence(
            layer_scores, regime_info['weights']
        )
        
        # Determine signal type
        signal_type = SignalType.HOLD
        if confluence['direction'] == 'BULLISH':
            signal_type = SignalType.BUY
        elif confluence['direction'] == 'BEARISH':
            signal_type = SignalType.SELL
        
        # Calculate confidence
        base_confidence = confluence['score']
        regime_confidence = regime_info['confidence']
        agreement_boost = confluence['agreement'] * 0.2
        
        confidence = (base_confidence * 0.6 + regime_confidence * 0.3 + 
                     agreement_boost * 0.1)
        confidence = max(0, min(100, confidence))
        
        # Calculate stop-loss and targets using ATR
        atr_value = df.iloc[-1].get('atr', current_price * 0.02)
        sl_calc = VolatilityIndicators.calculate_stop_loss_target(
            current_price, atr_value,
            signal_type='BUY' if signal_type == SignalType.BUY else 'SELL'
        )
        
        stop_loss = sl_calc['stop_loss']
        targets = sl_calc['targets']
        risk_reward = sl_calc['best_risk_reward']
        
        # Apply rejection rules
        if confidence < self.min_confidence:
            if self.logger:
                self.logger.info(f"{symbol}: Rejected - Low confidence ({confidence:.1f}%)")
            return None
        
        if risk_reward < self.min_risk_reward:
            if self.logger:
                self.logger.info(f"{symbol}: Rejected - Poor R:R ({risk_reward:.2f})")
            return None
        
        if signal_type == SignalType.HOLD:
            return None
        
        # Generate reasoning
        reasoning_parts = []
        reasoning_parts.append(f"Regime: {regime_info['regime'].value}")
        reasoning_parts.append(f"Confluence: {confluence['direction']} ({confluence['strength']})")
        
        if trend_analysis['trend'] != 'UNKNOWN':
            reasoning_parts.append(f"Trend: {trend_analysis['trend']}")
        
        if momentum_analysis.get('macd_crossover'):
            reasoning_parts.append(f"MACD: {momentum_analysis['macd_signal']}")
        
        if structure_analysis['breakout'].get('breakout'):
            reasoning_parts.append(f"Breakout: {structure_analysis['breakout']['direction']}")
        
        reasoning = " | ".join(reasoning_parts)
        
        # Create indicator summary
        indicators_summary = {
            'trend': {
                'type': trend_analysis.get('trend'),
                'strength': trend_analysis.get('strength'),
                'price_vs_vwap': trend_analysis.get('price_vs_vwap')
            },
            'momentum': {
                'rsi': momentum_analysis.get('rsi_value'),
                'macd_signal': momentum_analysis.get('macd_signal'),
                'score': momentum_analysis.get('momentum_score')
            },
            'volatility': {
                'atr': atr_value,
                'regime': volatility_analysis.get('regime'),
                'bb_position': volatility_analysis.get('bb_position')
            },
            'structure': {
                'pattern': structure_analysis.get('pattern'),
                'breakout': structure_analysis['breakout'].get('breakout', False)
            },
            'confluence': {
                'score': confluence['score'],
                'agreement': confluence['agreement']
            }
        }
        
        # Update cooldown tracker
        self.last_signal_time[cooldown_key] = datetime.now()
        
        # Return signal
        signal = {
            'symbol': symbol,
            'timeframe': timeframe,
            'timestamp': datetime.now(),
            'signal_type': signal_type,
            'confidence': confidence,
            'regime': regime_info['regime'],
            'entry_price': current_price,
            'stop_loss': stop_loss,
            'targets': targets,
            'risk_reward': risk_reward,
            'reasoning': reasoning,
            'indicators': indicators_summary,
            'layer_scores': layer_scores
        }
        
        return signal
    
    def evaluate_signal_validity(self, signal: Dict[str, Any], 
                                current_df: pd.DataFrame) -> Dict[str, Any]:
        """Evaluate if an existing signal is still valid (invalidation logic).
        
        Args:
            signal: Previously generated signal
            current_df: Current market data
            
        Returns:
            Dictionary with validity status and reason
        """
        if current_df.empty:
            return {'valid': False, 'reason': 'No data available'}
        
        current_price = current_df.iloc[-1]['close']
        entry_price = signal['entry_price']
        stop_loss = signal['stop_loss']
        signal_type = signal['signal_type']
        
        # Check if stop-loss hit
        if signal_type == SignalType.BUY:
            if current_price <= stop_loss:
                return {'valid': False, 'reason': 'Stop-loss triggered'}
        elif signal_type == SignalType.SELL:
            if current_price >= stop_loss:
                return {'valid': False, 'reason': 'Stop-loss triggered'}
        
        # Check if targets hit
        for i, target in enumerate(signal['targets']):
            if signal_type == SignalType.BUY and current_price >= target:
                return {'valid': False, 'reason': f'Target {i+1} achieved'}
            elif signal_type == SignalType.SELL and current_price <= target:
                return {'valid': False, 'reason': f'Target {i+1} achieved'}
        
        # Re-calculate indicators and check if confluence dropped significantly
        current_df = self.calculate_all_indicators(current_df)
        trend_analysis = TrendIndicators.analyze_trend(current_df)
        momentum_analysis = MomentumIndicators.analyze_momentum(current_df)
        volatility_analysis = VolatilityIndicators.analyze_volatility(current_df)
        structure_analysis = StructureAnalysis.analyze_structure(current_df)
        
        regime_info = self.regime_detector.detect_regime(
            current_df, trend_analysis, volatility_analysis
        )
        
        layer_scores = self.confluence_calculator.calculate_layer_scores(
            trend_analysis, momentum_analysis, volatility_analysis,
            structure_analysis, current_price
        )
        
        confluence = self.confluence_calculator.calculate_confluence(
            layer_scores, regime_info['weights']
        )
        
        # Invalidate if confluence direction reversed
        original_direction = 'BULLISH' if signal_type == SignalType.BUY else 'BEARISH'
        current_direction = confluence['direction']
        
        if original_direction == 'BULLISH' and current_direction == 'BEARISH':
            return {'valid': False, 'reason': 'Confluence reversed to bearish'}
        elif original_direction == 'BEARISH' and current_direction == 'BULLISH':
            return {'valid': False, 'reason': 'Confluence reversed to bullish'}
        
        # Still valid
        return {'valid': True, 'reason': 'Signal intact', 'current_confluence': confluence['score']}
