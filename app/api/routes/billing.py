import logging
import stripe
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel

from app.services.auth_service import AuthService, get_current_user
from app.core.config import get_settings

router = APIRouter()
logger = logging.getLogger(__name__)
settings = get_settings()
stripe.api_key = settings.stripe_secret_key

# Plan definitions — change prices to match your Stripe dashboard
PLANS = {
    "pro": {
        "name": "Pro Plan",
        "price_id": "price_your_pro_price_id_here",  # from Stripe dashboard
        "price": "₹999/month",
        "features": ["Unlimited messages", "5 PDFs", "Priority support"],
    },
    "business": {
        "name": "Business Plan",
        "price_id": "price_your_business_price_id_here",
        "price": "₹2999/month",
        "features": ["Unlimited messages", "Unlimited PDFs", "Dedicated support"],
    },
}


class CheckoutRequest(BaseModel):
    plan: str  # "pro" or "business"
    success_url: str
    cancel_url: str


@router.get("/billing/plans")
async def get_plans():
    """Returns available subscription plans."""
    return PLANS


@router.post("/billing/checkout")
async def create_checkout(
    request: CheckoutRequest,
    user=Depends(get_current_user),
):
    """
    Creates a Stripe checkout session.
    The user is redirected to Stripe's hosted payment page.
    After payment, Stripe calls /billing/webhook to confirm.
    """
    if request.plan not in PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan.")

    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=503,
            detail="Billing not configured yet. Contact support."
        )

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price": PLANS[request.plan]["price_id"],
                "quantity": 1,
            }],
            mode="subscription",
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            metadata={
                "email": user["sub"],
                "plan": request.plan,
            },
        )
        return {"checkout_url": session.url}

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/billing/webhook")
async def stripe_webhook(request: Request):
    """
    Stripe calls this after a successful payment.
    We upgrade the user's plan here.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        email = session["metadata"]["email"]
        plan = session["metadata"]["plan"]

        auth_service = AuthService()
        auth_service.upgrade_plan(email, plan)
        logger.info(f"Upgraded {email} to {plan} via Stripe")

    return {"status": "ok"}