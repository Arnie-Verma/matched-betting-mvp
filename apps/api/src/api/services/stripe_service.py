# apps/api/src/api/services/stripe_service.py
"""Stripe service for managing products, prices, and subscriptions"""
import os
from typing import Optional, Dict, Any, List
import stripe
from sqlalchemy.orm import Session
from api.models import Plan, Subscription, User, WebhookEvent


class StripeService:
    """Service for interacting with Stripe API"""

    def __init__(self):
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        self.webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    def create_or_update_products_and_prices(self, db: Session) -> Dict[str, Any]:
        """Create/update Stripe products and prices for all plans"""
        results = {"created": [], "updated": [], "errors": []}

        plans = db.query(Plan).filter(Plan.is_active == True).all()

        for plan in plans:
            try:
                # Skip free plan
                if plan.name == "free":
                    continue

                # Create or update product
                product_data = {
                    "name": plan.display_name,
                    "description": plan.description,
                    "metadata": {"plan_name": plan.name}
                }

                if plan.stripe_product_id:
                    # Update existing product
                    product = stripe.Product.modify(
                        plan.stripe_product_id,
                        **product_data
                    )
                    results["updated"].append(f"Product {product.id}")
                else:
                    # Create new product
                    product = stripe.Product.create(**product_data)
                    plan.stripe_product_id = product.id
                    results["created"].append(f"Product {product.id}")

                # Create or update monthly price
                if plan.price_monthly_cents:
                    monthly_price_data = {
                        "currency": "aud",
                        "product": product.id,
                        "unit_amount": plan.price_monthly_cents,
                        "recurring": {"interval": "month"},
                        "metadata": {
                            "plan_name": plan.name,
                            "billing_cycle": "monthly"
                        }
                    }

                    if plan.stripe_price_monthly_id:
                        # For existing prices, we need to create a new one (Stripe doesn't allow price updates)
                        # We'll deactivate the old one and create a new one
                        try:
                            stripe.Price.modify(
                                plan.stripe_price_monthly_id,
                                active=False
                            )
                        except stripe.error.StripeError:
                            pass  # Price might not exist or already inactive

                    monthly_price = stripe.Price.create(**monthly_price_data)
                    plan.stripe_price_monthly_id = monthly_price.id
                    results["created"].append(f"Monthly price {monthly_price.id}")

                # Create or update yearly price
                if plan.price_yearly_cents:
                    yearly_price_data = {
                        "currency": "aud",
                        "product": product.id,
                        "unit_amount": plan.price_yearly_cents,
                        "recurring": {"interval": "year"},
                        "metadata": {
                            "plan_name": plan.name,
                            "billing_cycle": "yearly"
                        }
                    }

                    if plan.stripe_price_yearly_id:
                        # Deactivate old price
                        try:
                            stripe.Price.modify(
                                plan.stripe_price_yearly_id,
                                active=False
                            )
                        except stripe.error.StripeError:
                            pass

                    yearly_price = stripe.Price.create(**yearly_price_data)
                    plan.stripe_price_yearly_id = yearly_price.id
                    results["created"].append(f"Yearly price {yearly_price.id}")

            except stripe.error.StripeError as e:
                error_msg = f"Stripe error for plan {plan.name}: {str(e)}"
                results["errors"].append(error_msg)
            except Exception as e:
                error_msg = f"General error for plan {plan.name}: {str(e)}"
                results["errors"].append(error_msg)

        # Commit changes to database
        db.commit()
        return results

    def create_customer(self, user: User, email: str) -> stripe.Customer:
        """Create a Stripe customer for a user"""
        customer = stripe.Customer.create(
            email=email,
            metadata={
                "user_id": str(user.id),
                "clerk_user_id": user.clerk_user_id
            }
        )
        return customer

    def create_checkout_session(
        self,
        user: User,
        price_id: str,
        success_url: str,
        cancel_url: str,
        plan_name: Optional[str] = None
    ) -> stripe.checkout.Session:
        """Create a Stripe checkout session for subscription"""
        # Ensure user has a Stripe customer ID
        if not user.stripe_customer_id:
            customer = self.create_customer(user, user.email)
            user.stripe_customer_id = customer.id

        session_data = {
            "customer": user.stripe_customer_id,
            "payment_method_types": ["card"],
            "line_items": [{
                "price": price_id,
                "quantity": 1,
            }],
            "mode": "subscription",
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": {
                "user_id": str(user.id),
                "clerk_user_id": user.clerk_user_id
            },
            "automatic_tax": {"enabled": True},  # Enable automatic tax calculation
            "customer_update": {
                "address": "auto",  # Automatically collect and save customer address for tax calculation
                "name": "auto"      # Automatically collect and save customer name for tax ID collection
            },
            "tax_id_collection": {"enabled": True},  # Allow customers to provide tax IDs
            "allow_promotion_codes": True,  # Show promotion code field in Checkout
        }

        if plan_name:
            session_data["subscription_data"] = {
                "metadata": {"plan_name": plan_name.lower()}
            }

        # No trial periods

        session = stripe.checkout.Session.create(**session_data)
        return session

    def create_customer_portal_session(
        self,
        customer_id: str,
        return_url: str
    ) -> stripe.billing_portal.Session:
        """Create a customer portal session for managing subscription"""
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )
        return session

    def get_subscription(self, stripe_subscription_id: str) -> stripe.Subscription:
        """Retrieve a subscription from Stripe"""
        return stripe.Subscription.retrieve(stripe_subscription_id)

    def cancel_subscription(
        self,
        stripe_subscription_id: str,
        at_period_end: bool = True
    ) -> stripe.Subscription:
        """Cancel a subscription"""
        if at_period_end:
            return stripe.Subscription.modify(
                stripe_subscription_id,
                cancel_at_period_end=True
            )
        else:
            return stripe.Subscription.delete(stripe_subscription_id)

    def construct_webhook_event(
        self,
        payload: bytes,
        sig_header: str
    ) -> stripe.Event:
        """Construct and verify a webhook event"""
        return stripe.Webhook.construct_event(
            payload, sig_header, self.webhook_secret
        )
