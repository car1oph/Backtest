from pathlib import Path
import pandas as pd
import numpy as np

class DataLoader:
    
    def load_action_prices(self, folder_path: str | Path) -> pd.DataFrame:
        """
        Loads all .csv files in the folder and concatenates them by date.
        :param folder_path: Path to the folder containing CSV files with prices.
        :return: DataFrame with dates as the index and one column per asset with its closing price.
        """
        if isinstance(folder_path, str):
            base_path = Path(folder_path)
        else:
            base_path = folder_path

        all_tickers = []

        if not base_path.exists(): 
            raise FileNotFoundError(f"The specified path does not exist: '{base_path.absolute()}'")
        
        # Scan the folder for CSV files
        for csv_file in base_path.glob('*.csv'):
            df = pd.read_csv(csv_file)
            
            # Make sure the date column is in datetime format
            df['m_date'] = pd.to_datetime(df['m_date'])
            
            # Convert the date to the INDEX immediately
            df.set_index('m_date', inplace=True)
            df.index.name = 'Date' # Renombramos el índice
            
            # Extract the ticker name from the file name (without extension)
            ticker = csv_file.stem
            
            # Rename the 'm_close' column to the ticker name for clarity
            df.rename(columns={'m_close': ticker}, inplace=True)
            
            # Save the DataFrame for this ticker to the list
            all_tickers.append(df[[ticker]])
        
        # Join all tickers into a single DataFrame, aligning by date
        if all_tickers:
            result = pd.concat(all_tickers, axis=1)
            
            # Arrange the DataFrame by date to ensure chronological order
            result.sort_index(inplace=True)
            
            return result
        else:
            raise FileNotFoundError(f".CSV files not found in folder: {folder_path}")
            
    def load_portfolio(self, file_path: str | Path) -> pd.DataFrame:
        """
        Loads the 'portfolio_weights.csv' file containing the portfolio composition over time.
        Automatically detects if the structure is horizontal or vertical and standardizes it for the Backtest.
        """
        file_path = Path(file_path)
        if not file_path.exists(): 
            raise FileNotFoundError(f"The specified path does not exist: '{file_path.absolute()}'")
        
        # Load the CSV into a DataFrame
        df = pd.read_csv(file_path)
        
        # Standardize column names to lowercase for safe searching
        cols_lower = [str(c).lower() for c in df.columns]
        
        if 'date' in cols_lower or 'm_date' in cols_lower:
            # === CASE 1: THE FILE IS VERTICAL (CORRECT) ===
            # We find the exact column name ('Date', 'DATE', etc.)
            date_col_name = df.columns[cols_lower.index('date')] if 'date' in cols_lower else df.columns[cols_lower.index('m_date')]
            
            df[date_col_name] = pd.to_datetime(df[date_col_name])
            df.set_index(date_col_name, inplace=True)
            df.index.name = 'Date' # Forzamos el nombre limpio
            
        else:
            # === CASE 2: THE FILE IS HORIZONTAL (TO BE FIXED) ===
            # We assume the first column (e.g., 'Ticker', 'Symbol') contains the stock names
            # and the remaining columns are the dates.
            ticker_col = df.columns[0]
            
            # Temporarily set the ticker column as the index to facilitate transposition
            df.set_index(ticker_col, inplace=True)
            df = df.T
            
            # Now the index contains the dates, but they might be strings. We convert them to datetime.
            df.index = pd.to_datetime(df.index)
            df.index.name = 'Date'
            df.columns.name = None # Clear the column name to avoid confusion
            # The ticker names are preserved because we set them as the index before transposing

        # Convert all data to float to ensure numerical operations work correctly
        df = df.astype(float)
        
        # Arrange the DataFrame by date to ensure chronological order
        return df.sort_index()
    
    def load_benchmark(self, file_path: str | Path) -> pd.DataFrame:
        """
        Loads the benchmark prices from a CSV file. The CSV should have a 'Date' column and at least one price column.
        The first column after 'Date' will be used as the benchmark.
        """

        file_path = Path(file_path)
        if not file_path.exists(): # Error handling for missing benchmark file
            raise FileNotFoundError(f"The specified path does not exist: '{file_path.absolute()}'")
        
        result = pd.read_csv(file_path)
        if 'Date' in result.columns:
            result['Date'] = pd.to_datetime(result['Date'], dayfirst=True)
            result.set_index('Date', inplace=True)
        return result.sort_index() # Ensure the DataFrame is sorted by date
    

