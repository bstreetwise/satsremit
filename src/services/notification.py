"""
Notification service using WhatsApp Business API
"""

import logging
import httpx
from typing import Optional
from src.core.config import get_settings

logger = logging.getLogger(__name__)


class NotificationService:
    """Send notifications via WhatsApp Business API"""

    def __init__(self):
        self.settings = get_settings()
        self.account_id = self.settings.whatsapp_business_account_id
        self.phone_number_id = self.settings.whatsapp_business_phone_number_id
        self.access_token = self.settings.whatsapp_business_access_token
        self.api_url = "https://graph.instagram.com/v18.0"

    async def send_whatsapp(
        self,
        phone_number: str,
        message: str,
        message_type: str = "text",
    ) -> Optional[dict]:
        """
        Send WhatsApp message via WhatsApp Business API

        Args:
            phone_number: Recipient phone in E.164 format (e.g., "+263123456789")
            message: Message content
            message_type: Type of message ("text")

        Returns:
            Response data or None if failed
        """
        try:
            url = f"{self.api_url}/{self.phone_number_id}/messages"

            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            }

            # Ensure phone is in E.164 format
            recipient = phone_number.replace("+", "") if phone_number.startswith("+") else phone_number

            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": recipient,
                "type": "text",
                "text": {"body": message},
            }

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(url, json=payload, headers=headers)

                if response.status_code in [200, 201]:
                    logger.info(f"WhatsApp message sent to {phone_number}")
                    return response.json()
                else:
                    error_msg = response.text
                    logger.error(
                        f"WhatsApp API error {response.status_code}: {error_msg}"
                    )
                    return None

        except httpx.RequestError as e:
            logger.error(f"WhatsApp request failed: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error sending WhatsApp message: {str(e)}")
            return None

    async def send_pin_to_receiver(
        self, phone_number: str, pin: str, transfer_reference: str, amount_zar: float = None
    ) -> bool:
        """
        Send verification PIN to receiver via WhatsApp

        Args:
            phone_number: Receiver's phone
            pin: 4-digit verification PIN
            transfer_reference: Transfer reference ID
            amount_zar: Amount in ZAR (optional)

        Returns:
            True if sent successfully
        """
        amount_text = f"\nAmount: ZAR {amount_zar:.2f}" if amount_zar else ""
        
        message = (
            f"🎉 *SatsRemit Transfer Received*\n\n"
            f"Reference: {transfer_reference}\n"
            f"Verification PIN: {pin}{amount_text}\n\n"
            f"*Valid for 5 minutes*\n"
            f"Enter this PIN in the SatsRemit app to confirm payment.\n\n"
            f"If you didn't expect this, please contact support."
        )

        result = await self.send_whatsapp(phone_number, message)
        return result is not None

    async def notify_agent_pending_transfer(
        self,
        agent_phone: str,
        transfer_reference: str,
        receiver_name: str,
        amount_zar: float,
    ) -> bool:
        """
        Notify agent of pending transfer awaiting verification

        Args:
            agent_phone: Agent's phone number
            transfer_reference: Transfer reference
            receiver_name: Name of receiver
            amount_zar: Amount in ZAR

        Returns:
            True if sent successfully
        """
        message = (
            f"📢 *New Transfer Alert*\n\n"
            f"Reference: {transfer_reference}\n"
            f"Receiver: {receiver_name}\n"
            f"Amount: ZAR {amount_zar:.2f}\n\n"
            f"Please verify the receiver and process payment.\n"
            f"Check SatsRemit dashboard for details."
        )

        result = await self.send_whatsapp(agent_phone, message)
        return result is not None

    async def notify_sender_completion(
        self,
        sender_phone: str,
        transfer_reference: str,
        receiver_name: str,
        amount_zar: float,
        status: str = "completed",
    ) -> bool:
        """
        Notify sender that transfer is complete

        Args:
            sender_phone: Sender's phone number
            transfer_reference: Transfer reference ID
            receiver_name: Name of receiver
            amount_zar: Amount transferred
            status: Transfer status (completed, failed, etc.)

        Returns:
            True if sent successfully
        """
        status_emoji = "✅" if status == "completed" else "❌"

        message = (
            f"{status_emoji} *Transfer {status.title()}*\n\n"
            f"Receiver: {receiver_name}\n"
            f"Amount: ZAR {amount_zar:.2f}\n"
            f"Reference: {transfer_reference}\n\n"
        )

        if status == "completed":
            message += "Payment has been delivered successfully!"
        else:
            message += (
                "We encountered an issue processing this transfer.\n"
                "Please contact support for assistance."
            )

        result = await self.send_whatsapp(sender_phone, message)
        return result is not None

    async def send_admin_alert(
        self, admin_phone: str, alert_type: str, details: str
    ) -> bool:
        """
        Send admin alert notification

        Args:
            admin_phone: Admin's phone number
            alert_type: Type of alert (error, warning, info)
            details: Alert details

        Returns:
            True if sent successfully
        """
        emoji_map = {
            "error": "🚨",
            "warning": "⚠️",
            "info": "ℹ️",
        }
        emoji = emoji_map.get(alert_type.lower(), "ℹ️")

        message = f"{emoji} *Admin Alert: {alert_type.upper()}*\n\n{details}"

        result = await self.send_whatsapp(admin_phone, message)
        return result is not None


# Singleton instance
_notification_service = None


def get_notification_service() -> NotificationService:
    """Get notification service instance"""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service
