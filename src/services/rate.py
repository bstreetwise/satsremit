"""
Rate Service - Exchange rate management
Handles ZAR ↔ SAT conversion with caching and multiple feed sources
"""

import logging
import asyncio
from typing import Optional, Dict, Any
from decimal import Decimal
from datetime import datetime, timedelta

import httpx
from sqlalchemy.orm import Session

from src.models.models import RateCache
from src.core.config import get_settings

logger = logging.getLogger(__name__)


class RateService:
    """Exchange rate service for ZAR/SAT conversion"""

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.rate_source = self.settings.rate_source or "coingecko"
        self.cache_minutes = self.settings.rate_cache_minutes
        self._rate_cache: Dict[str, Dict[str, Any]] = {}

    async def get_zar_per_btc(self) -> Decimal:
        """
        Get ZAR per BTC exchange rate

        Returns:
            Decimal exchange rate (e.g., Decimal("120000.00"))
        """
        pair = "ZAR_BTC"

        # Check memory cache
        if pair in self._rate_cache:
            cached = self._rate_cache[pair]
            if datetime.utcnow() < cached["expires_at"]:
                logger.debug(f"Using cached rate: {cached['rate']}")
                return cached["rate"]

        # Check database cache
        db_cache = self.db.query(RateCache).filter(
            RateCache.pair == pair
        ).first()

        if db_cache:
            # Check if still valid — cached_at always has a DB default
            age = datetime.utcnow() - db_cache.cached_at
            if age < timedelta(minutes=self.cache_minutes):
                rate = Decimal(str(db_cache.rate))
                self._rate_cache[pair] = {
                    "rate": rate,
                    "expires_at": datetime.utcnow() + timedelta(minutes=self.cache_minutes),
                }
                logger.debug(f"Using database cached rate: {rate}")
                return rate

        # Fetch fresh rate
        try:
            rate = await self._fetch_rate(self.rate_source)

            # Update cache
            if db_cache:
                db_cache.rate = rate
                db_cache.cached_at = datetime.utcnow()
            else:
                db_cache = RateCache(
                    pair=pair,
                    rate=rate,
                    source=self.rate_source,
                )
                self.db.add(db_cache)

            self.db.commit()

            # Update memory cache
            self._rate_cache[pair] = {
                "rate": rate,
                "expires_at": datetime.utcnow() + timedelta(minutes=self.cache_minutes),
            }

            logger.info(f"Fresh rate fetched: {rate} ZAR/BTC from {self.rate_source}")
            return rate

        except Exception as e:
            logger.error(f"Failed to fetch rate: {e}")
            # Fall back to database cache if available
            if db_cache:
                rate = Decimal(str(db_cache.rate))
                logger.warning(f"Using stale cache due to fetch error: {rate}")
                return rate
            raise

    async def _fetch_rate(self, source: str) -> Decimal:
        """
        Fetch exchange rate from source

        Args:
            source: Rate source name (coingecko, kraken, etc.)

        Returns:
            Exchange rate as Decimal
        """
        if source == "coingecko":
            return await self._fetch_coingecko()
        elif source == "kraken":
            return await self._fetch_kraken()
        elif source == "bitstamp":
            return await self._fetch_bitstamp()
        else:
            raise ValueError(f"Unknown rate source: {source}")

    async def _fetch_coingecko(self) -> Decimal:
        """Fetch from CoinGecko API (free, no auth required)"""
        try:
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {
                "ids": "bitcoin",
                "vs_currencies": "zar",
                "include_market_cap": "false",
                "include_24hr_vol": "false",
            }

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()

            data = response.json()
            rate = Decimal(str(data["bitcoin"]["zar"]))

            if rate <= 0:
                raise ValueError("Invalid rate from CoinGecko")

            logger.debug(f"CoinGecko rate: {rate}")
            return rate

        except httpx.HTTPError as e:
            logger.error(f"CoinGecko fetch error: {e}")
            raise

    async def _fetch_kraken(self) -> Decimal:
        """Fetch from Kraken API (requires API key for real trading, but ticker is public)"""
        try:
            # Kraken XBTCZAR pair
            url = "https://api.kraken.com/0/public/Ticker"
            params = {"pair": "XBTCZAR"}

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()

            data = response.json()

            if data.get("error"):
                raise ValueError(f"Kraken error: {data['error']}")

            # Get last trade price
            pair_data = list(data["result"].values())[0]
            last_price = pair_data["c"]  # close price
            rate = Decimal(str(last_price[0]))

            if rate <= 0:
                raise ValueError("Invalid rate from Kraken")

            logger.debug(f"Kraken rate (SA): {rate}")
            return rate

        except httpx.HTTPError as e:
            logger.error(f"Kraken fetch error: {e}")
            raise

    async def _fetch_bitstamp(self) -> Decimal:
        """Fetch from Bitstamp API (public, no auth required)"""
        try:
            # Bitstamp BTCZAR pair
            url = "https://www.bitstamp.net/api/v2/ticker/btczar/"

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url)
                response.raise_for_status()

            data = response.json()
            last_price = data.get("last")
            rate = Decimal(str(last_price))

            if rate <= 0:
                raise ValueError("Invalid rate from Bitstamp")

            logger.debug(f"Bitstamp rate (SA): {rate}")
            return rate

        except httpx.HTTPError as e:
            logger.error(f"Bitstamp fetch error: {e}")
            raise

    async def get_usd_per_zar(self) -> Decimal:
        """
        Get USD per ZAR exchange rate from reliable market sources
        Uses direct USD/ZAR data for accuracy matching standard rates (like Google)

        Returns:
            Decimal ZAR per USD (e.g., Decimal("20.50"))
        """
        pair = "USD_ZAR"

        # Check memory cache
        if pair in self._rate_cache:
            cached = self._rate_cache[pair]
            if datetime.utcnow() < cached["expires_at"]:
                logger.debug(f"Using cached USD/ZAR rate: {cached['rate']}")
                return cached["rate"]

        # Check database cache
        db_cache = self.db.query(RateCache).filter(
            RateCache.pair == pair
        ).first()

        if db_cache:
            age = datetime.utcnow() - db_cache.cached_at
            if age < timedelta(minutes=self.cache_minutes):
                rate = Decimal(str(db_cache.rate))
                self._rate_cache[pair] = {
                    "rate": rate,
                    "expires_at": datetime.utcnow() + timedelta(minutes=self.cache_minutes),
                }
                logger.debug(f"Using cached USD/ZAR from DB: {rate}")
                return rate

        # Fetch fresh rate directly from reliable sources
        try:
            rate = await self._fetch_usd_zar_direct()
            
            logger.info(f"Fresh USD/ZAR rate fetched: {rate} ZAR per USD")

            # Update cache
            if db_cache:
                db_cache.rate = rate
                db_cache.cached_at = datetime.utcnow()
            else:
                db_cache = RateCache(
                    pair=pair,
                    rate=rate,
                    source="coingecko_direct",
                )
                self.db.add(db_cache)

            self.db.commit()

            # Update memory cache
            self._rate_cache[pair] = {
                "rate": rate,
                "expires_at": datetime.utcnow() + timedelta(minutes=self.cache_minutes),
            }

            return rate

        except Exception as e:
            logger.error(f"Failed to fetch USD/ZAR rate: {e}")
            # Fall back to database cache if available
            if db_cache:
                rate = Decimal(str(db_cache.rate))
                logger.warning(f"Using stale USD/ZAR cache due to fetch error: {rate}")
                return rate
            raise

    async def _fetch_usd_zar_direct(self) -> Decimal:
        """
        Fetch USD to ZAR exchange rate from fiat exchange API (matches Google Finance rates)
        
        Returns:
            Decimal ZAR per USD (e.g., Decimal("20.50"))
        """
        try:
            # Use exchangerate.host API for direct fiat conversion (free, no auth)
            # This provides rates aligned with major financial sources like Google Finance
            url = "https://api.exchangerate.host/latest"
            params = {
                "base": "USD",
                "symbols": "ZAR",
            }

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()

            data = response.json()
            
            if not data.get("success"):
                raise ValueError(f"Exchange rate API error: {data.get('error', 'Unknown error')}")

            usd_to_zar = Decimal(str(data["rates"]["ZAR"]))

            if usd_to_zar <= 0:
                raise ValueError("Invalid rate from exchange API")

            logger.debug(f"ExchangeRate.host USD/ZAR rate: 1 USD = {usd_to_zar:.2f} ZAR")
            
            return usd_to_zar

        except httpx.HTTPError as e:
            logger.error(f"ExchangeRate API fetch error: {e}")
            # Try alternative method
            try:
                return await self._fetch_usd_zar_fallback()
            except Exception as fallback_e:
                logger.error(f"Fallback USD/ZAR fetch also failed: {fallback_e}")
                raise

    async def _fetch_usd_zar_fallback(self) -> Decimal:
        """
        Fallback method to fetch USD/ZAR rate from alternative API
        
        Returns:
            Decimal ZAR per USD
        """
        try:
            # Fallback to another exchange rate API
            url = "https://open.er-api.com/v6/latest/USD"

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url)
                response.raise_for_status()

            data = response.json()
            
            if data.get("result") != "success":
                raise ValueError("Fallback API error")

            usd_to_zar = Decimal(str(data["rates"]["ZAR"]))
            logger.debug(f"Fallback USD/ZAR via open.er-api: 1 USD = {usd_to_zar:.2f} ZAR")
            
            return usd_to_zar

        except Exception as e:
            logger.error(f"Fallback method failed: {e}")
            raise

    async def get_zar_for_sats(self, sats: int) -> Decimal:
        """
        Convert satoshis to ZAR

        Args:
            sats: Amount in satoshis

        Returns:
            Amount in ZAR
        """
        if sats <= 0:
            return Decimal("0.00")

        rate = await self.get_zar_per_btc()
        # Convert: sats / 100,000,000 * rate
        zar = Decimal(sats) / Decimal("100000000") * rate
        return zar.quantize(Decimal("0.01"))

    async def get_sats_for_zar(self, zar: Decimal) -> int:
        """
        Convert ZAR to satoshis

        Args:
            zar: Amount in ZAR

        Returns:
            Amount in satoshis (rounded down)
        """
        if zar <= 0:
            return 0

        rate = await self.get_zar_per_btc()
        # Convert: zar / rate * 100,000,000
        sats = (zar / rate) * Decimal("100000000")
        return int(sats)  # Round down

    async def validate_transfer_amount(
        self,
        amount_zar: Decimal,
    ) -> Dict[str, Any]:
        """
        Validate transfer amount against limits

        Args:
            amount_zar: Transfer amount in ZAR

        Returns:
            {
                "valid": bool,
                "amount_zar": Decimal,
                "amount_sats": int,
                "rate_zar_per_btc": Decimal,
                "error": Optional[str],
            }
        """
        try:
            min_amount = Decimal(str(self.settings.min_transfer_zar))
            max_amount = Decimal(str(self.settings.max_transfer_zar))

            if amount_zar < min_amount:
                return {
                    "valid": False,
                    "amount_zar": amount_zar,
                    "amount_sats": 0,
                    "rate_zar_per_btc": Decimal("0"),
                    "error": f"Minimum transfer: ZAR {min_amount}",
                }

            if amount_zar > max_amount:
                return {
                    "valid": False,
                    "amount_zar": amount_zar,
                    "amount_sats": 0,
                    "rate_zar_per_btc": Decimal("0"),
                    "error": f"Maximum transfer: ZAR {max_amount}",
                }

            # Get current rate
            rate = await self.get_zar_per_btc()

            # Convert to sats
            sats = await self.get_sats_for_zar(amount_zar)

            # Ensure minimum sats (e.g., 100 sats)
            if sats < 100:
                return {
                    "valid": False,
                    "amount_zar": amount_zar,
                    "amount_sats": sats,
                    "rate_zar_per_btc": rate,
                    "error": f"Amount too small: {sats} sats (min: 100)",
                }

            return {
                "valid": True,
                "amount_zar": amount_zar,
                "amount_sats": sats,
                "rate_zar_per_btc": rate,
                "error": None,
            }

        except Exception as e:
            logger.error(f"Validation error: {e}")
            return {
                "valid": False,
                "amount_zar": amount_zar,
                "amount_sats": 0,
                "rate_zar_per_btc": Decimal("0"),
                "error": str(e),
            }

    async def get_fee_breakdown(self, amount_zar: Decimal) -> Dict[str, Decimal]:
        """
        Calculate fee breakdown for a transfer

        Args:
            amount_zar: Transfer amount in ZAR

        Returns:
            {
                "amount_zar": Decimal,
                "platform_fee_zar": Decimal,
                "agent_commission_zar": Decimal,
                "total_fees_zar": Decimal,
                "receiver_gets_zar": Decimal,
            }
        """
        try:
            platform_fee_percent = Decimal(str(self.settings.platform_fee_percent))
            agent_commission_percent = Decimal(str(self.settings.agent_commission_percent))

            platform_fee = (amount_zar * platform_fee_percent) / Decimal("100")
            agent_commission = (amount_zar * agent_commission_percent) / Decimal("100")
            total_fees = platform_fee + agent_commission
            receiver_gets = amount_zar - total_fees

            return {
                "amount_zar": amount_zar.quantize(Decimal("0.01")),
                "platform_fee_zar": platform_fee.quantize(Decimal("0.01")),
                "agent_commission_zar": agent_commission.quantize(Decimal("0.01")),
                "total_fees_zar": total_fees.quantize(Decimal("0.01")),
                "receiver_gets_zar": receiver_gets.quantize(Decimal("0.01")),
            }

        except Exception as e:
            logger.error(f"Fee calculation error: {e}")
            raise
