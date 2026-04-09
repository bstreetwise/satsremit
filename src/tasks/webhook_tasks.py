"""
Webhook retry handling tasks.

Retries failed webhook deliveries with exponential backoff.
Can process both LND webhook retries and manual retry requests.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import and_

from src.core.celery import app
from src.core.database import get_db
from src.models import Webhook
from src.services.webhook import WebhookService

logger = logging.getLogger(__name__)


@app.task(
    name="src.tasks.webhook_tasks.retry_failed_webhooks",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def retry_failed_webhooks(self) -> Dict[str, Any]:
    """
    Auto-retry failed webhook deliveries every 5 minutes.
    
    Finds webhooks with status=FAILED and retry_count < max_retries.
    Attempts delivery again with exponential backoff.
    
    Returns:
        dict: Retry statistics
    """
    db = None
    try:
        db = next(get_db())
        webhook_service = WebhookService()
        
        stats = {
            "checked": 0,
            "retried": 0,
            "succeeded": 0,
            "still_failed": 0,
            "errors": 0,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        logger.info("🔄 Checking for failed webhooks to retry...")
        
        # Find failed webhooks eligible for retry
        max_retries = 5
        failed_webhooks = db.query(Webhook).filter(
            and_(
                Webhook.status == "FAILED",
                Webhook.retry_count < max_retries,
            )
        ).all()
        
        stats["checked"] = len(failed_webhooks)
        logger.info(f"Found {len(failed_webhooks)} failed webhooks to retry")
        
        for webhook in failed_webhooks:
            try:
                # Calculate backoff: 2^retry_count minutes
                backoff_minutes = 2 ** webhook.retry_count
                last_attempt = webhook.last_retry_at or webhook.created_at
                time_since_attempt = datetime.utcnow() - last_attempt
                
                if time_since_attempt < timedelta(minutes=backoff_minutes):
                    logger.debug(
                        f"Webhook {webhook.id} not ready for retry yet "
                        f"(backoff: {backoff_minutes}min)"
                    )
                    continue
                
                # Retry the webhook
                logger.info(
                    f"Retrying webhook {webhook.id} "
                    f"(attempt {webhook.retry_count + 1}/{max_retries})"
                )
                
                # Re-process the original payload
                result = webhook_service.retry_webhook(webhook.id, db)
                
                if result.get("success"):
                    webhook.status = "DELIVERED"
                    logger.info(f"✅ Webhook {webhook.id} delivered on retry")
                    stats["succeeded"] += 1
                else:
                    webhook.retry_count += 1
                    webhook.last_retry_at = datetime.utcnow()
                    
                    if webhook.retry_count >= max_retries:
                        webhook.status = "PERMANENTLY_FAILED"
                        logger.error(
                            f"❌ Webhook {webhook.id} failed after {max_retries} retries"
                        )
                    else:
                        logger.warning(
                            f"⚠️ Webhook {webhook.id} retry failed, "
                            f"will retry later"
                        )
                    
                    stats["still_failed"] += 1
                
                db.commit()
                stats["retried"] += 1
            
            except Exception as e:
                stats["errors"] += 1
                logger.error(
                    f"Error retrying webhook {webhook.id}: {str(e)}"
                )
        
        logger.info(
            f"📊 Webhook retry complete: "
            f"checked={stats['checked']}, "
            f"retried={stats['retried']}, "
            f"succeeded={stats['succeeded']}, "
            f"still_failed={stats['still_failed']}"
        )
        
        return stats
    
    except Exception as e:
        logger.error(
            f"❌ Webhook retry task failed: {str(e)}",
            exc_info=True,
        )
        
        try:
            raise self.retry(exc=e, countdown=60)
        except Exception:
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }
    
    finally:
        if db:
            db.close()


@app.task(
    name="src.tasks.webhook_tasks.retry_webhook",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def retry_webhook(self, webhook_id: str) -> Dict[str, Any]:
    """
    Retry a specific webhook delivery.
    
    Args:
        webhook_id: Webhook ID
    
    Returns:
        dict: Retry result
    """
    db = None
    try:
        db = next(get_db())
        webhook_service = WebhookService()
        
        webhook = db.query(Webhook).filter(
            Webhook.id == webhook_id
        ).first()
        
        if not webhook:
            logger.warning(f"Webhook {webhook_id} not found")
            return {"error": "Webhook not found"}
        
        # Attempt delivery
        result = webhook_service.retry_webhook(webhook_id, db)
        
        if result.get("success"):
            webhook.status = "DELIVERED"
            db.commit()
            logger.info(f"✅ Webhook {webhook_id} delivered")
            return result
        
        else:
            webhook.retry_count = (webhook.retry_count or 0) + 1
            webhook.last_retry_at = datetime.utcnow()
            
            if webhook.retry_count >= 5:
                webhook.status = "PERMANENTLY_FAILED"
            
            db.commit()
            logger.warning(f"Webhook {webhook_id} retry failed")
            
            try:
                return self.retry(exc=Exception(result.get("error")), countdown=60)
            except Exception:
                return result
    
    except Exception as e:
        logger.error(f"Error retrying webhook: {str(e)}")
        try:
            return self.retry(exc=e, countdown=30)
        except Exception:
            return {"error": str(e)}
    
    finally:
        if db:
            db.close()


@app.task(
    name="src.tasks.webhook_tasks.cleanup_old_webhooks",
    bind=True,
)
def cleanup_old_webhooks(self) -> Dict[str, Any]:
    """
    Clean up old webhook records (older than 90 days).
    
    Returns:
        dict: Cleanup statistics
    """
    db = None
    try:
        db = next(get_db())
        
        # Delete webhooks older than 90 days
        cutoff_date = datetime.utcnow() - timedelta(days=90)
        
        old_webhooks = db.query(Webhook).filter(
            Webhook.created_at < cutoff_date
        ).delete()
        
        db.commit()
        
        logger.info(f"✅ Deleted {old_webhooks} old webhook records")
        
        return {
            "deleted_count": old_webhooks,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    except Exception as e:
        logger.error(f"Error cleaning up webhooks: {str(e)}")
        return {"error": str(e)}
    
    finally:
        if db:
            db.close()


__all__ = [
    "retry_failed_webhooks",
    "retry_webhook",
    "cleanup_old_webhooks",
]
