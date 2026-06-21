from src.backtester.engine import DataLoader, Backtest, MetricsCalculator

# Cambiar las rutas a tus archivos locales
CARPETA_PRECIOS_ACCIONES = "Data_Curator/"
RUTA_PORTAFOLIO = "portfolio_weights.csv"
RUTA_BENCHMARK = "Benchmark.csv"


def run_pipeline():
    print("=== Iniciando Pipeline de Backtesting ===")
    
    # 1. Carga de datos
    loader = DataLoader()
    try:
        weights = loader.load_portfolio(RUTA_PORTAFOLIO)
        benchmark = loader.load_benchmark(RUTA_BENCHMARK) # Opcional
    except Exception as e:
        print(f"Error al cargar los archivos: {e}")
        return

    # 2. Ejecución del Backtest
    engine = Backtest(prices_path=CARPETA_PRECIOS_ACCIONES, initial_capital=100000.0, commission_rate=0.002)
    try:
        history = engine.run(weights_df=weights, fecha_inicio="01-01-2018", fecha_fin="01-04-2026")
        print("Backtest ejecutado con éxito.")
    except ValueError as e:
        print(f"El Backtest falló:\n{e}")
        return

    # 3. Cálculo de Métricas
    calculator = MetricsCalculator(portfolio_history=history, benchmark_prices=benchmark)
    report = calculator.summary()
    
    print("\n=== REPORTE DE RENDIMIENTO Y RIESGO ===")
    print(report)
    
    # Guardar resultados para análisis posterior o gráficas
    history.to_csv("outputs/backtest_results.csv")
    print("\nHistorial guardado en 'outputs/backtest_results.csv'")

if __name__ == "__main__":
    run_pipeline()