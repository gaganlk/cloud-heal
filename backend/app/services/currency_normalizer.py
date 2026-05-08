"""
Currency Normalizer — converts cloud provider billing currencies to USD.

Architecture:
  - Primary: exchangerate-api.com free tier (no API key required)
  - Cache: Redis (TTL=3600s) with local dict fallback
  - Fallback: hardcoded approximate rates (updated quarterly)

Usage:
    normalizer = CurrencyNormalizer()
    usd = await normalizer.to_usd(150.0, "EUR")
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Optional

import httpx

logger = logging.getLogger(__name__)

RATES_API_URL = "https://api.exchangerate-api.com/v4/latest/USD"
CACHE_KEY = "finops:fx_rates"
CACHE_TTL = 3600  # 1 hour

# Fallback rates (USD base, updated periodically)
FALLBACK_RATES: Dict[str, float] = {
    "USD": 1.0,
    "EUR": 1.09,
    "GBP": 1.27,
    "JPY": 0.0067,
    "AUD": 0.65,
    "CAD": 0.74,
    "CHF": 1.12,
    "INR": 0.012,
    "CNY": 0.138,
    "BRL": 0.20,
}


class CurrencyNormalizer:
    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._local_cache: Dict[str, float] = {}
        self._cache_ts: Optional[float] = None

    async def _fetch_rates(self) -> Dict[str, float]:
        """Fetch live rates from API, fall back to hardcoded on failure."""
        # Check local memory cache (5 min)
        if self._cache_ts and (datetime.now().timestamp() - self._cache_ts) < 300:
            return self._local_cache

        # Check Redis cache
        if self._redis:
            try:
                cached = await self._redis.get(CACHE_KEY)
                if cached:
                    rates = json.loads(cached)
                    self._local_cache = rates
                    return rates
            except Exception:
                pass

        # Fetch live rates
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(RATES_API_URL)
                resp.raise_for_status()
                data = resp.json()
                rates = data.get("rates", {})

                # Cache in Redis
                if self._redis:
                    try:
                        await self._redis.setex(CACHE_KEY, CACHE_TTL, json.dumps(rates))
                    except Exception:
                        pass

                self._local_cache = rates
                self._cache_ts = datetime.now().timestamp()
                logger.debug(f"[CurrencyNormalizer] Fetched {len(rates)} FX rates")
                return rates
        except Exception as e:
            logger.warning(f"[CurrencyNormalizer] Live rate fetch failed ({e}) — using fallback")
            return FALLBACK_RATES

    async def to_usd(self, amount: float, currency: str) -> tuple[float, float]:
        """
        Convert amount to USD.
        Returns (usd_amount, exchange_rate).
        """
        if currency.upper() == "USD":
            return round(amount, 6), 1.0

        rates = await self._fetch_rates()
        # rates dict is: { "EUR": rate_vs_USD }
        # If rate is X: 1 USD = X EUR → 1 EUR = 1/X USD
        rate_vs_usd = rates.get(currency.upper())
        if not rate_vs_usd:
            logger.warning(f"[CurrencyNormalizer] Unknown currency '{currency}' — treating as USD")
            return round(amount, 6), 1.0

        usd_amount = amount / rate_vs_usd
        return round(usd_amount, 6), round(rate_vs_usd, 6)


# Module-level singleton — redis attached lazily after startup
_normalizer: Optional[CurrencyNormalizer] = None


def get_normalizer(redis_client=None) -> CurrencyNormalizer:
    global _normalizer
    if _normalizer is None:
        _normalizer = CurrencyNormalizer(redis_client)
    return _normalizer
