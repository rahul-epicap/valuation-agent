"""Barra-inspired factor catalog for valuation research.

Each FactorDefinition describes a factor that can be used in regression models.
Factors are sourced from existing dashboard data or FMP API endpoints.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FactorCategory(str, Enum):
    GROWTH = "growth"
    SIZE = "size"
    VOLATILITY = "volatility"
    MOMENTUM = "momentum"
    LEVERAGE = "leverage"
    QUALITY = "quality"
    INDUSTRY = "industry"


class FactorSource(str, Enum):
    DASHBOARD = "dashboard"  # Derived from existing snapshot data
    FMP = "fmp"  # Fetched from FMP API


class FactorTransform(str, Enum):
    RAW = "raw"
    LOG = "log"
    ZSCORE = "zscore"
    PCT_CHANGE = "pct_change"
    BINARY = "binary"


@dataclass(frozen=True)
class FactorDefinition:
    """Definition of a single factor for regression models."""

    name: str
    category: FactorCategory
    source: FactorSource
    transform: FactorTransform
    description: str
    fmp_endpoint: str = ""  # Only for FMP-sourced factors
    fmp_field: str = ""  # JSON field within FMP response
    is_continuous: bool = True  # False for dummy/binary factors
    requires_history: bool = False  # True if needs time-series data


# --- Built-in factors from dashboard data ---

DASHBOARD_FACTORS: dict[str, FactorDefinition] = {
    "revenue_growth": FactorDefinition(
        name="revenue_growth",
        category=FactorCategory.GROWTH,
        source=FactorSource.DASHBOARD,
        transform=FactorTransform.RAW,
        description="Forward revenue growth rate (rg)",
    ),
    "eps_growth": FactorDefinition(
        name="eps_growth",
        category=FactorCategory.GROWTH,
        source=FactorSource.DASHBOARD,
        transform=FactorTransform.RAW,
        description="Forward EPS growth rate (xg)",
    ),
    "gross_margin": FactorDefinition(
        name="gross_margin",
        category=FactorCategory.QUALITY,
        source=FactorSource.DASHBOARD,
        transform=FactorTransform.ZSCORE,
        description="Gross margin proxy: EV/Rev divided by EV/GP (er/eg)",
    ),
}


# --- FMP-sourced factors (Phase 2) ---

FMP_FACTORS: dict[str, FactorDefinition] = {
    "log_market_cap": FactorDefinition(
        name="log_market_cap",
        category=FactorCategory.SIZE,
        source=FactorSource.FMP,
        transform=FactorTransform.LOG,
        description="Log of market capitalization",
        fmp_endpoint="/api/v3/profile/{sym}",
        fmp_field="mktCap",
    ),
    "beta": FactorDefinition(
        name="beta",
        category=FactorCategory.VOLATILITY,
        source=FactorSource.FMP,
        transform=FactorTransform.ZSCORE,
        description="Stock beta vs market",
        fmp_endpoint="/api/v3/profile/{sym}",
        fmp_field="beta",
    ),
    "momentum_6m": FactorDefinition(
        name="momentum_6m",
        category=FactorCategory.MOMENTUM,
        source=FactorSource.FMP,
        transform=FactorTransform.PCT_CHANGE,
        description="6-month price momentum",
        fmp_endpoint="/api/v3/historical-price-full/{sym}",
        fmp_field="close",
        requires_history=True,
    ),
    "momentum_12m": FactorDefinition(
        name="momentum_12m",
        category=FactorCategory.MOMENTUM,
        source=FactorSource.FMP,
        transform=FactorTransform.PCT_CHANGE,
        description="12-month price momentum",
        fmp_endpoint="/api/v3/historical-price-full/{sym}",
        fmp_field="close",
        requires_history=True,
    ),
    "historical_vol_90d": FactorDefinition(
        name="historical_vol_90d",
        category=FactorCategory.VOLATILITY,
        source=FactorSource.FMP,
        transform=FactorTransform.ZSCORE,
        description="90-day historical return volatility",
        fmp_endpoint="/api/v3/historical-price-full/{sym}",
        fmp_field="close",
        requires_history=True,
    ),
    "debt_to_equity": FactorDefinition(
        name="debt_to_equity",
        category=FactorCategory.LEVERAGE,
        source=FactorSource.FMP,
        transform=FactorTransform.ZSCORE,
        description="Total debt to equity ratio",
        fmp_endpoint="/api/v3/key-metrics/{sym}",
        fmp_field="debtToEquity",
    ),
    "roe": FactorDefinition(
        name="roe",
        category=FactorCategory.QUALITY,
        source=FactorSource.FMP,
        transform=FactorTransform.ZSCORE,
        description="Return on equity",
        fmp_endpoint="/api/v3/key-metrics/{sym}",
        fmp_field="roe",
    ),
    "roic": FactorDefinition(
        name="roic",
        category=FactorCategory.QUALITY,
        source=FactorSource.FMP,
        transform=FactorTransform.ZSCORE,
        description="Return on invested capital",
        fmp_endpoint="/api/v3/key-metrics/{sym}",
        fmp_field="roic",
    ),
    "operating_margin": FactorDefinition(
        name="operating_margin",
        category=FactorCategory.QUALITY,
        source=FactorSource.FMP,
        transform=FactorTransform.ZSCORE,
        description="Operating profit margin",
        fmp_endpoint="/api/v3/key-metrics/{sym}",
        fmp_field="operatingProfitMargin",
    ),
    "interest_coverage": FactorDefinition(
        name="interest_coverage",
        category=FactorCategory.LEVERAGE,
        source=FactorSource.FMP,
        transform=FactorTransform.ZSCORE,
        description="Interest coverage ratio",
        fmp_endpoint="/api/v3/ratios/{sym}",
        fmp_field="interestCoverage",
    ),
}


# Combined catalog
ALL_FACTORS: dict[str, FactorDefinition] = {**DASHBOARD_FACTORS, **FMP_FACTORS}


def get_available_factors(include_fmp: bool = False) -> dict[str, FactorDefinition]:
    """Return factors available given current configuration."""
    if include_fmp:
        return ALL_FACTORS
    return DASHBOARD_FACTORS
