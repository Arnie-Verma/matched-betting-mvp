# apps/api/src/api/routers/stripe_webhooks.py
"""Stripe webhook handlers with idempotency"""
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
import stripe

from api.core.database import get_db
from api.models import User, WebhookEvent
from api.services.stripe_service import StripeService
from api.services.subscription_service import SubscriptionService


router = APIRouter(prefix="/webhooks/stripe", tags=["stripe-webhooks"])


@router.post("/")
async def handle_stripe_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle Stripe webhook events with idempotency"""
    stripe_service = StripeService()
    subscription_service = SubscriptionService()

    # Get raw payload
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing stripe-signature header")

    try:
        # Construct and verify the event
        event = stripe_service.construct_webhook_event(payload, sig_header)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Check for idempotency - have we already processed this event?
    existing_event = (
        db.query(WebhookEvent)
        .filter(WebhookEvent.stripe_event_id == event["id"])
        .first()
    )

    if existing_event:
        if existing_event.processed:
            return {"status": "already_processed"}
        else:
            # Event exists but wasn't processed successfully, increment retry count
            existing_event.retry_count += 1
            webhook_event = existing_event
    else:
        # Create new webhook event record
        webhook_event = WebhookEvent(
            stripe_event_id=event["id"],
            event_type=event["type"],
            stripe_api_version=event.get("api_version"),
            event_data=event["data"]
        )
        db.add(webhook_event)
        db.commit()
        db.refresh(webhook_event)

    try:
        # Process the event based on type
        event_type = event["type"]
        event_data = event["data"]["object"]

        if event_type == "customer.subscription.created":
            await handle_subscription_created(db, event_data, subscription_service)

        elif event_type == "customer.subscription.updated":
            await handle_subscription_updated(db, event_data, subscription_service)

        elif event_type == "customer.subscription.deleted":
            await handle_subscription_deleted(db, event_data, subscription_service)

        elif event_type == "invoice.payment_succeeded":
            await handle_payment_succeeded(db, event_data, subscription_service)

        elif event_type == "invoice.payment_failed":
            await handle_payment_failed(db, event_data, subscription_service)

        elif event_type == "customer.subscription.trial_will_end":
            await handle_trial_will_end(db, event_data, subscription_service)

        else:
            # Log unhandled event types but don't fail
            print(f"Unhandled webhook event type: {event_type}")

        # Mark event as processed
        webhook_event.processed = True
        webhook_event.processed_at = datetime.now(timezone.utc)
        webhook_event.error_message = None
        db.commit()

        return {"status": "success", "event_type": event_type}

    except Exception as e:
        # Mark event as failed
        webhook_event.processed = False
        webhook_event.error_message = str(e)
        db.commit()

        # Log the error
        print(f"Error processing webhook {event['id']} ({event_type}): {str(e)}")

        # Return success to Stripe to avoid retries for application errors
        # (we've logged the error and can investigate)
        return {"status": "error", "message": str(e)}


async def handle_subscription_created(
    db: Session,
    subscription_data: dict,
    subscription_service: SubscriptionService
):
    """Handle subscription creation"""
    stripe_customer_id = subscription_data["customer"]

    # Find user by stripe customer ID
    user = (
        db.query(User)
        .filter(User.stripe_customer_id == stripe_customer_id)
        .first()
    )

    if not user:
        raise Exception(f"User not found for Stripe customer {stripe_customer_id}")

    # Create Stripe subscription object for processing
    stripe_subscription = stripe.Subscription.construct_from(
        subscription_data, stripe.api_key
    )

    subscription_service.create_subscription_from_stripe(
        db, stripe_subscription, user.id
    )


async def handle_subscription_updated(
    db: Session,
    subscription_data: dict,
    subscription_service: SubscriptionService
):
    """Handle subscription updates"""
    stripe_subscription = stripe.Subscription.construct_from(
        subscription_data, stripe.api_key
    )

    subscription_service.update_subscription_from_stripe(db, stripe_subscription)


async def handle_subscription_deleted(
    db: Session,
    subscription_data: dict,
    subscription_service: SubscriptionService
):
    """Handle subscription deletion"""
    subscription_id = subscription_data["id"]
    subscription_service.handle_subscription_deleted(db, subscription_id)


async def handle_payment_succeeded(
    db: Session,
    invoice_data: dict,
    subscription_service: SubscriptionService
):
    """Handle successful payment"""
    subscription_id = invoice_data.get("subscription")

    if subscription_id:
        # Refresh subscription data from Stripe
        stripe_subscription = stripe.Subscription.retrieve(subscription_id)
        subscription_service.update_subscription_from_stripe(db, stripe_subscription)


async def handle_payment_failed(
    db: Session,
    invoice_data: dict,
    subscription_service: SubscriptionService
):
    """Handle failed payment"""
    subscription_id = invoice_data.get("subscription")

    if subscription_id:
        # Update subscription status
        stripe_subscription = stripe.Subscription.retrieve(subscription_id)
        subscription = subscription_service.update_subscription_from_stripe(db, stripe_subscription)

        if subscription and subscription.user:
            # Could implement email notifications here
            print(f"Payment failed for user {subscription.user.email}")


async def handle_trial_will_end(
    db: Session,
    subscription_data: dict,
    subscription_service: SubscriptionService
):
    """Handle trial ending soon"""
    subscription_id = subscription_data["id"]

    # Find the subscription
    from api.models import Subscription
    subscription = (
        db.query(Subscription)
        .filter(Subscription.stripe_subscription_id == subscription_id)
        .first()
    )

    if subscription and subscription.user:
        # Could implement trial ending email notifications here
        print(f"Trial ending soon for user {subscription.user.email}")