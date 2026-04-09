"""
LND Service - Lightning Network operations
Handles invoice creation, payment verification, channel management
"""

import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from decimal import Decimal
import ssl

import httpx

try:
    from grpc import aio as grpc_aio
    import invoicesrpc
    import lnrpc
    _GRPC_AVAILABLE = True
except ImportError:  # pragma: no cover — only missing in test/CI environments
    grpc_aio = None  # type: ignore[assignment]
    invoicesrpc = None  # type: ignore[assignment]
    lnrpc = None  # type: ignore[assignment]
    _GRPC_AVAILABLE = False

from src.core.config import get_settings

logger = logging.getLogger(__name__)


class LNDService:
    """Lightning Network Daemon operations"""

    def __init__(self):
        self.settings = get_settings()
        self.rest_url = self.settings.lnd_rest_url
        self.macaroon_path = self.settings.lnd_macaroon_path
        self.cert_path = self.settings.lnd_cert_path
        self.hold_invoice_expiry = self.settings.lnd_hold_invoice_expiry_minutes
        self.invoice_timeout = self.settings.lnd_invoice_timeout_hours
        self._macaroon = None
        self._ssl_context = None

    def _load_macaroon(self) -> str:
        """Load hex-encoded macaroon from file"""
        if self._macaroon:
            return self._macaroon
        try:
            with open(self.macaroon_path, 'rb') as f:
                macaroon_hex = f.read().hex()
            self._macaroon = macaroon_hex
            return macaroon_hex
        except FileNotFoundError:
            logger.error(f"Macaroon not found at {self.macaroon_path}")
            raise

    def _get_ssl_context(self) -> ssl.SSLContext:
        """
        Get SSL context for LND REST API.

        Loads the TLS certificate from the path configured in
        ``settings.lnd_cert_path`` so that the LND self-signed cert is
        trusted without disabling verification entirely.

        LND uses an IP SAN rather than a hostname in its cert, so
        ``check_hostname`` is disabled while ``verify_mode`` remains
        ``CERT_REQUIRED``.
        """
        if self._ssl_context:
            return self._ssl_context
        try:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.load_verify_locations(self.cert_path)
            self._ssl_context = context
            return context
        except FileNotFoundError:
            logger.error(f"LND TLS cert not found at {self.cert_path}")
            raise
        except Exception as e:
            logger.error(f"Failed to create SSL context: {e}")
            raise

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for LND REST API"""
        macaroon = self._load_macaroon()
        return {
            "Grpc-Metadata-macaroon": macaroon,
            "Content-Type": "application/json",
        }

    async def create_hold_invoice(
        self,
        amount_sats: int,
        memo: str,
        description_hash: Optional[str] = None,
        cltv_expiry: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Create a hold invoice (no preimage)

        Args:
            amount_sats: Amount in satoshis
            memo: Invoice memo/description
            description_hash: Hash of a longer description
            cltv_expiry: CLTV expiry in blocks (default: ~4 days)

        Returns:
            {
                "payment_hash": "...",  # hex string
                "payment_request": "lnbc...",  # BOLT11 invoice
                "add_index": "...",  # invoice index
            }
        """
        try:
            url = f"{self.rest_url}/v1/invoices"
            headers = self._get_headers()

            payload = {
                "value": str(amount_sats),
                "memo": memo,
                "expiry": str(self.hold_invoice_expiry * 60),  # Convert to seconds
                "is_private": True,
            }

            if description_hash:
                payload["description_hash"] = description_hash

            if cltv_expiry:
                payload["cltv_expiry"] = str(cltv_expiry)

            async with httpx.AsyncClient(verify=self._get_ssl_context(), timeout=30) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()

            data = response.json()
            logger.info(f"Hold invoice created: {data.get('r_hash')}")

            return {
                "payment_hash": data.get("r_hash"),
                "payment_request": data.get("payment_request"),
                "add_index": data.get("add_index"),
            }

        except httpx.HTTPError as e:
            logger.error(f"Failed to create hold invoice: {e}")
            raise

    async def get_invoice(self, payment_hash: str) -> Optional[Dict[str, Any]]:
        """
        Get invoice details by payment hash

        Args:
            payment_hash: Hex-encoded payment hash

        Returns:
            Invoice details or None if not found
        """
        try:
            url = f"{self.rest_url}/v1/invoice/{payment_hash}"
            headers = self._get_headers()

            async with httpx.AsyncClient(verify=self._get_ssl_context(), timeout=30) as client:
                response = await client.get(url, headers=headers)

                if response.status_code == 404:
                    logger.warning(f"Invoice not found: {payment_hash}")
                    return None

                response.raise_for_status()

            data = response.json()
            return {
                "state": data.get("state"),  # OPEN, SETTLED, CANCELED, ACCEPTED
                "settled": data.get("settled", False),
                "value": int(data.get("value", 0)),
                "amount_paid": int(data.get("amt_paid_sat", 0)),
                "creation_date": int(data.get("creation_date", 0)),
                "settle_date": int(data.get("settle_date", 0)),
                "expiry": int(data.get("expiry", 0)),
                "memo": data.get("memo", ""),
                "htlcs": data.get("htlcs", []),
            }

        except httpx.HTTPError as e:
            logger.error(f"Failed to get invoice: {e}")
            raise

    async def check_invoice_paid(self, payment_hash: str) -> bool:
        """
        Check if invoice is fully paid

        Args:
            payment_hash: Hex-encoded payment hash

        Returns:
            True if invoice is settled, False otherwise
        """
        try:
            invoice = await self.get_invoice(payment_hash)
            if not invoice:
                return False
            return invoice["settled"]
        except Exception as e:
            logger.error(f"Error checking invoice payment: {e}")
            return False

    async def settle_invoice(
        self,
        preimage: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Settle a hold invoice using preimage

        Args:
            preimage: Hex-encoded preimage (32 bytes = 64 hex chars)

        Returns:
            Settlement result or None if failed
        """
        try:
            if len(preimage) != 64:
                raise ValueError(f"Preimage must be 64 hex chars, got {len(preimage)}")

            url = f"{self.rest_url}/v1/invoices/settle"
            headers = self._get_headers()

            payload = {"preimage": preimage}

            async with httpx.AsyncClient(verify=self._get_ssl_context(), timeout=30) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()

            logger.info(f"Invoice settled with preimage")
            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Failed to settle invoice: {e}")
            raise

    async def get_wallet_balance(self) -> Dict[str, int]:
        """
        Get wallet balance

        Returns:
            {
                "total_balance": satoshis,
                "confirmed_balance": satoshis,
                "unconfirmed_balance": satoshis,
            }
        """
        try:
            url = f"{self.rest_url}/v1/balance/blockchain"
            headers = self._get_headers()

            async with httpx.AsyncClient(verify=self._get_ssl_context(), timeout=30) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()

            data = response.json()
            return {
                "total_balance": int(data.get("total_balance", 0)),
                "confirmed_balance": int(data.get("confirmed_balance", 0)),
                "unconfirmed_balance": int(data.get("unconfirmed_balance", 0)),
            }

        except httpx.HTTPError as e:
            logger.error(f"Failed to get wallet balance: {e}")
            raise

    async def list_channels(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """
        List open channels

        Args:
            active_only: Return only active channels

        Returns:
            List of channel details
        """
        try:
            url = f"{self.rest_url}/v1/channels"
            headers = self._get_headers()

            async with httpx.AsyncClient(verify=self._get_ssl_context(), timeout=30) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()

            data = response.json()
            channels = []

            for ch in data.get("channels", []):
                if active_only and not ch.get("active", False):
                    continue

                channels.append({
                    "channel_id": ch.get("chan_id"),
                    "remote_pubkey": ch.get("remote_pubkey"),
                    "capacity": int(ch.get("capacity", 0)),
                    "local_balance": int(ch.get("local_balance", 0)),
                    "remote_balance": int(ch.get("remote_balance", 0)),
                    "active": ch.get("active", False),
                    "initiated_by_us": ch.get("initiator", False),
                    "num_updates": int(ch.get("num_updates", 0)),
                })

            return channels

        except httpx.HTTPError as e:
            logger.error(f"Failed to list channels: {e}")
            raise

    async def send_payment(
        self,
        payment_request: str,
        timeout_seconds: int = 120,
    ) -> Optional[Dict[str, Any]]:
        """
        Send payment via payment request

        Args:
            payment_request: BOLT11 invoice string
            timeout_seconds: Payment attempt timeout

        Returns:
            Payment result or None if failed
        """
        try:
            url = f"{self.rest_url}/v1/channels/transactions"
            headers = self._get_headers()

            payload = {
                "payment_request": payment_request,
                "timeout_seconds": timeout_seconds,
            }

            async with httpx.AsyncClient(verify=self._get_ssl_context(), timeout=timeout_seconds + 10) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()

            data = response.json()

            if data.get("payment_error"):
                logger.error(f"Payment failed: {data.get('payment_error')}")
                return None

            return {
                "payment_hash": data.get("payment_hash"),
                "payment_preimage": data.get("payment_preimage"),
                "value": int(data.get("payment", {}).get("value", 0)),
                "fee": int(data.get("payment", {}).get("fee", 0)),
            }

        except httpx.HTTPError as e:
            logger.error(f"Failed to send payment: {e}")
            return None

    async def get_node_info(self) -> Optional[Dict[str, Any]]:
        """
        Get LND node information

        Returns:
            Node info or None if failed
        """
        try:
            url = f"{self.rest_url}/v1/getinfo"
            headers = self._get_headers()

            async with httpx.AsyncClient(verify=self._get_ssl_context(), timeout=30) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()

            data = response.json()
            return {
                "identity_pubkey": data.get("identity_pubkey"),
                "alias": data.get("alias", ""),
                "num_peers": int(data.get("num_peers", 0)),
                "num_pending_channels": int(data.get("num_pending_channels", 0)),
                "num_active_channels": int(data.get("num_active_channels", 0)),
                "num_inactive_channels": int(data.get("num_inactive_channels", 0)),
                "chains": data.get("chains", []),
                "uris": data.get("uris", []),
            }

        except httpx.HTTPError as e:
            logger.error(f"Failed to get node info: {e}")
            raise

    async def new_address(self, address_type: str = "p2wkh") -> Optional[str]:
        """
        Generate new on-chain address

        Args:
            address_type: "p2wkh", "np2wkh", or "p2tr"

        Returns:
            New address or None if failed
        """
        try:
            url = f"{self.rest_url}/v1/newaddress"
            headers = self._get_headers()

            payload = {
                "type": address_type.upper(),
            }

            async with httpx.AsyncClient(verify=self._get_ssl_context(), timeout=30) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()

            data = response.json()
            address = data.get("address")
            logger.info(f"New address generated: {address}")
            return address

        except httpx.HTTPError as e:
            logger.error(f"Failed to generate address: {e}")
            return None
