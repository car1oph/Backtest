# Backtester Engine

A modular Python library for simulating and running daily backtests of investment strategies with dynamic asset allocation. The engine is optimized to handle common data imperfections, such as asset survivorship bias and liquidity after commissions.

---

## Features

* Daily simulation of portfolios with dynamic, date-based rebalancing weights.
* Built-in handling of commissions and cash positions.
* Handles survivorship of the assets.
* Risk and performance metrics out of the box: CAGR, volatility, Sharpe, Sortino, max drawdown, VaR, CVaR, and alpha vs. a benchmark.

---

## Project Structure

```text
BACKTESTER/
│
├── src/
│   └── backtester/          # Central library code
│       ├── __init__.py      # Package initializer
│       └── engine.py        # Core engine logic
│
├── Benchmark.csv             # Historical prices of the benchmark
├── portfolio_weights.csv     # Historical weights of the strategy
├── main.py                   # Executable script for local testing
├── pyproject.toml             # Pip packaging configuration
└── README.md                  # Main documentation
```

## Requirements

* Python >= 3.9
* pandas >= 2.0.0
* numpy >= 2.0.0
* pyarrow >= 12.0.0

These dependencies are installed automatically when you install the package.

## Installation

This project is structured as a native Python package, so you can install it directly from this GitHub repository without needing to clone or download it manually.

### Standard installation (usage only)

If you only want to use the engine in a script and don't need to modify any of the underlying logic:

```Bash
pip install git+https://github.com/car1oph/Backtest.git
```

### Developer installation

If you want to clone the project to make modifications to the engine or extend its statistical metrics:

```Bash
# Clone the repository
git clone https://github.com/car1oph/Backtest.git
cd Backtest

pip install -e .
```

## Usage Example

The package exposes three main classes: `DataLoader`, `Backtest`, and `MetricsCalculator`.

```python
from backtester.engine import DataLoader, Backtest, MetricsCalculator

PORTFOLIO_PATH = "YOUR_PATH_TO_portfolio_weights.csv"
BENCHMARK_PATH = "YOUR_PATH_TO_benchmark.csv"
FOLDER_ASSET_PRICES = "YOUR_PATH_TO_FOLDER_ASSET_PRICES/"

# Initialize and load the portfolio and benchmark
loader = DataLoader()
weights = loader.load_portfolio(PORTFOLIO_PATH)
benchmark = loader.load_benchmark(BENCHMARK_PATH) # Opcional

# Initialize and run the Backtest
engine = Backtest(prices_path=FOLDER_ASSETS_PRICES, initial_capital=100000.0, commission_rate=0.002)
history = engine.run(weights_df=weights, fecha_inicio="01-01-2018", fecha_fin="01-04-2026")

# Initialize and calculate the metrics
calculator = MetricsCalculator(portfolio_history=history, benchmark_prices=benchmark)
report = calculator.summary()

print("\n=== BACKTEST REPORT ===")
print(report) # Print the metrics

# Save portfolio valuation to csv
history.to_csv("outputs/backtest_results.csv")
```

A full runnable version of this example, using the sample data included in this repo (`portfolio_weights.csv` and `Benchmark.csv`), is available in `main.py`. Note that prices for each individual asset must also be provided as a separate `.csv` file, with all such files grouped together in a single folder. For this example, that price data is available in [this Google Drive folder](https://drive.google.com/drive/folders/16FX9FNkqPv2eKyrAVhKi1O_GufxwK-us?usp=sharing) — this is just sample data for the demo, not a dependency of the package itself.

To run the example:

1. Open `main.py` and update the file/folder paths at the top of the script to match your setup.
2. Make sure an `output` folder exists in your working directory.
3. Run the script and wait for it to finish.

The resulting portfolio trajectory will be saved to the `outputs/` folder once the backtest completes. We recommend using `matplotlib` or `seaborn` to plot the portfolio's trajectory against the benchmark.

### Sample Output

`MetricsCalculator.report()` returns a summary like this:

```text
=== REPORTE DE RENDIMIENTO Y RIESGO ===
Total Return            2.186629
CAGR                    0.150951
Volatilidad Anual        0.287145
Sharpe Ratio Anual       0.386393
Sortino Ratio Anual      0.478663
Max Drawdown            -0.397980
VaR (5%)                -0.028325
CVaR (5%)               -0.043367
Total Commisions     17304.315527
Alpha                    0.031357
dtype: float64
```

## Data Requirements

To ensure the engine runs correctly, your input data must follow these rules:

* **Asset prices**: The prices folder must contain one `.csv` file per asset, named after the asset's identifier (e.g., `NVDA.csv`). Each file must include a date column (`date` or `m_date`) and a closing price column (`close`, `m_close`, or any uppercase variation of these).
* **Portfolio weights**: The `portfolio_weights.csv` file must contain one column per asset plus a column for rebalancing dates, with cell values representing each asset's weight. The table may also be transposed, with one row per asset and the columns reserved for dates. Every asset listed here must have a corresponding price `.csv` file — except for the reserved keyword `cash`, which is treated as an asset but does not require a `CASH.csv` file.
* **Benchmark (optional)**: The benchmark file requires a daily valuation with `Date` and `Close` columns. It is only used to calculate the alpha ($\alpha$) parameter in `MetricsCalculator` and for comparison against other performance metrics.

## Contributing

This project doesn't have a formal contributing process yet. If you'd like to report a bug, suggest a feature, or contribute changes, feel free to reach out at **carlo.pena.hdz@gmail.com**.

## License

This project does not currently have a license. All rights are reserved by the author until one is specified.
Feel free to use the scripts and the engine the way you prefer.

---
