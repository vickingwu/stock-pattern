import logging
from datetime import datetime
from typing import Optional

import pandas as pd

try:
    import yfinance as yf
except ModuleNotFoundError:
    exit("yfinance not found. Run `pip install yfinance` to install")

from .AbstractLoader import AbstractLoader

logger = logging.getLogger(__name__)


class YFinanceLoader(AbstractLoader):
    """
    Loads OHLC data online from Yahoo Finance for any ticker symbol.

    This lets the scanner run without any local CSV files, which is what
    makes the GitHub Actions "type tickers and email me the report" flow
    possible.

    Ticker notes:
    - US stocks: use the plain symbol, e.g. AAPL, MSFT, NVDA
    - Indian NSE stocks: append ".NS", e.g. RELIANCE.NS, INFY.NS
    - Indian BSE stocks: append ".BO"
    - Other exchanges use their own Yahoo suffixes (see Yahoo Finance).

    :param config: User config
    :param tf: daily, weekly or monthly
    :param end_date: End date up to which data must be returned
    :param period: Approx number of bars to return from end_date / latest
    """

    # Map the tool's timeframe strings to yfinance interval strings.
    timeframes = dict(daily="1d", weekly="1wk", monthly="1mo")

    # How much history to request from Yahoo for each timeframe. We request
    # generously and then trim to `period` bars so pattern detection always
    # has enough data to work with.
    _download_period = dict(daily="2y", weekly="10y", monthly="max")

    def __init__(
        self,
        config: dict,
        tf: Optional[str] = None,
        end_date: Optional[datetime] = None,
        period: int = 160,
    ):
        # Network based loader, but yfinance manages its own session, so
        # there is nothing for us to close explicitly.
        self.closed = True

        self.default_tf = str(config.get("DEFAULT_TF", "daily"))

        if self.default_tf not in self.timeframes:
            valid_values = ", ".join(self.timeframes.keys())
            raise ValueError(f"`DEFAULT_TF` in config must be one of {valid_values}")

        if tf is None:
            tf = self.default_tf

        if tf not in self.timeframes:
            valid_values = ", ".join(self.timeframes.keys())
            raise ValueError(f"Timeframe must be one of {valid_values}")

        self.tf = tf
        self.interval = self.timeframes[tf]
        self.end_date = end_date
        self.period = period

    def get(self, symbol: str) -> Optional[pd.DataFrame]:
        symbol = symbol.strip()

        if not symbol:
            return None

        try:
            df = yf.download(
                symbol,
                period=self._download_period[self.tf],
                interval=self.interval,
                auto_adjust=False,
                progress=False,
                threads=False,
            )
        except Exception as e:
            logger.warning(f"{symbol}: Error downloading data - {e!r}")
            return None

        if df is None or df.empty:
            logger.warning(f"{symbol}: No data returned from Yahoo Finance")
            return None

        # Newer yfinance versions return a column MultiIndex even for a single
        # ticker (e.g. ('Close', 'AAPL')). Flatten it to a plain column index.
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Keep only the columns the scanner expects.
        expected = ["Open", "High", "Low", "Close", "Volume"]
        missing = [c for c in expected if c not in df.columns]

        if missing:
            logger.warning(f"{symbol}: Missing columns {missing} in downloaded data")
            return None

        df = df[expected].copy()

        # Normalise the index to a clean, sorted, timezone-naive DatetimeIndex.
        df.index = pd.to_datetime(df.index)

        if getattr(df.index, "tz", None) is not None:
            df.index = df.index.tz_localize(None)

        if df.index.has_duplicates:
            df = df.loc[~df.index.duplicated()]

        if not df.index.is_monotonic_increasing:
            df = df.sort_index(ascending=True)

        df = df.dropna()

        if self.end_date:
            df = df.loc[: self.end_date]

        if df.empty:
            return None

        return df.iloc[-self.period :]

    def close(self):
        """Nothing to close for the yfinance loader."""
        pass
