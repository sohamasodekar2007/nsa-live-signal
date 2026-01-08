"""Performance analytics and metrics calculation."""

import pandas as pd
import numpy as np
from typing import Dict, List, Any
from datetime import datetime, timedelta


class PerformanceAnalytics:
    """Calculate portfolio performance metrics."""
    
    @staticmethod
    def calculate_returns_series(portfolio_snapshots: pd.DataFrame) -> pd.Series:
        """Calculate returns series from portfolio snapshots.
        
        Args:
            portfolio_snapshots: DataFrame with portfolio history
            
        Returns:
            Series of returns
        """
        if portfolio_snapshots.empty or len(portfolio_snapshots) < 2:
            return pd.Series()
        
        returns = portfolio_snapshots['total_capital'].pct_change().dropna()
        return returns
    
    @staticmethod
    def calculate_sharpe_ratio(returns: pd.Series, periods_per_year: int = 252,
                              risk_free_rate: float = 0.06) -> float:
        """Calculate Sharpe Ratio.
        
        Args:
            returns: Returns series
            periods_per_year: Trading periods per year (252 for daily)
            risk_free_rate: Annual risk-free rate
            
        Returns:
            Sharpe Ratio
        """
        if returns.empty or returns.std() == 0:
            return 0.0
        
        # Annualize returns and volatility
        mean_return = returns.mean() * periods_per_year
        std_return = returns.std() * np.sqrt(periods_per_year)
        
        sharpe = (mean_return - risk_free_rate) / std_return
        return sharpe
    
    @staticmethod
    def calculate_sortino_ratio(returns: pd.Series, periods_per_year: int = 252,
                               risk_free_rate: float = 0.06) -> float:
        """Calculate Sortino Ratio (downside deviation only).
        
        Args:
            returns: Returns series
            periods_per_year: Trading periods per year
            risk_free_rate: Annual risk-free rate
            
        Returns:
            Sortino Ratio
        """
        if returns.empty:
            return 0.0
        
        # Downside deviation (only negative returns)
        downside_returns = returns[returns < 0]
        if downside_returns.empty or downside_returns.std() == 0:
            return 0.0
        
        mean_return = returns.mean() * periods_per_year
        downside_std = downside_returns.std() * np.sqrt(periods_per_year)
        
        sortino = (mean_return - risk_free_rate) / downside_std
        return sortino
    
    @staticmethod
    def calculate_max_drawdown(portfolio_values: pd.Series) -> Dict[str, Any]:
        """Calculate maximum drawdown.
        
        Args:
            portfolio_values: Series of portfolio values
            
        Returns:
            Dictionary with max drawdown info
        """
        if portfolio_values.empty:
            return {'max_drawdown': 0, 'drawdown_duration': 0}
        
        # Calculate running maximum
        running_max = portfolio_values.expanding().max()
        
        # Calculate drawdown
        drawdown = (portfolio_values - running_max) / running_max * 100
        
        max_dd = drawdown.min()
        max_dd_idx = drawdown.idxmin()
        
        # Find recovery
        recovery_idx = None
        if max_dd_idx is not None:
            post_dd = portfolio_values[max_dd_idx:]
            peak_value = running_max[max_dd_idx]
            recovery = post_dd[post_dd >= peak_value]
            if not recovery.empty:
                recovery_idx = recovery.index[0]
        
        # Calculate duration
        if max_dd_idx is not None and recovery_idx is not None:
            duration = (recovery_idx - max_dd_idx).days if hasattr(recovery_idx - max_dd_idx, 'days') else 0
        else:
            duration = 0
        
        return {
            'max_drawdown': abs(max_dd),
            'drawdown_duration_days': duration,
            'max_dd_date': max_dd_idx
        }
    
    @staticmethod
    def calculate_trade_statistics(trades_df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate trade-level statistics.
        
        Args:
            trades_df: DataFrame with trade history
            
        Returns:
            Dictionary with trade statistics
        """
        if trades_df.empty:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'profit_factor': 0,
                'expectancy': 0
            }
        
        # Filter closed trades
        closed_trades = trades_df[trades_df['status'] == 'CLOSED']
        
        if closed_trades.empty:
            return {'total_trades': 0}
        
        total_trades = len(closed_trades)
        winning_trades = closed_trades[closed_trades['pnl'] > 0]
        losing_trades = closed_trades[closed_trades['pnl'] < 0]
        
        win_count = len(winning_trades)
        loss_count = len(losing_trades)
        
        win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
        
        avg_win = winning_trades['pnl'].mean() if not winning_trades.empty else 0
        avg_loss = losing_trades['pnl'].mean() if not losing_trades.empty else 0
        
        gross_profit = winning_trades['pnl'].sum() if not winning_trades.empty else 0
        gross_loss = abs(losing_trades['pnl'].sum()) if not losing_trades.empty else 0
        
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0
        
        # Expectancy = (win_rate * avg_win) + (loss_rate * avg_loss)
        expectancy = (win_rate/100 * avg_win) + ((100-win_rate)/100 * avg_loss)
        
        return {
            'total_trades': total_trades,
            'winning_trades': win_count,
            'losing_trades': loss_count,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'largest_win': winning_trades['pnl'].max() if not winning_trades.empty else 0,
            'largest_loss': losing_trades['pnl'].min() if not losing_trades.empty else 0,
            'gross_profit': gross_profit,
            'gross_loss': gross_loss,
            'profit_factor': profit_factor,
            'expectancy': expectancy
        }
    
    @staticmethod
    def generate_performance_report(portfolio_snapshots: pd.DataFrame,
                                   trades_df: pd.DataFrame,
                                   initial_capital: float) -> Dict[str, Any]:
        """Generate comprehensive performance report.
        
        Args:
            portfolio_snapshots: DataFrame with portfolio history
            trades_df: DataFrame with trade history
            initial_capital: Initial portfolio capital
            
        Returns:
            Dictionary with complete performance metrics
        """
        if portfolio_snapshots.empty:
            return {'error': 'No portfolio data available'}
        
        # Portfolio metrics
        current_capital = portfolio_snapshots.iloc[-1]['total_capital']
        total_return = ((current_capital - initial_capital) / initial_capital) * 100
        
        # Returns analysis
        returns = PerformanceAnalytics.calculate_returns_series(portfolio_snapshots)
        sharpe = PerformanceAnalytics.calculate_sharpe_ratio(returns)
        sortino = PerformanceAnalytics.calculate_sortino_ratio(returns)
        
        # Drawdown analysis
        portfolio_values = portfolio_snapshots['total_capital']
        dd_info = PerformanceAnalytics.calculate_max_drawdown(portfolio_values)
        
        # Trade statistics
        trade_stats = PerformanceAnalytics.calculate_trade_statistics(trades_df)
        
        # Time period
        start_date = portfolio_snapshots.iloc[0]['timestamp']
        end_date = portfolio_snapshots.iloc[-1]['timestamp']
        
        return {
            'period': {
                'start': start_date,
                'end': end_date,
                'duration_days': (pd.to_datetime(end_date) - pd.to_datetime(start_date)).days
            },
            'returns': {
                'total_return_pct': total_return,
                'initial_capital': initial_capital,
                'final_capital': current_capital,
                'total_pnl': current_capital - initial_capital
            },
            'risk_metrics': {
                'sharpe_ratio': sharpe,
                'sortino_ratio': sortino,
                'max_drawdown_pct': dd_info['max_drawdown'],
                'max_drawdown_duration_days': dd_info['drawdown_duration_days']
            },
            'trade_statistics': trade_stats
        }
