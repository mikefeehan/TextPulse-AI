"""
Stripe Checkout integration for per-read payments.

Flow:
    1. Frontend calls POST /contacts/{id}/analysis/checkout
    2. Backend creates a Stripe Checkout Session with the tier price
    3. Returns the checkout URL → frontend redirects to Stripe
    4. User pays → Stripe sends webhook → backend queues analysis
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.contacts import _get_contact_or_404
from app.core.config import get_settings
from app.db.session import get_db
from app.models import User
from app.services.analysis_engine import get_pricing_tier, scan_conversation

log = logging.getLogger(__name__)
router = APIRouter()


@router.post("/{contact_id}/analysis/checkout")
def create_checkout_session(
    contact_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    Create a Stripe Checkout Session for the full analysis read.
    Returns the checkout URL for the frontend to redirect to.
    """
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment processing is not configured yet.",
        )

    contact = _get_contact_or_404(db, current_user.id, contact_id)
    scan = scan_conversation(db, contact)
    tier = scan["tier"]

    try:
        import stripe
        stripe.api_key = settings.stripe_secret_key

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "unit_amount": tier["price_usd"] * 100,  # cents
                        "product_data": {
                            "name": f"TextPulse {tier['label']} Read — {contact.name}",
                            "description": f"Full AI relationship analysis of {scan['message_count']:,} messages over {scan.get('duration_days', 0)} days.",
                        },
                    },
                    "quantity": 1,
                }
            ],
            mode="payment",
            success_url=settings.stripe_success_url.format(contact_id=contact_id),
            cancel_url=settings.stripe_cancel_url.format(contact_id=contact_id),
            metadata={
                "contact_id": contact_id,
                "user_id": current_user.id,
                "tier": tier["name"],
            },
        )
        return {"checkout_url": session.url, "tier": tier}
    except Exception as exc:
        log.exception("Stripe checkout creation failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to create payment session.",
        ) from exc


@router.post("/stripe/webhook")
async def stripe_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict:
    """
    Handle Stripe webhook events. On successful payment, queue the
    full windowed analysis pipeline.
    """
    settings = get_settings()
    if not settings.stripe_secret_key or not settings.stripe_webhook_secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        import stripe
        stripe.api_key = settings.stripe_secret_key
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature.") from exc

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        contact_id = session.get("metadata", {}).get("contact_id")
        if contact_id:
            from app.api.routes.analysis import _run_analysis_job
            background_tasks.add_task(_run_analysis_job, contact_id)
            log.info("Payment completed for contact %s, analysis queued.", contact_id)

    return {"received": True}
