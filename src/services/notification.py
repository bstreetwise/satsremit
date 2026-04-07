"""
Notification service using Africa's Talking SMS
"""
import httpx
import logging
from typing import Optional
from src.core.config import get_settings

logger = logging.getLogger(__name__)


class NotificationService:
    """Send notifications via Africa's Talking SMS API"""
    
    BASE_URL = "https://api.sandbox.africastalking.com/version1/messaging"
    
    def __init__(self):
        self.settings = get_settings()
        self.api_key = self.settings.africas_talking_api_key
        self.username = self.settings.africas_talking_username
        self.shortcode = self.settings.africas_talking_shortcode
    
    async def send_sms(
        self,
        phone_number: str,
        message: str,
        sender_id: Optional[str] = None,
    ) -> bool:
        """
        Send SMS via Africa's Talking
        
        Args:
            phone_number: Recipient phone (e.g., +263712345678)
            message: SMS message text
            sender_id: Custom sender ID or shortcode (optional)
        
        Returns:
            True if delivery successful, False otherwise
        """
        try:
            sender = sender_id or self.shortcode or self.username
            
            headers = {
                "ApiKey": self.api_key,
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            }
            
            payload = {
                "username": self.username,
                "to": phone_number,
                "message": message,
                "from": sender,
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/send",
                    data=payload,
                    headers=headers,
                    timeout=10,
                )
                
                if response.status_code == 200:
                    result = response.json()
                    # Check Africa's Talking response
                    if result.get("SMSMessageData", {}).get("Message") == "Sent":
                        logger.info(f"SMS sent to {phone_number}")
                        return True
                    else:
                        logger.error(
                            f"SMS delivery failed for {phone_number}: "
                            f"{result.get('SMSMessageData', {}).get('Message')}"
                        )
                        return False
                else:
                    logger.error(
                        f"Africa's Talking API error {response.status_code}: "
                        f"{response.text}"
                    )
                    return False
        
        except Exception as e:
            logger.error(f"Failed to send SMS to {phone_number}: {str(e)}")
            return False
    
    async def send_pin_to_receiver(
        self,
        phone_number: str,
        pin: str,
        transfer_reference: str,
        amount_zar: float,
    ) -> bool:
        """
        Send PIN notification to receiver
        
        Args:
            phone_number: Receiver phone
            pin: 4-digit PIN
            transfer_reference: Transfer reference (e.g., REF-XXXXX)
            amount_zar: Amount in ZAR
        
        Returns:
            True if delivery successful
        """
        message = (
            f"SatsRemit Transfer\n"
            f"PIN: {pin}\n"
            f"Amount: {amount_zar:.2f} ZAR\n"
            f"Ref: {transfer_reference}\n"
            f"Valid for 5 minutes"
        )
        
        return await self.send_sms(phone_number, message)
    
    async def notify_agent_pending_transfer(
        self,
        agent_phone: str,
        transfer_reference: str,
        receiver_name: str,
        amount_zar: float,
    ) -> bool:
        """
        Alert agent of pending transfer verification
        
        Args:
            agent_phone: Agent phone number
            transfer_reference: Transfer reference
            receiver_name: Receiver name
            amount_zar: Amount in ZAR
        
        Returns:
            True if delivery successful
        """
        message = (
            f"New Transfer Alert\n"
            f"Ref: {transfer_reference}\n"
            f"To: {receiver_name}\n"
            f"Amount: {amount_zar:.2f} ZAR\n"
            f"Action: Verify receiver"
        )
        
        return await self.send_sms(agent_phone, message)
    
    async def notify_sender_completion(
        self,
        sender_phone: str,
        transfer_reference: str,
        receiver_name: str,
        amount_zar: float,
    ) -> bool:
        """
        Notify sender that transfer is complete
        
        Args:
            sender_phone: Sender phone number
            transfer_reference: Transfer reference
            receiver_name: Receiver name
            amount_zar: Amount in ZAR
        
        Returns:
            True if delivery successful
        """
        message = (
            f"Transfer Complete\n"
            f"Ref: {transfer_reference}\n"
            f"To: {receiver_name}\n"
            f"Amount: {amount_zar:.2f} ZAR\n"
            f"Status: Funds delivered"
        )
        
        return await self.send_sms(sender_phone, message)


# Singleton instance
_notification_service = None


def get_notification_service() -> NotificationService:
    """Get notification service instance"""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service
