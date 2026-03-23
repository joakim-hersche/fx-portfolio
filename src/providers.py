"""Data provider abstraction layer.

Current implementation: YFinanceProvider (yfinance).
Planned migration: EOD Historical Data (paid API) — swap YFinanceProvider for
EodProvider and update the factory; no other code changes required.
"""

import logging
import statistics
from datetime import datetime, timezone
from typing import Protocol, cast, runtime_checkable

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


@runtime_checkable
class DataProvider(Protocol):
    def get_current_prices(self, tickers: list[str]) -> dict[str, float]: ...
    def get_price_history_short(self, ticker: str) -> pd.DataFrame: ...
    def get_price_history_long(self, ticker: str) -> pd.DataFrame: ...
    def get_price_history_range(self, ticker: str, period: str) -> pd.DataFrame: ...
    def get_simulation_history(self, ticker: str) -> pd.DataFrame: ...
    def get_analytics_history(self, ticker: str) -> pd.DataFrame: ...
    def get_fundamentals(self, ticker: str) -> dict: ...
    def get_news(self, ticker: str) -> list[dict]: ...
    def get_sector_peers(self, sector: str, candidates: list[str], target: str, max_peers: int) -> list[dict]: ...
    def get_sector_medians(self, sector: str, candidates: list[str], max_samples: int) -> dict: ...
    def get_company_name(self, ticker: str) -> str: ...


