"""Example usage of the enhanced rule-driven execution engine."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import yaml
from core.database import TradingDatabase
from core.logger import get_logger
from data.fetcher import NSEDataFetcher
from portfolio.state import PortfolioState
from portfolio.risk_manager import RiskManager
from execution.execution_engine import RuleDrivenExecutionEngine


def main():
    """Example of using the rule-driven execution engine."""
    
    # Load configuration
    with open('config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    # Initialize components
    logger = get_logger()
    db = TradingDatabase()
    data_fetcher = NSEDataFetcher(logger=logger)
    
    # Portfolio
    initial_capital = config.get('portfolio', {}).get('initial_capital', 100000)
    portfolio = PortfolioState(initial_capital, db, logger)
    
    # Risk manager
    risk_manager = RiskManager(config.get('risk', {}), portfolio, logger)
    
    # Enhanced execution engine
    execution_engine = RuleDrivenExecutionEngine(
        portfolio=portfolio,
        risk_manager=risk_manager,
        data_fetcher=data_fetcher,
        min_confidence=70.0,  # 70% confidence threshold
        min_rr=2.0,          # Minimum 1:2 risk-reward
        risk_per_trade_pct=1.0,  # 1% risk per trade
        logger=logger
    )
    
    # Example: Evaluate trade for a symbol
    symbols_to_evaluate = ['RELIANCE.NS', 'TCS.NS', 'INFY.NS']
    
    print("\n" + "="*80)
    print("NSE RULE-DRIVEN EXECUTION ENGINE - EVALUATION")
    print("="*80 + "\n")
    
    for symbol in symbols_to_evaluate:
        print(f"\n{'─'*80}")
        print(f"Evaluating: {symbol}")
        print(f"{'─'*80}\n")
        
        # Evaluate with multi-timeframe analysis
        trade_order = execution_engine.evaluate_trade_opportunity(
            symbol=symbol,
            higher_tf='15m',  # Higher timeframe for trend
            lower_tf='5m'     # Lower timeframe for entry timing
        )
        
        # Display result
        if trade_order['ACTION'] == 'EXECUTE_TRADE':
            print(f"✅ TRADE APPROVED")
            print(f"\nTrade Details:")
            print(f"  Trade ID: {trade_order['trade_id']}")
            print(f"  Symbol: {trade_order['symbol']}")
            print(f"  Direction: {trade_order['direction']}")
            print(f"  Entry Price: ₹{trade_order['entry_price']:.2f}")
            print(f"  Entry Type: {trade_order['entry_type']}")
            print(f"  Quantity: {trade_order['quantity']} shares")
            print(f"  Capital Required: ₹{trade_order['capital_required']:,.2f}")
            
            print(f"\nRisk Management:")
            print(f"  Stop-Loss: ₹{trade_order['stop_loss']:.2f} ({trade_order['stop_method']})")
            print(f"  Risk Amount: ₹{trade_order['risk_amount']:,.2f} ({trade_order['risk_pct']:.2f}%)")
            print(f"  Risk-Reward: {trade_order['risk_reward']:.2f}")
            
            print(f"\nTargets (Partial Booking):")
            for i, target in enumerate(trade_order['targets'], 1):
                print(f"  T{i}: ₹{target['price']:.2f} - Book {target['book_percentage']}% ({target['action']})")
            
            print(f"\nConfidence & Reasoning:")
            print(f"  Confidence: {trade_order['confidence']:.1f}%")
            print(f"  Regime: {trade_order['regime']}")
            print(f"  MTF Alignment: {trade_order['mtf_alignment']}")
            print(f"  Reasoning: {trade_order['reasoning']}")
            
            # Ask for confirmation (in production, this would auto-execute or require manual approval)
            user_input = input(f"\nExecute this trade? (y/n): ")
            if user_input.lower() == 'y':
                success = execution_engine.execute_trade(trade_order)
                if success:
                    print(f"✅ Trade executed successfully!")
                else:
                    print(f"❌ Trade execution failed")
            else:
                print(f"⏭️ Trade skipped by user")
        
        else:
            # HOLD decision
            print(f"⏸️ HOLD DECISION")
            print(f"  Symbol: {trade_order['symbol']}")
            print(f"  Reason: {trade_order['reason']}")
            print(f"  Timestamp: {trade_order['timestamp']}")
    
    # Display portfolio summary
    print(f"\n{'='*80}")
    print("PORTFOLIO SUMMARY")
    print(f"{'='*80}\n")
    
    summary = portfolio.get_portfolio_summary()
    print(f"Total Capital: ₹{summary['total_capital']:,.2f}")
    print(f"Available: ₹{summary['available_capital']:,.2f}")
    print(f"Invested: ₹{summary['invested_capital']:,.2f}")
    print(f"Open Positions: {summary['open_positions']}")
    print(f"Total P&L: ₹{summary['total_pnl']:,.2f} ({summary['total_return_pct']:+.2f}%)")
    
    # Display trade lifecycle summary
    print(f"\n{'='*80}")
    print("TRADE LIFECYCLE SUMMARY")
    print(f"{'='*80}\n")
    
    perf = execution_engine.trade_lifecycle_manager.get_performance_summary()
    if perf.get('total_trades', 0) > 0:
        print(f"Total Trades: {perf['total_trades']}")
        print(f"Win Rate: {perf['win_rate']:.1f}%")
        print(f"Total P&L: ₹{perf['total_pnl']:,.2f}")
        print(f"Avg Win: ₹{perf['avg_win']:,.2f}")
        print(f"Avg Loss: ₹{perf['avg_loss']:,.2f}")
    else:
        print("No completed trades yet")


if __name__ == '__main__':
    main()
