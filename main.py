from src.backtester.engine import DataLoader, Backtest, MetricsCalculator

# CHANGE THESE PATHS TO YOUR LOCAL FILES
FOLDER_ASSETS_PRICES = "Data_Curator/"
PORTFOLIO_PATH = "portfolio_weights.csv"
BENCHMARK_PATH = "Benchmark.csv"


def run_pipeline():
    print("=== Starting Backtest Pipeline ===")
    
    # Load data
    loader = DataLoader()
    try:
        weights = loader.load_portfolio(PORTFOLIO_PATH)
        benchmark = loader.load_benchmark(BENCHMARK_PATH) # Opcional
    except Exception as e:
        print(f"Error while loading files: {e}")
        return

    # Backtest execution
    engine = Backtest(prices_path=FOLDER_ASSETS_PRICES, initial_capital=100000.0, commission_rate=0.002)
    try:
        history = engine.run(weights_df=weights, start_date="01-01-2018", end_date="01-04-2026")
        print("Backtest executed successfully.")
    except ValueError as e:
        print(f"Backtest failed:\n{e}")
        return

    # Calculate metrics and generate report
    calculator = MetricsCalculator(portfolio_history=history, benchmark_prices=benchmark)
    report = calculator.summary()
    
    print("\n=== BACKTEST REPORT ===")
    print(report)
    
    # Save results to CSV
    history.to_csv("outputs/backtest_results.csv")
    print("\nHistory saved to 'outputs/backtest_results.csv'")

if __name__ == "__main__":
    run_pipeline()