class YFinanceProvider:
    """DataProvider implementation backed by yfinance."""

    # ── prices ────────────────────────────────────────────────────────────────

    def get_current_prices(self, tickers: list[str]) -> dict[str, float]:
        try:
            df = yf.download(
                tickers,
                period="5d",
                group_by="ticker",
                progress=False,
                threads=True,
            )
            result: dict[str, float] = {}
            if df is None:
                return result
            if len(tickers) == 1:
                ticker = tickers[0]
                close_col = cast(pd.Series, df["Close"])
                if "Close" in df.columns and not close_col.dropna().empty:
                    result[ticker] = float(close_col.dropna().iloc[-1])
            else:
                for ticker in tickers:
                    try:
                        close = cast(pd.Series, df[ticker]["Close"]).dropna()
                        if not close.empty:
                            result[ticker] = float(close.iloc[-1])
                    except (KeyError, TypeError):
                        continue
            return result
        except Exception as e:
            logger.error("get_current_prices failed: %s", e)
            return {}

    # ── history helpers ───────────────────────────────────────────────────────

    def _safe_history(self, ticker: str, period: str) -> pd.DataFrame:
        try:
            hist = yf.Ticker(ticker).history(period=period)
            hist.index = cast(pd.DatetimeIndex, hist.index).tz_localize(None)
            return hist
        except Exception:
            return pd.DataFrame()

    def get_price_history_short(self, ticker: str) -> pd.DataFrame:
        return self._safe_history(ticker, "6mo")

    def get_price_history_long(self, ticker: str) -> pd.DataFrame:
        return self._safe_history(ticker, "max")

    def get_price_history_range(self, ticker: str, period: str) -> pd.DataFrame:
        return self._safe_history(ticker, period)

    def get_simulation_history(self, ticker: str) -> pd.DataFrame:
        try:
            hist = yf.Ticker(ticker).history(period="5y")
            if hist.empty:
                logger.warning("get_simulation_history(%s): empty DataFrame", ticker)
                return pd.DataFrame()
            hist.index = cast(pd.DatetimeIndex, hist.index).tz_localize(None)
            logger.info("get_simulation_history(%s): %d rows", ticker, len(hist))
            return hist
        except Exception as e:
            logger.error("get_simulation_history(%s) failed: %s", ticker, e)
            return pd.DataFrame()

    def get_analytics_history(self, ticker: str) -> pd.DataFrame:
        return self._safe_history(ticker, "1y")

    # ── fundamentals ──────────────────────────────────────────────────────────

    def get_fundamentals(self, ticker: str) -> dict:
        try:
            info = yf.Ticker(ticker).info
            current      = info.get("currentPrice") or info.get("regularMarketPrice")
            low_1y       = info.get("fiftyTwoWeekLow")
            high_1y      = info.get("fiftyTwoWeekHigh")
            pe           = info.get("trailingPE")
            div_rate     = info.get("dividendRate")
            sector       = info.get("sector", None)
            target_price = info.get("targetMeanPrice", None)

            trading_ccy   = info.get("currency")
            financial_ccy = info.get("financialCurrency")
            if financial_ccy == "GBp":
                financial_ccy = "GBX"

            div_pct = None
            div = info.get("dividendYield")
            if div is not None:
                candidate = div * 100
                div_pct = candidate if candidate <= 20.0 else div

            position = None
            if current and low_1y and high_1y and high_1y > low_1y:
                position = round((current - low_1y) / (high_1y - low_1y) * 100, 1)

            return {
                "P/E Ratio":          round(pe, 1)            if pe           else None,
                "Div Yield (%)":      round(div_pct, 2)       if div_pct      else None,
                "1-Year Low":         round(low_1y, 2)        if low_1y       else None,
                "1-Year High":        round(high_1y, 2)       if high_1y      else None,
                "1-Year Position":    position,
                "Current Price":      round(current, 2)       if current      else None,
                "Sector":             sector if sector else "Unknown",
                "Target Price":       round(target_price, 2)  if target_price else None,
                "Dividend Rate":      round(div_rate, 4)      if div_rate     else None,
                "Financial Currency": financial_ccy,
            }
        except Exception:
            return {}

    # ── news ──────────────────────────────────────────────────────────────────

    def get_news(self, ticker: str) -> list[dict]:
        try:
            news = yf.Ticker(ticker).news
            if not news:
                return []
            results = []
            for item in news:
                content = item.get("content", item)
                provider = content.get("provider", {})
                canonical = content.get("canonicalUrl", {})
                pub_time = 0
                pub_date = content.get("pubDate", "")
                if pub_date:
                    try:
                        pub_time = int(
                            datetime.fromisoformat(
                                pub_date.replace("Z", "+00:00")
                            ).timestamp()
                        )
                    except (ValueError, TypeError):
                        pub_time = item.get("providerPublishTime", 0)
                else:
                    pub_time = item.get("providerPublishTime", 0)
                results.append({
                    "title":               content.get("title", item.get("title", "")),
                    "publisher":           provider.get("displayName", item.get("publisher", "")),
                    "link":                canonical.get("url", item.get("link", "")),
                    "providerPublishTime": pub_time,
                })
            return results
        except Exception:
            return []

    # ── sector peers / medians ────────────────────────────────────────────────

    def get_sector_peers(self, sector, candidates, target, max_peers=4) -> list[dict]:
        peers = []
        for ticker in candidates:
            if len(peers) >= max_peers:
                break
            if ticker == target:
                continue
            try:
                info = yf.Ticker(ticker).info
                if info.get("sector", "") != sector:
                    continue
                hist = yf.Ticker(ticker).history("1y")
                return_1y = None
                if not hist.empty and "Close" in hist.columns:
                    close = hist["Close"].dropna()
                    if len(close) >= 2:
                        return_1y = round((close.iloc[-1] / close.iloc[0] - 1) * 100, 1)
                peers.append({
                    "ticker":    ticker,
                    "name":      info.get("shortName", ticker),
                    "pe":        info.get("trailingPE"),
                    "div_yield": round(info.get("dividendYield", 0) * 100, 2) if info.get("dividendYield") else None,
                    "beta":      info.get("beta"),
                    "return_1y": return_1y,
                })
            except Exception:
                continue
        return peers

    def get_sector_medians(self, sector, candidates, max_samples=10) -> dict:
        pe_values, dy_values = [], []
        sampled = 0
        for ticker in candidates:
            if sampled >= max_samples:
                break
            try:
                info = yf.Ticker(ticker).info
                if info.get("sector") != sector:
                    continue
                sampled += 1
                pe = info.get("trailingPE")
                if pe and pe > 0:
                    pe_values.append(pe)
                dy = info.get("dividendYield")
                if dy and dy > 0:
                    dy_values.append(dy * 100)
            except Exception:
                continue
        return {
            "median_pe":        round(statistics.median(pe_values), 1) if pe_values else None,
            "median_div_yield": round(statistics.median(dy_values), 2) if dy_values else None,
        }

    # ── company name ──────────────────────────────────────────────────────────

    def get_company_name(self, ticker: str) -> str:
        try:
            info = yf.Ticker(ticker).info
            return info.get("shortName") or info.get("longName") or ticker
        except Exception:
            return ticker
