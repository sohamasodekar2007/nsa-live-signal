"""Hybrid stop-loss calculation system."""

import pandas as pd
from typing import Dict, Any
from core.enums import SignalType


class HybridStopLoss:
    """Calculate stop-loss using hybrid approach."""
    
    @staticmethod
    def calculate_hybrid_stop(df: pd.DataFrame,
                             entry_price: float,
                             signal_type: SignalType,
                             atr_multiplier: float = 1.5) -> Dict[str, Any]:
        """Calculate stop-loss using hybrid model.
        
        Uses the maximum of:
        1. ATR-based stop
        2. Recent swing high/low
        3. VWAP invalidation level
        
        Args:
            df: DataFrame with price data and indicators
            entry_price: Entry price
            signal_type: BUY or SELL
            atr_multiplier: ATR multiplier for stop distance
            
        Returns:
            Dictionary with stop-loss details
        """
        if df.empty or len(df) < 20:
            # Fallback to simple percentage stop
            fallback_stop = entry_price * 0.98 if signal_type == SignalType.BUY else entry_price * 1.02
            return {
                'stop_loss': fallback_stop,
                'method': 'FALLBACK',
                'stop_distance': abs(entry_price - fallback_stop),
                'stop_distance_pct': 2.0
            }
        
        latest = df.iloc[-1]
        
        # 1. ATR-based stop
        atr = latest.get('atr', entry_price * 0.02)
        if signal_type == SignalType.BUY:
            atr_stop = entry_price - (atr * atr_multiplier)
        else:
            atr_stop = entry_price + (atr * atr_multiplier)
        
        # 2. Swing high/low stop
        lookback = min(20, len(df))
        recent_data = df.tail(lookback)
        
        if signal_type == SignalType.BUY:
            swing_low = recent_data['low'].min()
            swing_stop = swing_low * 0.998  # Slightly below swing low
        else:
            swing_high = recent_data['high'].max()
            swing_stop = swing_high * 1.002  # Slightly above swing high
        
        # 3. VWAP invalidation stop
        vwap = latest.get('vwap', entry_price)
        if signal_type == SignalType.BUY:
            vwap_stop = vwap * 0.995  # 0.5% below VWAP
        else:
            vwap_stop = vwap * 1.005  # 0.5% above VWAP
        
        # Choose the stop that gives maximum protection (furthest from entry)
        if signal_type == SignalType.BUY:
            # For buy, choose the highest stop (closest to entry = tightest)
            # But we want reasonable protection, so check all three
            candidate_stops = {
                'ATR': atr_stop,
                'SWING': swing_stop,
                'VWAP': vwap_stop
            }
            
            # Use the maximum of these (most conservative for long)
            final_stop = max(candidate_stops.values())
            method = [k for k, v in candidate_stops.items() if v == final_stop][0]
            
        else:  # SELL
            # For sell, choose the lowest stop (closest to entry)
            candidate_stops = {
                'ATR': atr_stop,
                'SWING': swing_stop,
                'VWAP': vwap_stop
            }
            
            # Use the minimum of these (most conservative for short)
            final_stop = min(candidate_stops.values())
            method = [k for k, v in candidate_stops.items() if v == final_stop][0]
        
        # Validate stop is reasonable (not too tight, not too wide)
        stop_distance = abs(entry_price - final_stop)
        stop_distance_pct = (stop_distance / entry_price) * 100
        
        # Enforce minimum and maximum stop distances
        min_stop_pct = 0.5  # Minimum 0.5%
        max_stop_pct = 5.0  # Maximum 5%
        
        if stop_distance_pct < min_stop_pct:
            # Stop too tight, widen it
            if signal_type == SignalType.BUY:
                final_stop = entry_price * (1 - min_stop_pct/100)
            else:
                final_stop = entry_price * (1 + min_stop_pct/100)
            method = f'{method}_ADJUSTED_MIN'
            stop_distance_pct = min_stop_pct
            
        elif stop_distance_pct > max_stop_pct:
            # Stop too wide, tighten it
            if signal_type == SignalType.BUY:
                final_stop = entry_price * (1 - max_stop_pct/100)
            else:
                final_stop = entry_price * (1 + max_stop_pct/100)
            method = f'{method}_ADJUSTED_MAX'
            stop_distance_pct = max_stop_pct
        
        return {
            'stop_loss': final_stop,
            'method': method,
            'stop_distance': abs(entry_price - final_stop),
            'stop_distance_pct': stop_distance_pct,
            'atr_stop': atr_stop,
            'swing_stop': swing_stop,
            'vwap_stop': vwap_stop,
            'atr_value': atr
        }
    
    @staticmethod
    def calculate_trailing_stop(entry_price: float,
                                current_price: float,
                                signal_type: SignalType,
                                atr: float,
                                trailing_multiplier: float = 2.0) -> float:
        """Calculate trailing stop-loss.
        
        Args:
            entry_price: Original entry price
            current_price: Current market price
            signal_type: BUY or SELL
            atr: Current ATR value
            trailing_multiplier: ATR multiplier for trailing distance
            
        Returns:
            Trailing stop price
        """
        if signal_type == SignalType.BUY:
            # Trail stop upward as price increases
            trailing_stop = current_price - (atr * trailing_multiplier)
            # Ensure trail stop never goes below entry (for profits)
            if current_price <= entry_price:
                return entry_price * 0.98  # Original stop
            return max(trailing_stop, entry_price)
        
        else:  # SELL
            # Trail stop downward as price decreases
            trailing_stop = current_price + (atr * trailing_multiplier)
            if current_price >= entry_price:
                return entry_price * 1.02
            return min(trailing_stop, entry_price)
