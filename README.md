# Backtester Engine

A Python library designed to make simulation and daily backtesting of investment strategies with dynamic asset allocation. The engine is optimized to manage some imperfections of the data like asset survival or liquidity after commissions.

---

## Estructura del Proyecto

```text
BACKTESTER/
│
├── src/
│   └── backtester/          # Código central de la librería
│       ├── __init__.py      # Inicializador del paquete
│       └── engine.py        # Clase principal BacktestEngine
│
├── Benchmark.csv            # Matriz de precios históricos de referencia (Ejemplo)
├── portfolio_weights.csv    # Histórico de pesos de la estrategia (Ejemplo)
├── main.py                  # Script ejecutable para pruebas locales
├── pyproject.toml           # Configuración del empaquetado pip
└── README.md                # Documentación principal
```

## Instalation

It is structures as a Python native package, so the users can install ir directyle from this GitHub repository without the need of clone or download it.

### Only-usage instalation

You should write this on your terminal.

```Bash
pip install git+[https://github.com/car1oph/Backtest.git](https://github.com/car1oph/Backtest.git)
```

### Developer instalation

If you wish to clone the project, make modifications in the engine or extend the statistics metrics:

```Bash
# Clonar el repositorio
git clone [https://github.com/car1oph/Backtest.git](https://github.com/car1oph/Backtest.git)
cd Backtest

pip install -e .
```

## Usage Example

Small usage example:
Here I show how to initialize the engine using the example data included in this repo `portfolio_weights.csv` and `Benchmark.csv`. However, the prices of every individual asset is needed on a `.csv`, and then all those files grouped in a folder; for this particular example, that data can de found in [this google drive](https://drive.google.com/drive/folders/16FX9FNkqPv2eKyrAVhKi1O_GufxwK-us?usp=sharing).

To see and run the example, you will need to open the `main.py` file, then on the firsts lines change the paths for the files and folder you need; and make sure it exist a folder named `output` on your working directory

## Spetial requirements for the data

To ensure the correct functioning of the algorithm, the inputs must satisfy the next rules:

* **Initial Data**: In the folder of the prices it must be one `.csv` file for each asset, named with the identifier of the asset (p.e. `NVDA.csv`) and in the inside of the file, it must be one column named `date`, `m_date` and another column named `close` or `m_close` or any uppercase variation of those.
* **Portfolio Wheights**: In the `portfolio_weights.csv` file, you should have one column per asset, and another column for the rebalancing dates, and the values filling tha DataFrame must be the weights of the assets. It can also be transposed, with one column for all the assets and the first row for the dates. Every asset in thes file must have its own `.csv` of prices; there is a reserved word `cash` treated as another asset, but without the need of having a `CASH.csv`.
* **Benchmarks**: For the benchmark, which is optional, you need a daily valuation of some portfolio with the *Date* and the *Close* columns. The benchmark is only needed for calculating the $\alpha$ parameter with the MetricsCalculator, and for comparision with all the other metrics.

---