class Backtest:
    
    def __init__(self, prices_path: str | Path, initial_capital: float = 1000000.0, commission_rate: float = 0.005):
        """
        Initializes the backtesting engine.
        :param prices_path: Path to the folder containing the CSV files with the prices.
        :param initial_capital: Initial liquid capital for the portfolio, default is $1M. The currency is assumed to be the same as the prices.
        :param commission_rate: Commission rate per share (e.g., 0.05 = 5%, 0.001 = 0.1%).
        """
        data_loader = DataLoader()
        self.prices = data_loader.load_action_prices(folder_path=prices_path)
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.portfolio_history = None

    def _validate_inputs(self, weights_df: pd.DataFrame, start_date: pd.Timestamp, end_date: pd.Timestamp):
        """
        Validaciones iniciales de control de calidad sobre los archivos y configuraciones. Verifica que los activos en los pesos existan en los precios y que la suma de pesos + cash sea igual a 1.0 en todo el histórico de entrada.
        """
        # Check that all tickers in the weights DataFrame exist in the prices DataFrame
        tickers = [col for col in weights_df.columns if col.lower() != 'cash']
        for ticker in tickers:
            if ticker not in self.prices.columns:
                raise ValueError(f"Consistency error: The asset '{ticker}' is in the portfolio weights but does not have a valid price file.")

        # Check that the sum of weights + cash is equal to 1.0 for all dates in the weights DataFrame
        # We use np.isclose due to micro-noise in floating-point arithmetic
        weights_sum = weights_df.sum(axis=1)
        if not np.isclose(weights_sum, 1.0, atol=1e-4).all():
            fechas_erroneas = weights_sum[~np.isclose(weights_sum, 1.0, atol=1e-4)].index.strftime('%Y-%m-%d').tolist()
            if (fechas_erroneas >= start_date).any() or (fechas_erroneas <= end_date).any():
                raise ValueError(f"Allocation error: The sum of weights + cash is not equal to 1.0 on dates: {fechas_erroneas[:5]}.\n Only the first 5 dates with errors are shown.")

    def run(self, weights_df: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Runs the backtest by crossing weights and prices day by day, applying commissions and cash control.
        :param weights_df: DataFrame with the portfolio composition over time. Should have a 'Date' column with dates and the rest of the columns, one for each ticker with the assigned weights (e.g., 'AAPL', 'MSFT', etc.) and optionally a 'cash' or 'CASH' column with the percentage of cash.
        :param start_date: Start date of the backtest in 'DD-MM-YYYY' format.
        :param end_date: End date of the backtest in 'DD-MM-YYYY' format.
        """
        # Convert inputs to homogeneous Pandas Timestamps
        t_inicio = pd.to_datetime(start_date, dayfirst=True)
        t_fin = pd.to_datetime(end_date, dayfirst=True)
        
        # Run structural quality validations
        self._validate_inputs(weights_df, t_inicio, t_fin)
        
        # Filter data to the requested date range
        active_weights = weights_df.loc[t_inicio:t_fin].sort_index()
        # Apply forward-fill to prices to address missing days
        active_prices = self.prices.loc[t_inicio:t_fin].sort_index().ffill(limit = 10) # Only fill up to 10 business days.
        
        # Identify the tickers to be used in the backtest (excluding cash)
        tickers = [col for col in weights_df.columns if col.lower() != 'cash']
        
        # Initialize the portfolio history DataFrame to store daily portfolio value, cash balance, and daily commissions
        portfolio_history = pd.DataFrame(index=active_prices.index, columns=['portfolio_value', 'cash_balance', 'daily_commission'])
        
        # --- Setup initial conditions ---
        cash = self.initial_capital # Primero todo el CASH
        current_shares = pd.Series(0.0, index=tickers) # Al inicio no hay acciones, hay que comprarlas
        
        # --- Daily Temporal Loop ---
        for date, daily_prices in active_prices.iterrows():
            
            # 1. DAILY ASSET VALUATION: How much is the portfolio worth today with the current prices?
            active_shares_value = (current_shares.fillna(0) * daily_prices[tickers].fillna(0)).sum()
            total_portfolio_value = active_shares_value + cash
            
            if pd.isna(active_shares_value):
                archivos_faltantes = [ticker for ticker in tickers if pd.isna(daily_prices[ticker])]
                raise ValueError(f"Survival error on date [{date.strftime('%d-%m-%Y')}]: Asset value is NaN, probably because the asset was not trading/existing."
                                 f"Number of assets with missing data: {len(archivos_faltantes)}.\n Which correspond to: {archivos_faltantes}.")

            # 2. DAILY EXISTENCE CHECK (Critical point for asset survival)
            # If today is a rebalance date or if I already hold a position, the asset must have a price
            if date in active_weights.index:
                target_weights = active_weights.loc[date]
                for ticker in tickers:
                    # If the target weight is greater than 0, the asset must have a price today
                    if target_weights[ticker] > 0 and pd.isna(daily_prices[ticker]):
                        raise ValueError(
                            f"Survival error on date [{date.strftime('%Y-%m-%d')}]: "
                            f"An weight of {target_weights[ticker]*100}% was assigned to '{ticker}', but the asset was not trading/existing."
                        )
            
            # SAVE DAILY PORTFOLIO VALUE AND CASH BALANCE
            portfolio_history.loc[date, 'portfolio_value'] = total_portfolio_value
            portfolio_history.loc[date, 'cash_balance'] = cash
            
            # 3. REBALANCE DECISION: If today is a rebalance date, we calculate the trades needed to reach the target weights.
            if date in active_weights.index:
                target_weights = active_weights.loc[date]
                cash_pct = target_weights.get('cash', 0.0) or target_weights.get('CASH', 0.0)
                
                target_cash_reserve = total_portfolio_value * cash_pct
                capital_for_actions = total_portfolio_value - target_cash_reserve
                
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

                # 2. Separate the trades into buys and sells to handle cash flow and commissions
                sells = ideal_trade_values[ideal_trade_values < 0]
                buys = ideal_trade_values[ideal_trade_values > 0]
                
                # Sell first to free up cash, then buy with the remaining cash after commissions
                total_sell_revenue = abs(sells.sum())
                total_sell_commissions = total_sell_revenue * self.commission_rate
                
                max_budget_for_buys = (cash + total_sell_revenue - target_cash_reserve - total_sell_commissions) / (1.0 + self.commission_rate)
                max_budget_for_buys = max(0.0, max_budget_for_buys)
                
                ideal_total_buys = buys.sum()
                
                # Determine if we need to shrink the buy orders to fit within the available budget after selling and accounting for commissions
                shrink_factor = 1.0
                if ideal_total_buys > max_budget_for_buys and ideal_total_buys > 0:
                    shrink_factor = max_budget_for_buys / ideal_total_buys
                
                # 4. Calculate the final trade values after applying the shrink factor to buys and keeping sells as is
                final_trade_values = pd.Series(0.0, index=tickers)
                for ticker in sells.index:
                    final_trade_values[ticker] = sells[ticker]
                for ticker in buys.index:
                    final_trade_values[ticker] = buys[ticker] * shrink_factor
                
                # 5. Update the number of shares based on the final trade values and today's prices, and calculate the total traded volume for commission calculation
                new_shares = pd.Series(0.0, index=tickers)
                total_traded_volume = 0.0
                
                for ticker in tickers:
                    price = daily_prices[ticker]
                    trade_val = final_trade_values[ticker]
                    
                    if pd.notna(price) and price > 0:
                        new_shares[ticker] = current_shares[ticker] + (trade_val / price)
                        total_traded_volume += abs(trade_val)
                    else:
                        new_shares[ticker] = 0.0

                # 6. Final cash settlement with exact commissions
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
        Initializes the metrics calculator with the portfolio history and optional benchmark prices.
        :param portfolio_history: DataFrame with the daily portfolio value and cash balance.
        :param risk_free_rate: The risk-free rate for Sharpe ratio calculation.
        :param benchmark_prices: DataFrame with the benchmark asset prices.
        """
        self.portfolio_history = portfolio_history
        self.risk_free_rate = risk_free_rate
        self.benchmark_prices = benchmark_prices
        
        # Series base para cálculos rápidos
        self.portfolio_values = self.portfolio_history['portfolio_value'].astype(float)
        self.daily_returns = self.portfolio_values.pct_change().dropna()
        
    def calculate_total_return(self) -> float:
        """Calculate the total accumulated return from start to end."""
        initial_value = self.portfolio_values.iloc[0]
        final_value = self.portfolio_values.iloc[-1]
        return (final_value / initial_value) - 1.0

    def calculate_cagr(self) -> float:
        """Calculate the Compound Annual Growth Rate (CAGR)."""
        initial_value = self.portfolio_values.iloc[0]
        final_value = self.portfolio_values.iloc[-1]
        
        # Calculamos los años exactos transcurridos
        days = (self.portfolio_values.index[-1] - self.portfolio_values.index[0]).days
        if days == 0:
            return 0.0
        years = days / 365.25
        
        return (final_value / initial_value) ** (1 / years) - 1.0

    def calculate_volatility(self) -> float:
        """Calculate the annualized volatility (standard deviation of returns)."""
        return self.daily_returns.std(ddof=1) * np.sqrt(252)

    def calculate_sharpe_ratio(self) -> float:
        """Calculate the annualized Sharpe Ratio."""
        cagr = self.calculate_cagr()
        volatility = self.calculate_volatility()
        if volatility == 0:
            return 0.0
        return (cagr - self.risk_free_rate) / volatility

    def calculate_max_drawdown(self) -> float:
        """Calculate the maximum drawdown (Max Drawdown)."""
        cummax = self.portfolio_values.cummax()
        drawdown = (self.portfolio_values - cummax) / cummax
        return drawdown.min() # min porque son números negativos, el valor más bajo (más negativo) es la mayor caída

    def calculate_sortino_ratio(self) -> float:
        """Calculate the annualized Sortino Ratio, which considers only downside volatility."""
        cagr = self.calculate_cagr()
        
        # Filtramos solo los rendimientos negativos
        negative_returns = self.daily_returns[self.daily_returns < 0]
        downside_std = negative_returns.std(ddof=1) * np.sqrt(252)
        
        if downside_std == 0 or pd.isna(downside_std):
            return 0.0
        return (cagr - self.risk_free_rate) / downside_std

    def calculate_alpha(self) -> float:
        """Calculate the alpha, which is the excess annualized return relative to the benchmark."""
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
        """Calculate the Value at Risk (VaR) at the 5% confidence level."""
        # The 5th percentile of the empirical distribution of daily returns
        return np.percentile(self.daily_returns, 5)

    def calculate_cvar_5(self) -> float:
        """Calculate the Conditional Value at Risk (CVaR or Expected Shortfall) at the 5% confidence level."""
        var_5 = self.calculate_var_5()
        # Average of the returns that are worse than or equal to the VaR
        tail_returns = self.daily_returns[self.daily_returns <= var_5]
        return tail_returns.mean()

    def get_total_commissions(self) -> float:
        """Calculate the total commissions paid during the backtest."""
        if 'daily_commission' in self.portfolio_history.columns:
            return self.portfolio_history['daily_commission'].fillna(0).sum()
        return 0.0

    def summary(self) -> pd.Series:
        """Make a comprehensive report of all calculated metrics."""
        report = {
            "Total Return": self.calculate_total_return(),
            "CAGR": self.calculate_cagr(),
            "Anual Volatility": self.calculate_volatility(),
            "Anual Sharpe Ratio": self.calculate_sharpe_ratio(),
            "Anual Sortino Ratio": self.calculate_sortino_ratio(),
            "Max Drawdown": self.calculate_max_drawdown(),
            "VaR (5%)": self.calculate_var_5(),
            "CVaR (5%)": self.calculate_cvar_5(),
            "Total Commissions": self.get_total_commissions()
        }
        
        if self.benchmark_prices is not None:
            report["Alpha"] = self.calculate_alpha()
            
        return pd.Series(report)