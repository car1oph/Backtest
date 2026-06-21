from pathlib import Path
import pandas as pd
import numpy as np

class DataLoader:
    
    def load_action_prices(self, folder_path: str | Path) -> pd.DataFrame:
        """
        Lee todos los .csv en la carpeta y los une por fecha.
        :param folder_path: Ruta de la carpeta que contiene los archivos CSV con los precios.
        :return: DataFrame con las fechas en el índice y una columna por acción con su precio de cierre.
        """
        if isinstance(folder_path, str):
            base_path = Path(folder_path)
        else:
            base_path = folder_path

        all_tickers = []

        if not base_path.exists(): 
            raise FileNotFoundError(f"La ruta especificada no existe: '{base_path.absolute()}'")
        
        # Escanear la carpeta buscando .csv
        for csv_file in base_path.glob('*.csv'):
            df = pd.read_csv(csv_file)
            
            # 1. Asegurarnos de que sea datetime
            df['m_date'] = pd.to_datetime(df['m_date'])
            
            # 2. Convertir la fecha en el ÍNDICE inmediatamente
            df.set_index('m_date', inplace=True)
            df.index.name = 'Date' # Renombramos el índice
            
            # 3. Extraer el ticker
            ticker = csv_file.stem
            
            # 4. Renombrar la columna de cierre AL NOMBRE EXACTO DEL TICKER (Sin sufijos)
            df.rename(columns={'m_close': ticker}, inplace=True)
            
            # 5. Guardar SOLO la columna de los precios en la lista (la fecha ya está segura en el índice)
            all_tickers.append(df[[ticker]])
        
        # Unir todos los dataframes
        if all_tickers:
            # Como todos ya tienen 'Date' como índice, concat los alinea perfectamente por fecha
            result = pd.concat(all_tickers, axis=1)
            
            # Ordenamos cronológicamente para evitar problemas de viaje en el tiempo
            result.sort_index(inplace=True)
            
            return result
        else:
            raise FileNotFoundError(f"No se encontraron archivos .csv en la carpeta: {folder_path}")
            
    def load_portfolio(self, file_path: str | Path) -> pd.DataFrame:
        """
        Lee el archivo 'portfolio_weights.csv' que contiene la composición del portafolio a través del tiempo.
        Detecta automáticamente si la estructura es horizontal o vertical y la estandariza para el Backtest.
        """
        file_path = Path(file_path)
        if not file_path.exists(): 
            raise FileNotFoundError(f"La ruta especificada no existe: '{file_path.absolute()}'")
        
        # Leer el CSV crudo
        df = pd.read_csv(file_path)
        
        # Estandarizar temporalmente los nombres de las columnas a minúsculas para una búsqueda segura
        cols_lower = [str(c).lower() for c in df.columns]
        
        if 'date' in cols_lower or 'm_date' in cols_lower:
            # === CASO 1: EL ARCHIVO VIENE VERTICAL (CORRECTO) ===
            # Encontramos exactamente cómo está escrita la columna ('Date', 'DATE', etc.)
            date_col_name = df.columns[cols_lower.index('date')] if 'date' in cols_lower else df.columns[cols_lower.index('m_date')]
            
            df[date_col_name] = pd.to_datetime(df[date_col_name])
            df.set_index(date_col_name, inplace=True)
            df.index.name = 'Date' # Forzamos el nombre limpio
            
        else:
            # === CASO 2: EL ARCHIVO VIENE HORIZONTAL (A CORREGIR) ===
            # Asumimos que la 1ra columna (ej. 'Ticker', 'Symbol') contiene los nombres de las acciones
            # y el resto de las columnas son las fechas.
            ticker_col = df.columns[0]
            
            # Ponemos los tickers como índice temporal
            df.set_index(ticker_col, inplace=True)
            
            # ¡La magia! Transponemos: Las fechas se vuelven filas y los tickers se vuelven columnas
            df = df.T
            
            # Ahora el índice son strings de fechas. Los convertimos al formato datetime
            df.index = pd.to_datetime(df.index)
            df.index.name = 'Date'
            df.columns.name = None # Limpiamos el metadato del nombre de las columnas
            # Se mantiene el nombre de los Tickers porque lo hicimos índice antes de Transponer

        # Limpieza final: Asegurar que todo el contenido matemático sea tipo float
        df = df.astype(float)
        
        # Ordenamos cronológicamente para evitar problemas de viaje en el tiempo en el backtest
        return df.sort_index()
    
    def load_benchmark(self, file_path: str | Path) -> pd.DataFrame:
        """
        Lee el archivo 'benchmarks.csv' que contiene los precios de los benchmarks a través del tiempo y devuelve un DataFrame.
        """

        file_path = Path(file_path)
        if not file_path.exists(): # Prevención de errores: Verificar que la ruta existe
            raise FileNotFoundError(f"La ruta especificada no existe: '{file_path.absolute()}'")
        
        result = pd.read_csv(file_path)
        if 'Date' in result.columns:
            result['Date'] = pd.to_datetime(result['Date'], dayfirst=True)
            result.set_index('Date', inplace=True)
        return result.sort_index() # Asegurarse de que el DataFrame esté ordenado por fecha
    

