"""
Settlement processing tasks.

Daily settlement processor that:
1. Aggregates verified transfers for each agent
2. Calculates fees and payout amounts
3. Creates settlement records
4. Initiates payouts via agent's preferred method
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from src.core.celery import app
from src.db.database import get_db
from src.models.models import Transfer, Settlement, Agent
from src.services.notification import NotificationService
from src.services.webhook import run_async

logger = logging.getLogger(__name__)


@app.task(
    name="src.tasks.settlement_tasks.process_daily_settlements",
    bind=True,
    max_retries=2,
)
def process_daily_settlements(self) -> Dict[str, Any]:
    """
    Process daily settlements for all agents.
    
    Runs daily at 2 AM UTC. For each agent with verified transfers:
    1. Sum verified transfers from last settlement
    2. Calculate fees (5% typical)
    3. Calculate net payout
    4. Create settlement record
    5. Initiate payout to agent
    6. Send notification to agent
    
    Returns:
        dict: Settlement statistics
    """
    db = None
    try:
        db = next(get_db())
        notification_service = NotificationService()
        
        stats = {
            "agents_processed": 0,
            "transfers_settled": 0,
            "total_amount_zar": Decimal("0.00"),
            "total_fees": Decimal("0.00"),
            "total_payouts": Decimal("0.00"),
            "errors": 0,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        logger.info("💰 Starting daily settlement processing...")
        
        # Get distinct agent IDs that have PAYOUT_EXECUTED transfers not yet settled
        agent_ids = [
            row[0]
            for row in db.query(Transfer.agent_id).filter(
                Transfer.state == "PAYOUT_EXECUTED",
            ).distinct().all()
        ]

        # Resolve agent records
        agents_with_verified = db.query(Agent).filter(
            Agent.id.in_(agent_ids)
        ).all()

        logger.info(f"Found {len(agents_with_verified)} agents with verified transfers")

        for agent_obj in agents_with_verified:
            agent_id = agent_obj.id
            agent_phone = agent_obj.phone
            agent_name = agent_obj.name
            try:
                # Get all payout-executed transfers for this agent not yet settled
                transfers = db.query(Transfer).filter(
                    and_(
                        Transfer.agent_id == agent_id,
                        Transfer.state == "PAYOUT_EXECUTED",
                    )
                ).all()
                
                if not transfers:
                    continue
                
                # Calculate totals
                total_amount = sum(
                    Decimal(str(t.amount_zar)) for t in transfers
                )
                
                # Fee: 5% (configurable)
                fee_rate = Decimal(os.getenv("SETTLEMENT_FEE_RATE", "0.05"))
                total_fees = total_amount * fee_rate
                payout_amount = total_amount - total_fees
                
                logger.info(
                    f"Processing settlement for {agent_name}: "
                    f"{len(transfers)} transfers, "
                    f"ZAR {total_amount:.2f} gross, "
                    f"ZAR {total_fees:.2f} fees"
                )
                
                # Create settlement record aligned with Settlement ORM model
                now = datetime.utcnow()
                week_start = now - timedelta(days=now.weekday())
                week_end = week_start + timedelta(days=6)
                settlement = Settlement(
                    agent_id=agent_id,
                    period_start=week_start.replace(hour=0, minute=0, second=0, microsecond=0),
                    period_end=week_end.replace(hour=23, minute=59, second=59, microsecond=0),
                    amount_zar_owed=total_amount,
                    amount_zar_paid=Decimal("0.00"),
                    commission_sats_earned=0,
                    status="PENDING",
                )
                
                db.add(settlement)
                db.flush()  # Get settlement ID
                
                # Link transfers to settlement
                for transfer in transfers:
                    transfer.settlement_id = settlement.id
                    transfer.state = "SETTLED"
                
                db.commit()
                
                stats["agents_processed"] += 1
                stats["transfers_settled"] += len(transfers)
                stats["total_amount_zar"] = str(
                    Decimal(str(stats["total_amount_zar"])) + total_amount
                )
                stats["total_fees"] = str(
                    Decimal(str(stats["total_fees"])) + total_fees
                )
                stats["total_payouts"] = str(
                    Decimal(str(stats["total_payouts"])) + payout_amount
                )
                
                # Send settlement notification — run_async() is safe in a
                # Celery prefork worker (no running event loop in that process).
                try:
                    run_async(notification_service.send_whatsapp(
                        phone_number=agent_phone,
                        message=(
                            f"Settlement processed: ZAR {payout_amount:.2f} "
                            f"({len(transfers)} transfers). "
                            f"Fees: ZAR {total_fees:.2f}. "
                            f"Settlement ID: {settlement.id}"
                        ),
                    ))
                    logger.info(
                        f"Settlement {settlement.id} created and notified for {agent_name}"
                    )

                except Exception as e:
                    logger.error(f"Failed to notify agent: {str(e)}")
            
            except Exception as e:
                stats["errors"] += 1
                logger.error(
                    f"Error processing settlement for agent {agent_id}: {str(e)}"
                )
        
        logger.info(
            f"📊 Settlement processing complete: "
            f"agents={stats['agents_processed']}, "
            f"transfers={stats['transfers_settled']}, "
            f"payout=ZAR {stats['total_payouts']}"
        )
        
        return stats
    
    except Exception as e:
        logger.error(
            f"❌ Settlement processing failed: {str(e)}",
            exc_info=True,
        )
        
        try:
            raise self.retry(exc=e, countdown=300)
        except Exception:
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }
    
    finally:
        if db:
            db.close()


@app.task(
    name="src.tasks.settlement_tasks.initiate_agent_payout",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def initiate_agent_payout(self, settlement_id: str) -> Dict[str, Any]:
    """
    Initiate payout to agent for a settlement.
    
    Args:
        settlement_id: Settlement ID
    
    Returns:
        dict: Payout initiation result
    """
    db = None
    try:
        db = next(get_db())
        
        settlement = db.query(Settlement).filter(
            Settlement.id == settlement_id
        ).first()
        
        if not settlement:
            logger.warning(f"Settlement {settlement_id} not found")
            return {
                "error": "Settlement not found",
            }
        
        # Get agent info
        agent = db.query(Agent).filter(
            Agent.id == settlement.agent_id
        ).first()
        
        if not agent:
            return {"error": "Agent not found"}
        
        # Initiate payout (via bank transfer, mobile money, etc.)
        # This is a placeholder - actual implementation depends on payment method
        logger.info(
            f"💳 Initiating payout for settlement {settlement_id}: "
            f"ZAR {settlement.payout_amount_zar:.2f} to {agent.name}"
        )
        
        settlement.status = "PROCESSING"
        settlement.payout_initiated_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"✅ Payout initiated for settlement {settlement_id}")
        
        return {
            "success": True,
            "settlement_id": settlement_id,
            "payout_amount": str(settlement.payout_amount_zar),
        }
    
    except Exception as e:
        logger.error(f"Error initiating payout: {str(e)}")
        try:
            return self.retry(exc=e, countdown=60)
        except Exception:
            return {"error": str(e)}
    
    finally:
        if db:
            db.close()


@app.task(
    name="src.tasks.settlement_tasks.confirm_agent_payout",
    bind=True,
)
def confirm_agent_payout(
    self,
    settlement_id: str,
    payout_ref: str,
) -> Dict[str, Any]:
    """
    Confirm successful agent payout.
    
    Args:
        settlement_id: Settlement ID
        payout_ref: Reference from payment processor
    
    Returns:
        dict: Confirmation result
    """
    db = None
    try:
        db = next(get_db())
        notification_service = NotificationService()
        
        settlement = db.query(Settlement).filter(
            Settlement.id == settlement_id
        ).first()
        
        if not settlement:
            return {"error": "Settlement not found"}
        
        settlement.status = "COMPLETED"
        settlement.payout_completed_at = datetime.utcnow()
        settlement.payout_reference = payout_ref
        db.commit()
        
        # Mark transfers as COMPLETED
        transfers = db.query(Transfer).filter(
            Transfer.settlement_id == settlement_id
        ).all()
        
        for transfer in transfers:
            transfer.state = "COMPLETED"
        
        db.commit()
        
        logger.info(
            f"✅ Settlement {settlement_id} marked as COMPLETED "
            f"(reference: {payout_ref})"
        )
        
        return {
            "success": True,
            "settlement_id": settlement_id,
            "payout_ref": payout_ref,
        }
    
    except Exception as e:
        logger.error(f"Error confirming payout: {str(e)}")
        return {"error": str(e)}
    
    finally:
        if db:
            db.close()


__all__ = [
    "process_daily_settlements",
    "initiate_agent_payout",
    "confirm_agent_payout",
]
