"""
Unit tests for src/services/rate.py

Covers:
- In-memory cache hit avoids HTTP call
- DB cache hit avoids HTTP call
- Stale DB cache falls back when HTTP fetch fails
- ZAR→sats and sats→ZAR conversions
- validate_transfer_amount min/max enforcement
"""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.models import RateCache
from src.services.rate import RateService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_svc(db) -> RateService:
    return RateService(db)


MOCK_RATE = Decimal("1200000.00")


# ---------------------------------------------------------------------------
# Memory cache hit
# ---------------------------------------------------------------------------

class TestMemoryCache:
    @pytest.mark.asyncio
    async def test_second_call_uses_cached_rate(self, db):
        svc = _make_svc(db)

        with patch.object(svc, "_fetch_rate", new=AsyncMock(return_value=MOCK_RATE)) as mock_fetch:
            rate1 = await svc.get_zar_per_btc()
            rate2 = await svc.get_zar_per_btc()

        assert rate1 == MOCK_RATE
        assert rate2 == MOCK_RATE
        # _fetch_rate must only be called once — second call hits memory cache
        assert mock_fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_expired_memory_cache_refetches(self, db):
        svc = _make_svc(db)
        pair = "ZAR_BTC"

        # Pre-populate an expired memory cache entry
        svc._rate_cache[pair] = {
            "rate": Decimal("900000.00"),
            "expires_at": datetime.utcnow() - timedelta(seconds=1),  # expired
        }

        with patch.object(svc, "_fetch_rate", new=AsyncMock(return_value=MOCK_RATE)):
            rate = await svc.get_zar_per_btc()

        assert rate == MOCK_RATE


# ---------------------------------------------------------------------------
# DB cache
# ---------------------------------------------------------------------------

class TestDBCache:
    @pytest.mark.asyncio
    async def test_fresh_db_cache_used_without_http_call(self, db):
        svc = _make_svc(db)
        pair = "ZAR_BTC"

        # Insert a fresh DB cache row
        db_cache = RateCache(
            pair=pair,
            rate=MOCK_RATE,
            source="coingecko",
            cached_at=datetime.utcnow(),
        )
        db.add(db_cache)
        db.commit()

        with patch.object(svc, "_fetch_rate", new=AsyncMock()) as mock_fetch:
            rate = await svc.get_zar_per_btc()

        assert rate == MOCK_RATE
        mock_fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_stale_db_cache_used_as_fallback_on_http_error(self, db):
        svc = _make_svc(db)
        pair = "ZAR_BTC"
        stale_rate = Decimal("800000.00")

        # Insert a stale DB cache row (older than cache_minutes)
        db_cache = RateCache(
            pair=pair,
            rate=stale_rate,
            source="coingecko",
            cached_at=datetime.utcnow() - timedelta(hours=2),
        )
        db.add(db_cache)
        db.commit()

        with patch.object(svc, "_fetch_rate", new=AsyncMock(side_effect=Exception("API down"))):
            rate = await svc.get_zar_per_btc()

        assert rate == stale_rate


# ---------------------------------------------------------------------------
# Unit conversions
# ---------------------------------------------------------------------------

class TestConversions:
    @pytest.mark.asyncio
    async def test_sats_for_zar(self, db):
        svc = _make_svc(db)
        with patch.object(svc, "get_zar_per_btc", new=AsyncMock(return_value=Decimal("1000000"))):
            # 1 BTC = 1 000 000 ZAR → 1 ZAR = 100 sats
            sats = await svc.get_sats_for_zar(Decimal("100"))
        assert sats == 10_000  # 100 ZAR * 100 sats/ZAR

    @pytest.mark.asyncio
    async def test_zar_for_sats(self, db):
        svc = _make_svc(db)
        with patch.object(svc, "get_zar_per_btc", new=AsyncMock(return_value=Decimal("1000000"))):
            # 1 BTC = 1 000 000 ZAR, 100 sats = 100/100_000_000 BTC = 0.000001 BTC
            # 0.000001 * 1 000 000 = 1.00 ZAR
            zar = await svc.get_zar_for_sats(100)
        assert zar == Decimal("1.00")

    @pytest.mark.asyncio
    async def test_zero_sats_returns_zero_zar(self, db):
        svc = _make_svc(db)
        zar = await svc.get_zar_for_sats(0)
        assert zar == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_zero_zar_returns_zero_sats(self, db):
        svc = _make_svc(db)
        sats = await svc.get_sats_for_zar(Decimal("0"))
        assert sats == 0


# ---------------------------------------------------------------------------
# validate_transfer_amount
# ---------------------------------------------------------------------------

class TestValidateTransferAmount:
    @pytest.mark.asyncio
    async def test_amount_below_minimum_is_invalid(self, db):
        svc = _make_svc(db)
        with patch.object(svc, "get_zar_per_btc", new=AsyncMock(return_value=MOCK_RATE)):
            result = await svc.validate_transfer_amount(Decimal("50"))
        assert result["valid"] is False
        assert "Minimum" in result["error"]

    @pytest.mark.asyncio
    async def test_amount_above_maximum_is_invalid(self, db):
        svc = _make_svc(db)
        with patch.object(svc, "get_zar_per_btc", new=AsyncMock(return_value=MOCK_RATE)):
            result = await svc.validate_transfer_amount(Decimal("600"))
        assert result["valid"] is False
        assert "Maximum" in result["error"]

    @pytest.mark.asyncio
    async def test_valid_amount_passes(self, db):
        svc = _make_svc(db)
        with patch.object(svc, "get_zar_per_btc", new=AsyncMock(return_value=MOCK_RATE)):
            result = await svc.validate_transfer_amount(Decimal("200"))
        assert result["valid"] is True
        assert result["amount_sats"] > 0