class Backtest:
    
    def __init__(self, prices_path: str | Path, initial_capital: float = 1000000.0, commission_rate: float = 0.005):
        """
        Inicializa el motor de backtesting.
        :param prices_path: Ruta de la carpeta que contiene los archivos CSV con los precios.
        :param initial_capital: Capital líquido con el que inicia el portafolio, por defecto $1M. La divisa se considera que es la misma que la de los precios.
        :param commission_rate: Porcentaje de comisión por acción (ej. 0.05 = 5%, 0.001 = 0.1%).
        """
        data_loader = DataLoader()
        self.prices = data_loader.load_action_prices(folder_path=prices_path)
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.portfolio_history = None

    def _validate_inputs(self, weights_df: pd.DataFrame, fecha_inicio: pd.Timestamp, fecha_fin: pd.Timestamp):
        """
        Validaciones iniciales de control de calidad sobre los archivos y configuraciones. Verifica que los activos en los pesos existan en los precios y que la suma de pesos + cash sea igual a 1.0 en todo el histórico de entrada.
        """
        # 1. Comprobar que cada columna (excepto 'cash') exista en el DataFrame de precios
        tickers = [col for col in weights_df.columns if col.lower() != 'cash']
        for ticker in tickers:
            if ticker not in self.prices.columns:
                raise ValueError(f"Error de consistencia: El activo '{ticker}' está en los pesos del portafolio pero no tiene un archivo de precios válido.")

        # 2. Comprobar que sum(pesos + cash) == 1 en todo el histórico de entrada
        # Usamos np.isclose por el micro-ruido de flotantes en computación
        weights_sum = weights_df.sum(axis=1)
        if not np.isclose(weights_sum, 1.0, atol=1e-4).all():
            fechas_erroneas = weights_sum[~np.isclose(weights_sum, 1.0, atol=1e-4)].index.strftime('%Y-%m-%d').tolist()
            if (fechas_erroneas >= fecha_inicio).any() or (fechas_erroneas <= fecha_fin).any():
                raise ValueError(f"Error de asignación: La suma de pesos + cash no es igual a 1.0 en las fechas: {fechas_erroneas[:5]}.\n Solo se muestran las primeras 5 fechas con error.")

    def run(self, weights_df: pd.DataFrame, fecha_inicio: str, fecha_fin: str) -> pd.DataFrame:
        """
        Ejecuta el backtest cruzando pesos y precios día a día, aplicando comisiones y control de cash.
        :param weights_df: DataFrame con la composición del portafolio a través del tiempo. Debe tener una columna 'Date' con fechas y el resto de columnas, una por cada ticker con los pesos asignados (ej. 'AAPL', 'MSFT', etc.) y opcionalmente una columna 'cash' o 'CASH' con el porcentaje de efectivo.
        :param fecha_inicio: Fecha de inicio del backtest en formato 'DD-MM-YYYY'.
        :param fecha_fin: Fecha de fin del backtest en formato 'DD-MM-YYYY'.
        """
        # Convertir entradas a Timestamps homogéneos de Pandas
        t_inicio = pd.to_datetime(fecha_inicio, dayfirst=True)
        t_fin = pd.to_datetime(fecha_fin, dayfirst=True)
        
        # Ejecutar validaciones estructurales de calidad
        self._validate_inputs(weights_df, t_inicio, t_fin)
        
        # Filtrar datos al rango de fechas solicitado por el usuario
        active_weights = weights_df.loc[t_inicio:t_fin].sort_index()
        # Aplicamos forward-fill a los precios para solucionar el arrastre por días no cotizados
        active_prices = self.prices.loc[t_inicio:t_fin].sort_index().ffill(limit = 10) # Solo rellenamos hasta 10 días hábiles.
        
        # Identificar tickers operativos de la estrategia
        tickers = [col for col in weights_df.columns if col.lower() != 'cash']
        
        # Inicializar el DataFrame de salida
        portfolio_history = pd.DataFrame(index=active_prices.index, columns=['portfolio_value', 'cash_balance', 'daily_commission'])
        
        # --- VARIABLES DE ESTADO LOCALES ---
        cash = self.initial_capital # Primero todo el CASH
        current_shares = pd.Series(0.0, index=tickers) # Al inicio no hay acciones, hay que comprarlas
        
        # Ciclo temporal diario
        for date, daily_prices in active_prices.iterrows():
            
            # 1. VALUACIÓN DIARIA: ¿Cuánto vale el portafolio hoy con los precios actuales?
            active_shares_value = (current_shares.fillna(0) * daily_prices[tickers].fillna(0)).sum()
            total_portfolio_value = active_shares_value + cash
            
            if pd.isna(active_shares_value):
                archivos_faltantes = [ticker for ticker in tickers if pd.isna(daily_prices[ticker])]
                raise ValueError(f"Error de supervivencia en fecha [{date.strftime('%d-%m-%Y')}]: El valor de las acciones es NaN, probablemente porque el activo no cotizaba/existía."
                                 f"Número de activos con datos faltantes: {len(archivos_faltantes)}.\n Que corresponden a: {archivos_faltantes}.")

            # 2. COMPROBACIÓN DIARIA DE EXISTENCIA (Punto crítico de supervivencia de activos)
            # Si hoy toca rebalancear o si ya mantengo posición, el activo debe tener precio
            if date in active_weights.index:
                target_weights = active_weights.loc[date]
                for ticker in tickers:
                    # Si el peso es mayor a 0 pero el precio sigue siendo NaN (no existía la empresa)
                    if target_weights[ticker] > 0 and pd.isna(daily_prices[ticker]):
                        raise ValueError(
                            f"Error de supervivencia en fecha [{date.strftime('%Y-%m-%d')}]: "
                            f"Se asignó un {target_weights[ticker]*100}% a '{ticker}', pero el activo no cotizaba/existía."
                        )
            
            # Guardamos el valor de este día
            portfolio_history.loc[date, 'portfolio_value'] = total_portfolio_value
            portfolio_history.loc[date, 'cash_balance'] = cash
            
            # 3. EJECUCIÓN DEL REBALANCEO
            if date in active_weights.index:
                target_weights = active_weights.loc[date]
                cash_pct = target_weights.get('cash', 0.0) or target_weights.get('CASH', 0.0)
                
                target_cash_reserve = total_portfolio_value * cash_pct
                capital_for_actions = total_portfolio_value - target_cash_reserve
                
                # 1. Calcular el valor actual de cada posición y el cambio ideal requerido
                current_values = current_shares * daily_prices[tickers].fillna(0)
                sum_weights = sum([target_weights[t] for t in tickers if t.lower() != 'cash'])
                
                ideal_trade_values = pd.Series(0.0, index=tickers)
                for ticker in tickers:
                    w = target_weights[ticker]
                    price = daily_prices[ticker]
                    
                    if pd.notna(price) and price > 0 and sum_weights > 0:
                        ideal_target_value = capital_for_actions * (w / sum_weights)
                        ideal_trade_values[ticker] = ideal_target_value - current_values[ticker]
                    else:
                        # Si el activo no cotiza o el peso es 0, liquidamos lo que quede
                        ideal_trade_values[ticker] = -current_values[ticker]

                # 2. Separar flujos: VENTAS (negativos) y COMPRAS (positivos)
                sells = ideal_trade_values[ideal_trade_values < 0]
                buys = ideal_trade_values[ideal_trade_values > 0]
                
                # Las ventas se ejecutan por completo para liberar el efectivo
                total_sell_revenue = abs(sells.sum())
                total_sell_commissions = total_sell_revenue * self.commission_rate
                
                # 3. Aplicar la fórmula del presupuesto máximo real para las compras
                max_budget_for_buys = (cash + total_sell_revenue - target_cash_reserve - total_sell_commissions) / (1.0 + self.commission_rate)
                max_budget_for_buys = max(0.0, max_budget_for_buys)
                
                ideal_total_buys = buys.sum()
                
                # Determinamos si las compras exceden el presupuesto neto disponible
                shrink_factor = 1.0
                if ideal_total_buys > max_budget_for_buys and ideal_total_buys > 0:
                    shrink_factor = max_budget_for_buys / ideal_total_buys
                
                # 4. Consolidar transacciones finales (ventas intactas, compras ajustadas)
                final_trade_values = pd.Series(0.0, index=tickers)
                for ticker in sells.index:
                    final_trade_values[ticker] = sells[ticker]
                for ticker in buys.index:
                    final_trade_values[ticker] = buys[ticker] * shrink_factor
                
                # 5. Actualizar inventario de acciones y volumen operado
                new_shares = pd.Series(0.0, index=tickers)
                total_traded_volume = 0.0
                
                for ticker in tickers:
                    price = daily_prices[ticker]
                    trade_val = final_trade_values[ticker]
                    
                    if pd.notna(price) and price > 0:
                        # Sumamos algebraicamente (el valor de venta es negativo, reduce acciones)
                        new_shares[ticker] = current_shares[ticker] + (trade_val / price)
                        total_traded_volume += abs(trade_val)
                    else:
                        new_shares[ticker] = 0.0

                # 6. Liquidación final de caja con comisiones exactas
                commissions_cost = total_traded_volume * self.commission_rate
                portfolio_history.loc[date, 'daily_commission'] = commissions_cost
                
                money_invested_in_shares = (new_shares * daily_prices[tickers].fillna(0)).sum()
                cash = total_portfolio_value - money_invested_in_shares - commissions_cost
                
                if cash < 1e-6:
                    cash = 0.0
                    
                current_shares = new_shares    

        self.portfolio_history = portfolio_history
        return self.portfolio_history    


