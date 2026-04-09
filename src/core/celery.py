"""
Celery configuration and initialization for background task processing.

This module sets up Celery for asynchronous task execution, including:
- Invoice payment monitoring (polling LND every 30 seconds)
- Verification timeout handling (auto-refund expiring transfers)
- Settlement processing (weekly calculations)
- Webhook retry logic (failed delivery recovery)
"""

import os
from celery import Celery
from celery.schedules import crontab
from kombu import Exchange, Queue

# Initialize Celery app
app = Celery("satsremit")

# Configure from settings
app.conf.update(
    # Broker configuration
    broker_url=os.getenv(
        "CELERY_BROKER_URL",
        "redis://localhost:6379/0"
    ),
    result_backend=os.getenv(
        "CELERY_RESULT_BACKEND",
        "redis://localhost:6379/1"
    ),
    
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Task routing
    task_routes={
        "src.tasks.invoice_tasks.*": {"queue": "invoices"},
        "src.tasks.settlement_tasks.*": {"queue": "settlements"},
        "src.tasks.verification_tasks.*": {"queue": "verification"},
        "src.tasks.webhook_tasks.*": {"queue": "webhooks"},
    },
    
    # Queue configuration
    task_queues=(
        Queue(
            "invoices",
            Exchange("invoices", type="direct"),
            routing_key="invoice",
            priority=10,
        ),
        Queue(
            "settlements",
            Exchange("settlements", type="direct"),
            routing_key="settlement",
            priority=5,
        ),
        Queue(
            "verification",
            Exchange("verification", type="direct"),
            routing_key="verification",
            priority=8,
        ),
        Queue(
            "webhooks",
            Exchange("webhooks", type="direct"),
            routing_key="webhook",
            priority=9,
        ),
    ),
    
    # Task execution settings
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    task_max_retries=3,
    task_default_retry_delay=60,  # Retry after 60 seconds
    
    # Beat schedule (periodic tasks)
    beat_schedule={
        # Invoice payment monitoring - every 30 seconds
        "monitor-invoice-payments": {
            "task": "src.tasks.invoice_tasks.monitor_lnd_invoices",
            "schedule": 30.0,  # Every 30 seconds
            "options": {
                "queue": "invoices",
                "priority": 10,
            },
        },
        
        # Verification timeout handler - every 1 minute
        "verify-timeout-handler": {
            "task": "src.tasks.verification_tasks.handle_verification_timeouts",
            "schedule": 60.0,  # Every 60 seconds
            "options": {
                "queue": "verification",
                "priority": 8,
            },
        },
        
        # Settlement processor - daily at 2 AM UTC
        "process-settlements": {
            "task": "src.tasks.settlement_tasks.process_daily_settlements",
            "schedule": crontab(hour=2, minute=0),
            "options": {
                "queue": "settlements",
                "priority": 5,
            },
        },
        
        # Webhook retry handler - every 5 minutes
        "retry-failed-webhooks": {
            "task": "src.tasks.webhook_tasks.retry_failed_webhooks",
            "schedule": 300.0,  # Every 5 minutes
            "options": {
                "queue": "webhooks",
                "priority": 9,
            },
        },
    },
)


# Auto-discover tasks from all registered apps
app.autodiscover_tasks(["src.tasks"])


@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery setup."""
    print(f"Request: {self.request!r}")


__all__ = ["app"]
