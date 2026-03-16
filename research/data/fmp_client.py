"""FMP data client — all calls routed through market-data-service.

The market-data-service handles rate limiting, caching, and exponential backoff.
We just call its HTTP endpoints.
"""

from __future__ import annotations

from typing import Any

import httpx

MDS_BASE = "https://market-data-service-production-cd1d.up.railway.app"
MDS_HEADERS = {"X-Service-Name": "valuation-agent"}


class FMPClient:
    """Client that routes all FMP data through market-data-service."""

    def __init__(self, mds_base: str | None = None):
        self._mds_base = (mds_base or MDS_BASE).rstrip("/")
        self._client: httpx.AsyncClient | None = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _get(self, path: str, params: dict | None = None) -> Any:
        """Call market-data-service endpoint, return data payload."""
        client = await self._ensure_client()
        url = f"{self._mds_base}{path}"
        resp = await client.get(url, params=params, headers=MDS_HEADERS)
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    # --- Company ---

    async def get_profile(self, symbol: str) -> dict | None:
        """Company profile: mktCap, beta, sector, industry, ISIN."""
        try:
            data = await self._get(f"/api/v1/companies/{symbol}/profile")
            if isinstance(data, dict) and data.get("symbol"):
                return data
            if isinstance(data, list) and data:
                return data[0]
        except Exception:
            pass
        return None

    async def get_profiles_batch(self, symbols: list[str], batch_size: int = 50) -> dict[str, dict]:
        """Batch profiles for multiple symbols."""
        results: dict[str, dict] = {}
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i : i + batch_size]
            try:
                data = await self._get(f"/api/v1/companies/{','.join(batch)}/profiles")
                if isinstance(data, list):
                    for item in data:
                        sym = item.get("symbol", "")
                        if sym:
                            results[sym] = item
            except Exception:
                pass
        return results

    # --- Historical Prices ---

    async def get_historical_prices(
        self,
        symbol: str,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[dict]:
        """Historical daily OHLCV."""
        params: dict[str, str] = {}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        try:
            data = await self._get(f"/api/v1/quotes/{symbol}/historical", params)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("historical", [])
        except Exception:
            pass
        return []

    # --- Fundamentals (via new endpoints) ---

    async def get_key_metrics(self, symbol: str, period: str = "annual") -> list[dict]:
        """Key financial metrics: ROE, ROIC, D/E, EV/EBITDA, P/E, etc."""
        try:
            data = await self._get(
                f"/api/v1/fundamentals/{symbol}/key-metrics",
                {"period": period},
            )
            return data if isinstance(data, list) else []
        except Exception:
            return []

    async def get_ratios(self, symbol: str, period: str = "annual") -> list[dict]:
        """Financial ratios: margins, leverage, efficiency."""
        try:
            data = await self._get(
                f"/api/v1/fundamentals/{symbol}/ratios",
                {"period": period},
            )
            return data if isinstance(data, list) else []
        except Exception:
            return []

    async def get_financial_growth(self, symbol: str, period: str = "annual") -> list[dict]:
        """Financial growth rates: revenue, EPS, FCF growth."""
        try:
            data = await self._get(
                f"/api/v1/fundamentals/{symbol}/financial-growth",
                {"period": period},
            )
            return data if isinstance(data, list) else []
        except Exception:
            return []

    async def get_analyst_estimates(self, symbol: str, period: str = "annual") -> list[dict]:
        """Analyst consensus estimates: revenue, EPS, EBITDA."""
        try:
            data = await self._get(
                f"/api/v1/fundamentals/{symbol}/analyst-estimates",
                {"period": period},
            )
            return data if isinstance(data, list) else []
        except Exception:
            return []

    async def get_rating(self, symbol: str) -> dict | None:
        """Company rating and score."""
        try:
            data = await self._get(f"/api/v1/fundamentals/{symbol}/rating")
            if isinstance(data, list) and data:
                return data[0]
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    async def get_earnings_surprises(self, symbol: str) -> list[dict]:
        """Earnings surprise history: actual vs estimated EPS."""
        try:
            data = await self._get(f"/api/v1/fundamentals/{symbol}/earnings-surprises")
            return data if isinstance(data, list) else []
        except Exception:
            return []

    # --- ISIN Search ---

    async def search_by_isin(self, isin: str) -> str | None:
        """Resolve ISIN to FMP ticker symbol.

        Returns the US-listed symbol or None.
        """
        try:
            data = await self._get(f"/api/v1/fundamentals/isin/{isin}")
            if isinstance(data, list):
                for item in data:
                    if item.get("exchangeShortName") in ("NYSE", "NASDAQ", "AMEX") and item.get(
                        "isActivelyTrading", True
                    ):
                        return item.get("symbol")
                for item in data:
                    if item.get("currency") == "USD":
                        return item.get("symbol")
                if data:
                    return data[0].get("symbol")
        except Exception:
            pass
        return None