class MetricsCalculator:
    
    def __init__(self, portfolio_history: pd.DataFrame, risk_free_rate: float = 0.04, benchmark_prices: pd.DataFrame = None):
        """
        Inicializa la calculadora de métricas con el historial del portafolio.
        """
        self.portfolio_history = portfolio_history
        self.risk_free_rate = risk_free_rate
        self.benchmark_prices = benchmark_prices
        
        # Series base para cálculos rápidos
        self.portfolio_values = self.portfolio_history['portfolio_value'].astype(float)
        self.daily_returns = self.portfolio_values.pct_change().dropna()
        
    def calculate_total_return(self) -> float:
        """Rendimiento total acumulado de inicio a fin."""
        initial_value = self.portfolio_values.iloc[0]
        final_value = self.portfolio_values.iloc[-1]
        return (final_value / initial_value) - 1.0

    def calculate_cagr(self) -> float:
        """Tasa Anual de Crecimiento Compuesto (CAGR)."""
        initial_value = self.portfolio_values.iloc[0]
        final_value = self.portfolio_values.iloc[-1]
        
        # Calculamos los años exactos transcurridos
        days = (self.portfolio_values.index[-1] - self.portfolio_values.index[0]).days
        if days == 0:
            return 0.0
        years = days / 365.25
        
        return (final_value / initial_value) ** (1 / years) - 1.0

    def calculate_volatility(self) -> float:
        """Volatilidad anualizada (Desviación estándar de los rendimientos)."""
        return self.daily_returns.std(ddof=1) * np.sqrt(252)

    def calculate_sharpe_ratio(self) -> float:
        """Sharpe Ratio anualizado."""
        cagr = self.calculate_cagr()
        volatility = self.calculate_volatility()
        if volatility == 0:
            return 0.0
        return (cagr - self.risk_free_rate) / volatility

    def calculate_max_drawdown(self) -> float:
        """Máxima caída porcentual desde el pico más alto (Max Drawdown)."""
        cummax = self.portfolio_values.cummax()
        drawdown = (self.portfolio_values - cummax) / cummax
        return drawdown.min() # min porque son números negativos, el valor más bajo (más negativo) es la mayor caída

    def calculate_sortino_ratio(self) -> float:
        """Sortino Ratio (Penaliza solo la volatilidad a la baja)."""
        cagr = self.calculate_cagr()
        
        # Filtramos solo los rendimientos negativos
        negative_returns = self.daily_returns[self.daily_returns < 0]
        downside_std = negative_returns.std(ddof=1) * np.sqrt(252)
        
        if downside_std == 0 or pd.isna(downside_std):
            return 0.0
        return (cagr - self.risk_free_rate) / downside_std

    def calculate_alpha(self) -> float:
        """Exceso de retorno anualizado respecto al benchmark."""
        if self.benchmark_prices is None or self.benchmark_prices.empty:
            return np.nan
            
        # Tomamos la primera columna del benchmark (ej. el SPY o IPC)
        b_col = self.benchmark_prices.columns[0]
        
        # Alinear fechas del benchmark con el portafolio
        aligned_data = pd.concat([self.portfolio_values, self.benchmark_prices[b_col]], axis=1, join='inner')
        if aligned_data.empty:
            return np.nan
            
        initial_b = aligned_data.iloc[0, 1]
        final_b = aligned_data.iloc[-1, 1]
        days = (aligned_data.index[-1] - aligned_data.index[0]).days
        years = days / 365.25
        
        benchmark_cagr = (final_b / initial_b) ** (1 / years) - 1.0
        return self.calculate_cagr() - benchmark_cagr

    def calculate_var_5(self) -> float:
        """Value at Risk (VaR) histórico al 5%."""
        # El percentil 5 de la distribución empírica de rendimientos diarios
        return np.percentile(self.daily_returns, 5)

    def calculate_cvar_5(self) -> float:
        """Conditional Value at Risk (CVaR o Expected Shortfall) al 5%."""
        var_5 = self.calculate_var_5()
        # Promedio de los rendimientos que son peores o iguales al VaR
        tail_returns = self.daily_returns[self.daily_returns <= var_5]
        return tail_returns.mean()

    def get_total_commissions(self) -> float:
        """Suma de todas las comisiones pagadas durante el backtest."""
        if 'daily_commission' in self.portfolio_history.columns:
            return self.portfolio_history['daily_commission'].fillna(0).sum()
        return 0.0

    def summary(self) -> pd.Series:
        """Devuelve un reporte completo de todas las métricas calculadas."""
        report = {
            "Total Return": self.calculate_total_return(),
            "CAGR": self.calculate_cagr(),
            "Volatilidad Anual": self.calculate_volatility(),
            "Sharpe Ratio Anual": self.calculate_sharpe_ratio(),
            "Sortino Ratio Anual": self.calculate_sortino_ratio(),
            "Max Drawdown": self.calculate_max_drawdown(),
            "VaR (5%)": self.calculate_var_5(),
            "CVaR (5%)": self.calculate_cvar_5(),
            "Total Commisions": self.get_total_commissions()
        }
        
        if self.benchmark_prices is not None:
            report["Alpha"] = self.calculate_alpha()
            
        return pd.Series(report)