"""Target calculation and partial profit booking system."""

import pandas as pd
from typing import Dict, Any, List, Tuple
from core.enums import SignalType


class TargetCalculator:
    """Calculate targets with partial profit booking."""
    
    @staticmethod
    def calculate_targets(entry_price: float,
                         stop_loss: float,
                         signal_type: SignalType,
                         df: pd.DataFrame,
                         min_rr: float = 2.0) -> Dict[str, Any]:
        """Calculate targets using risk-reward and structure.
        
        Args:
            entry_price: Entry price
            stop_loss: Stop-loss price
            signal_type: BUY or SELL
            df: DataFrame with price data
            min_rr: Minimum risk-reward ratio
            
        Returns:
            Dictionary with target details and booking percentages
        """
        risk = abs(entry_price - stop_loss)
        
        # Calculate RR-based targets
        if signal_type == SignalType.BUY:
            target_1r = entry_price + (risk * 1.0)  # 1R (1:1)
            target_2r = entry_price + (risk * min_rr)  # 2R (default)
            target_3r = entry_price + (risk * 3.0)  # 3R
        else:
            target_1r = entry_price - (risk * 1.0)
            target_2r = entry_price - (risk * min_rr)
            target_3r = entry_price - (risk * 3.0)
        
        # Get structure-based targets if data available
        structure_targets = TargetCalculator._get_structure_targets(
            df, entry_price, signal_type
        )
        
        # Combine RR and structure targets
        final_targets = []
        
        # Target 1: Partial book at 1R or nearest structure
        t1 = target_1r
        if structure_targets:
            # Find nearest structure level to 1R
            if signal_type == SignalType.BUY:
                nearby = [s for s in structure_targets if s > entry_price and s <= target_2r]
            else:
                nearby = [s for s in structure_targets if s < entry_price and s >= target_2r]
            
            if nearby:
                t1 = nearby[0] if signal_type == SignalType.BUY else nearby[-1]
        
        final_targets.append({
            'price': t1,
            'rr_ratio': abs(t1 - entry_price) / risk,
            'book_percentage': 50,  # Book 50% at first target
            'action': 'PARTIAL_EXIT_50%',
            'type': 'TARGET_1'
        })
        
        # Target 2: Book another portion at 2R
        final_targets.append({
            'price': target_2r,
            'rr_ratio': min_rr,
            'book_percentage': 30,  # Book 30% more (80% total)
            'action': 'PARTIAL_EXIT_30%',
            'type': 'TARGET_2'
        })
        
        # Target 3: Trail remaining with 3R as final target
        final_targets.append({
            'price': target_3r,
            'rr_ratio': 3.0,
            'book_percentage': 20,  # Remaining 20%
            'action': 'TRAIL_OR_EXIT',
            'type': 'TARGET_3_TRAIL'
        })
        
        return {
            'targets': final_targets,
            'min_rr': min_rr,
            'risk': risk,
            'structure_levels': structure_targets,
            'profit_booking_plan': {
                'T1': '50% at 1R',
                'T2': '30% at 2R (80% total)',
                'T3': '20% trailing to 3R'
            }
        }
    
    @staticmethod
    def _get_structure_targets(df: pd.DataFrame,
                               entry_price: float,
                               signal_type: SignalType) -> List[float]:
        """Get structure-based target levels.
        
        Args:
            df: DataFrame with price data
            entry_price: Entry price
            signal_type: BUY or SELL
            
        Returns:
            List of structure-based target prices
        """
        if df.empty or len(df) < 20:
            return []
        
        lookback = min(50, len(df))
        recent_data = df.tail(lookback)
        
        structure_levels = []
        
        if signal_type == SignalType.BUY:
            # Find resistance levels above entry
            swing_highs = []
            for i in range(2, len(recent_data) - 2):
                if (recent_data.iloc[i]['high'] > recent_data.iloc[i-1]['high'] and
                    recent_data.iloc[i]['high'] > recent_data.iloc[i-2]['high'] and
                    recent_data.iloc[i]['high'] > recent_data.iloc[i+1]['high'] and
                    recent_data.iloc[i]['high'] > recent_data.iloc[i+2]['high']):
                    swing_highs.append(recent_data.iloc[i]['high'])
            
            # Filter for levels above entry
            structure_levels = sorted([h for h in swing_highs if h > entry_price])
        
        else:  # SELL
            # Find support levels below entry
            swing_lows = []
            for i in range(2, len(recent_data) - 2):
                if (recent_data.iloc[i]['low'] < recent_data.iloc[i-1]['low'] and
                    recent_data.iloc[i]['low'] < recent_data.iloc[i-2]['low'] and
                    recent_data.iloc[i]['low'] < recent_data.iloc[i+1]['low'] and
                    recent_data.iloc[i]['low'] < recent_data.iloc[i+2]['low']):
                    swing_lows.append(recent_data.iloc[i]['low'])
            
            # Filter for levels below entry
            structure_levels = sorted([l for l in swing_lows if l < entry_price], reverse=True)
        
        return structure_levels[:3]  # Return top 3 structure levels
    
    @staticmethod
    def should_trail_stop(current_price: float,
                         entry_price: float,
                         highest_price: float,
                         signal_type: SignalType,
                         profit_pct: float = 1.0) -> bool:
        """Determine if trailing stop should be activated.
        
        Args:
            current_price: Current market price
            entry_price: Entry price
            highest_price: Highest price since entry (for BUY)
            signal_type: BUY or SELL
            profit_pct: Minimum profit % to activate trailing
            
        Returns:
            True if should start trailing
        """
        if signal_type == SignalType.BUY:
            current_profit_pct = ((current_price - entry_price) / entry_price) * 100
            return current_profit_pct >= profit_pct
        else:
            current_profit_pct = ((entry_price - current_price) / entry_price) * 100
            return current_profit_pct >= profit_pct
