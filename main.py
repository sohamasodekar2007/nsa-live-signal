"""Main Application Entry Point."""

import sys
import yaml
from pathlib import Path
from PyQt6.QtWidgets import QApplication

# Import from current directory structure
from core.logger import get_logger
from core.database import TradingDatabase
from data.fetcher import NSEDataFetcher
from portfolio.state import PortfolioState
from portfolio.risk_manager import RiskManager
from execution.execution_engine import RuleDrivenExecutionEngine
from gui.main_window import TradingEngineGUI

def main():
    """Initialize and run the trading engine."""
    
    # Setup Logging
    logger = get_logger()
    logger.info("Starting NSE Trading Engine (Root Mode)...")
    
    # PRELOAD NSE SYMBOLS AT STARTUP (Critical for scanner)
    from data.nse_symbol_loader import preload_nse_symbols
    symbol_count = preload_nse_symbols()
    logger.info(f"Loaded {symbol_count} NSE symbols for scanning.")
    
    try:
        # Load Config (create default if missing)
        config = {
            'database': {'path': 'data_storage/trading.db'},
            'portfolio': {'initial_capital': 100000},
            'risk': {'max_daily_loss_percent': 3}
        }
        
        # Initialize Core components
        db = TradingDatabase(config['database']['path'])
        
        # Initialize Data Layer
        fetcher = NSEDataFetcher(logger=logger)
        
        # Initialize Portfolio & Risk
        initial_capital = config['portfolio']['initial_capital']
        portfolio = PortfolioState(initial_capital, db, logger)
        risk_manager = RiskManager(config['risk'], portfolio, logger)
        
        # Initialize Execution Engine
        engine = RuleDrivenExecutionEngine(
            portfolio=portfolio,
            risk_manager=risk_manager,
            data_fetcher=fetcher,
            logger=logger
        )
        
        # Start GUI
        app = QApplication(sys.argv)
        # Apply Dark Theme
        app.setStyle('Fusion')
        
        window = TradingEngineGUI(engine)
        window.show()
        
        logger.info("GUI Started Successfully.")
        sys.exit(app.exec())
        
    except Exception as e:
        logger.error(f"Fatal Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
