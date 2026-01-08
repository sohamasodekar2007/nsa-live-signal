"""Entry price logic for different entry types."""

import pandas as pd
from typing import Dict, Any, Optional
from enum import Enum


class EntryType(Enum):
    """Types of entry strategies."""
    PULLBACK = "PULLBACK"
    BREAKOUT_RETEST = "BREAKOUT_RETEST"
    MOMENTUM_CONTINUATION = "MOMENTUM_CONTINUATION"


class EntryLogic:
    """Determine optimal entry type and price."""
    
    @staticmethod
    def identify_entry_type(df: pd.DataFrame, 
                           trend_analysis: Dict[str, Any],
                           structure_analysis: Dict[str, Any],
                           current_price: float) -> Dict[str, Any]:
        """Identify the best entry type for current market conditions.
        
        Args:
            df: DataFrame with OHLCV and indicators
            trend_analysis: Trend analysis output
            structure_analysis: Structure analysis output
            current_price: Current market price
            
        Returns:
            Dictionary with entry type and details
        """
        if df.empty or len(df) < 50:
            return {
                'entry_type': None,
                'entry_price': current_price,
                'valid': False,
                'reason': 'Insufficient data'
            }
        
        latest = df.iloc[-1]
        
        # Check for pullback entry
        pullback_setup = EntryLogic._check_pullback_entry(
            df, trend_analysis, current_price
        )
        
        # Check for breakout-retest entry
        breakout_setup = EntryLogic._check_breakout_retest(
            df, structure_analysis, current_price
        )
        
        # Check for momentum continuation
        momentum_setup = EntryLogic._check_momentum_continuation(
            df, trend_analysis, current_price
        )
        
        # Prioritize entry types based on reliability
        if breakout_setup['valid'] and breakout_setup['volume_confirmed']:
            return breakout_setup
        elif pullback_setup['valid']:
            return pullback_setup
        elif momentum_setup['valid']:
            return momentum_setup
        else:
            return {
                'entry_type': None,
                'entry_price': current_price,
                'valid': False,
                'reason': 'No valid entry setup identified'
            }
    
    @staticmethod
    def _check_pullback_entry(df: pd.DataFrame,
                              trend_analysis: Dict[str, Any],
                              current_price: float) -> Dict[str, Any]:
        """Check for pullback entry to EMA or VWAP.
        
        Args:
            df: DataFrame with indicators
            trend_analysis: Trend analysis
            current_price: Current price
            
        Returns:
            Entry setup details
        """
        latest = df.iloc[-1]
        
        # Need a clear trend
        if trend_analysis.get('trend') not in ['BULLISH', 'BEARISH']:
            return {'valid': False, 'entry_type': EntryType.PULLBACK}
        
        is_bullish = trend_analysis['trend'] == 'BULLISH'
        
        # Check proximity to support levels (EMA, VWAP)
        ema_21 = latest.get('ema_21', 0)
        ema_50 = latest.get('ema_50', 0)
        vwap = latest.get('vwap', 0)
        
        if is_bullish:
            # Bullish pullback: price near EMA-21 or VWAP but above them
            near_ema21 = abs(current_price - ema_21) / ema_21 < 0.01  # Within 1%
            near_vwap = abs(current_price - vwap) / vwap < 0.01
            
            if (near_ema21 or near_vwap) and current_price > ema_50:
                return {
                    'valid': True,
                    'entry_type': EntryType.PULLBACK,
                    'entry_price': max(ema_21, vwap),  # Enter at support
                    'use_limit_order': True,
                    'limit_price': max(ema_21, vwap) * 1.001,  # 0.1% above
                    'reason': 'Bullish pullback to EMA/VWAP support'
                }
        else:
            # Bearish pullback: price near EMA-21 or VWAP but below them
            near_ema21 = abs(current_price - ema_21) / ema_21 < 0.01
            near_vwap = abs(current_price - vwap) / vwap < 0.01
            
            if (near_ema21 or near_vwap) and current_price < ema_50:
                return {
                    'valid': True,
                    'entry_type': EntryType.PULLBACK,
                    'entry_price': min(ema_21, vwap),  # Enter at resistance
                    'use_limit_order': True,
                    'limit_price': min(ema_21, vwap) * 0.999,  # 0.1% below
                    'reason': 'Bearish pullback to EMA/VWAP resistance'
                }
        
        return {'valid': False, 'entry_type': EntryType.PULLBACK}
    
    @staticmethod
    def _check_breakout_retest(df: pd.DataFrame,
                               structure_analysis: Dict[str, Any],
                               current_price: float) -> Dict[str, Any]:
        """Check for breakout-retest entry.
        
        Args:
            df: DataFrame with indicators
            structure_analysis: Structure analysis
            current_price: Current price
            
        Returns:
            Entry setup details
        """
        breakout = structure_analysis.get('breakout', {})
        
        if not breakout.get('breakout', False):
            return {'valid': False, 'entry_type': EntryType.BREAKOUT_RETEST}
        
        direction = breakout.get('direction')
        level = breakout.get('level', current_price)
        volume_confirmed = breakout.get('volume_confirmed', False)
        
        # Check if price has retested the breakout level
        if direction == 'BULLISH':
            # Price should be slightly above the breakout level (retest from above)
            retesting = current_price > level and current_price < level * 1.02
            
            if retesting:
                return {
                    'valid': True,
                    'entry_type': EntryType.BREAKOUT_RETEST,
                    'entry_price': level * 1.002,  # Enter just above breakout level
                    'use_limit_order': not volume_confirmed,  # Market order if strong volume
                    'limit_price': level * 1.002 if not volume_confirmed else None,
                    'volume_confirmed': volume_confirmed,
                    'reason': f'Bullish breakout retest at ₹{level:.2f}'
                }
        
        elif direction == 'BEARISH':
            # Price should be slightly below the breakdown level
            retesting = current_price < level and current_price > level * 0.98
            
            if retesting:
                return {
                    'valid': True,
                    'entry_type': EntryType.BREAKOUT_RETEST,
                    'entry_price': level * 0.998,  # Enter just below breakdown level
                    'use_limit_order': not volume_confirmed,
                    'limit_price': level * 0.998 if not volume_confirmed else None,
                    'volume_confirmed': volume_confirmed,
                    'reason': f'Bearish breakdown retest at ₹{level:.2f}'
                }
        
        return {'valid': False, 'entry_type': EntryType.BREAKOUT_RETEST}
    
    @staticmethod
    def _check_momentum_continuation(df: pd.DataFrame,
                                    trend_analysis: Dict[str, Any],
                                    current_price: float) -> Dict[str, Any]:
        """Check for momentum continuation entry.
        
        Args:
            df: DataFrame with indicators
            trend_analysis: Trend analysis
            current_price: Current price
            
        Returns:
            Entry setup details
        """
        if len(df) < 20:
            return {'valid': False, 'entry_type': EntryType.MOMENTUM_CONTINUATION}
        
        latest = df.iloc[-1]
        
        # Check for strong trend with momentum
        trend_strength = trend_analysis.get('strength', 0)
        
        if trend_strength < 70:  # Need strong trend
            return {'valid': False, 'entry_type': EntryType.MOMENTUM_CONTINUATION}
        
        # Check volume expansion
        avg_volume = df.tail(20)['volume'].mean()
        current_volume = latest['volume']
        volume_expansion = current_volume > avg_volume * 1.2
        
        # Check price momentum (higher highs / lower lows)
        recent_high = df.tail(5)['high'].max()
        recent_low = df.tail(5)['low'].min()
        
        is_bullish = trend_analysis['trend'] == 'BULLISH'
        
        if is_bullish:
            making_higher_highs = latest['high'] >= recent_high
            
            if making_higher_highs and volume_expansion:
                return {
                    'valid': True,
                    'entry_type': EntryType.MOMENTUM_CONTINUATION,
                    'entry_price': current_price,
                    'use_limit_order': False,  # Market order for momentum
                    'limit_price': None,
                    'volume_confirmed': True,
                    'reason': 'Strong bullish momentum continuation with volume'
                }
        else:
            making_lower_lows = latest['low'] <= recent_low
            
            if making_lower_lows and volume_expansion:
                return {
                    'valid': True,
                    'entry_type': EntryType.MOMENTUM_CONTINUATION,
                    'entry_price': current_price,
                    'use_limit_order': False,
                    'limit_price': None,
                    'volume_confirmed': True,
                    'reason': 'Strong bearish momentum continuation with volume'
                }
        
        return {'valid': False, 'entry_type': EntryType.MOMENTUM_CONTINUATION}
