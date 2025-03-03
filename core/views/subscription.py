from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings
from django.utils import timezone
from django.urls import reverse
import json
import hmac
import hashlib
import uuid
from ..models.subscription import Subscription, SubscriptionPlan
from ..services.subscription import SubscriptionService
from ..services.payments import PaymentService
import logging

logger = logging.getLogger(__name__)

@login_required
def subscription_plans(request):
    """View subscription plans"""
    # Get subscription plans from database
    subscription_plans = SubscriptionPlan.objects.filter(is_active=True)
    plans = {}
    
    # Map subscription plans to template format
    for plan in subscription_plans:
        if plan.tier == Subscription.Tier.FREE:
            key = 'free'
        elif plan.tier == Subscription.Tier.DEV_PRO:
            key = 'developer'
        elif plan.tier == Subscription.Tier.INV_PRO:
            key = 'investor'
        else:
            continue
            
        plans[key] = {
            'tier': plan.tier,
            'name': plan.name,
            'price': plan.price,
            'features': plan.features
        }
    
    # Ensure all required plans exist
    if 'free' not in plans:
        plans['free'] = {
            'tier': Subscription.Tier.FREE,
            'name': 'Free Plan',
            'price': 0,
            'features': SubscriptionService.get_tier_features(Subscription.Tier.FREE)['features']
        }
    if 'developer' not in plans:
        plans['developer'] = {
            'tier': Subscription.Tier.DEV_PRO,
            'name': 'Developer Pro',
            'price': 5000,  # Default price if no plan exists
            'features': SubscriptionService.get_tier_features(Subscription.Tier.DEV_PRO)['features']
        }
    if 'investor' not in plans:
        plans['investor'] = {
            'tier': Subscription.Tier.INV_PRO,
            'name': 'Investor Pro',
            'price': 10000,  # Default price if no plan exists
            'features': SubscriptionService.get_tier_features(Subscription.Tier.INV_PRO)['features']
        }
    
    context = {
        'current_subscription': request.user.subscription if hasattr(request.user, 'subscription') else None,
        'plans': plans
    }
    return render(request, 'core/subscription/plans.html', context)

@login_required
def payment_page(request):
    """Display payment form for subscription"""
    if request.method != 'POST':
        return redirect('core:subscription_plans')
    
    tier = request.POST.get('tier')
    if not tier:
        messages.error(request, 'Please select a subscription plan.')
        return redirect('core:subscription_plans')
    
    try:
        # Get plan from database
        plan = SubscriptionPlan.objects.get(tier=tier, is_active=True)
        subscription_plan = {
            'tier': plan.tier,
            'name': plan.name,
            'price': plan.price,
            'features': plan.features
        }
    except SubscriptionPlan.DoesNotExist:
        # Fallback to default plans if not found in database
        plans = {
            Subscription.Tier.FREE: {
                'tier': Subscription.Tier.FREE,
                'name': 'Free Plan',
                'price': 0,
                'features': SubscriptionService.get_tier_features(Subscription.Tier.FREE)['features']
            },
            Subscription.Tier.DEV_PRO: {
                'tier': Subscription.Tier.DEV_PRO,
                'name': 'Developer Pro',
                'price': 5000,
                'features': SubscriptionService.get_tier_features(Subscription.Tier.DEV_PRO)['features']
            },
            Subscription.Tier.INV_PRO: {
                'tier': Subscription.Tier.INV_PRO,
                'name': 'Investor Pro',
                'price': 10000,
                'features': SubscriptionService.get_tier_features(Subscription.Tier.INV_PRO)['features']
            }
        }
        subscription_plan = plans.get(tier)
    
    if not subscription_plan:
        messages.error(request, 'Invalid subscription plan selected.')
        return redirect('core:subscription_plans')
    
    # Don't process payment for free plan
    if tier == Subscription.Tier.FREE:
        result = SubscriptionService.upgrade_subscription(
            user=request.user,
            new_tier=tier
        )
        if result.get('success'):
            messages.success(request, 'Successfully switched to Free plan.')
            return redirect('core:dashboard')
        else:
            messages.error(request, f"Plan change failed: {result.get('error')}")
            return redirect('core:subscription_plans')
    
    # Generate payment reference for paid plans
    payment_reference = f"sub_{request.user.id}_{uuid.uuid4().hex[:8]}"
    
    context = {
        'subscription_plan': subscription_plan,
        'payment_reference': payment_reference,
        'paystack_public_key': settings.PAYSTACK_PUBLIC_KEY
    }
    return render(request, 'core/subscription/payment.html', context)

@login_required
@require_POST
def verify_payment(request):
    """Verify payment and update subscription"""
    reference = request.POST.get('reference')
    tier = request.POST.get('tier')
    
    if not reference or not tier:
        return JsonResponse({
            'status': 'error',
            'message': 'Missing payment reference or subscription tier'
        }, status=400)
    
    # Verify payment with Paystack
    verification = PaymentService.verify_subscription_payment(reference)
    
    if verification.get('success'):
        # Verify user ID in metadata matches current user
        if str(verification.get('user_id')) != str(request.user.id):
            logger.error(f"User ID mismatch: {verification.get('user_id')} != {request.user.id}")
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid payment verification'
            }, status=400)
        
        # Verify tier matches
        if verification.get('plan') != tier:
            logger.error(f"Tier mismatch: {verification.get('plan')} != {tier}")
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid subscription tier'
            }, status=400)
        
        # Upgrade subscription
        result = SubscriptionService.upgrade_subscription(
            user=request.user,
            new_tier=tier,
            payment_method='paystack',
            payment_reference=reference
        )
        
        if result.get('success'):
            return JsonResponse({
                'status': 'success',
                'message': 'Subscription upgraded successfully',
                'redirect_url': reverse('core:dashboard')
            })
        else:
            logger.error(f"Subscription upgrade failed: {result.get('error')}")
            return JsonResponse({
                'status': 'error',
                'message': f"Subscription upgrade failed: {result.get('error')}"
            }, status=400)
    else:
        logger.error(f"Payment verification failed: {verification.get('error')}")
        return JsonResponse({
            'status': 'error',
            'message': 'Payment verification failed. Please contact support.'
        }, status=400)

@login_required
def process_payment(request):
    """Process the payment response from Paystack"""
    if request.method != 'POST':
        return redirect('core:subscription_plans')
    
    plan = request.POST.get('plan')
    payment_reference = request.POST.get('payment_reference')
    
    if not plan or not payment_reference:
        messages.error(request, 'Invalid payment data.')
        return redirect('core:subscription_plans')
    
    # Verify payment with Paystack
    verification = PaymentService.verify_subscription_payment(payment_reference)
    
    if verification.get('success'):
        # Verify user ID in metadata matches current user
        if str(verification.get('user_id')) != str(request.user.id):
            messages.error(request, 'Invalid payment verification.')
            return redirect('core:subscription_plans')
        
        # Upgrade subscription
        result = SubscriptionService.upgrade_subscription(
            user=request.user,
            new_tier=plan,
            payment_method='paystack',
            payment_reference=payment_reference
        )
        
        if result.get('success'):
            messages.success(request, 'Subscription upgraded successfully!')
            return redirect('core:dashboard')
        else:
            messages.error(request, f"Subscription upgrade failed: {result.get('error')}")
    else:
        messages.error(request, 'Payment verification failed. Please try again.')
    
    return redirect('core:subscription_plans')

@login_required
def upgrade_subscription(request):
    """Handle subscription upgrade"""
    if request.method != 'POST':
        return redirect('core:subscription_plans')
    
    new_tier = request.POST.get('tier')
    
    if not new_tier or new_tier not in [choice[0] for choice in Subscription.Tier.choices]:
        messages.error(request, 'Invalid subscription tier selected.')
        return redirect('core:subscription_plans')
    
    # If upgrading to free plan, process directly
    if new_tier == Subscription.Tier.FREE:
        result = SubscriptionService.upgrade_subscription(
            user=request.user,
            new_tier=new_tier
        )
        
        if result.get('success'):
            messages.success(request, 'Successfully switched to Free plan.')
            return redirect('core:dashboard')
        else:
            messages.error(request, f"Plan change failed: {result.get('error')}")
            return redirect('core:subscription_plans')
    
    # For paid plans, get plan details and create payment
    try:
        # Get plan from database
        plan = SubscriptionPlan.objects.get(tier=new_tier, is_active=True)
        plan_details = {
            'tier': plan.tier,
            'name': plan.name,
            'price': plan.price,
            'features': plan.features
        }
    except SubscriptionPlan.DoesNotExist:
        # Fallback to default plan details if not found in database
        plan_details = SubscriptionService.get_tier_features(new_tier)
        
    # Create payment
    payment = PaymentService.create_subscription_payment(
        user=request.user,
        plan=new_tier,
        amount=plan_details['price']
    )
    
    if not payment.get('success'):
        messages.error(request, f"Payment initialization failed: {payment.get('error')}")
        return redirect('core:subscription_plans')
    
    context = {
        'plan': new_tier,
        'plan_name': plan_details['name'],
        'plan_price': plan_details['price'],
        'payment_reference': payment['reference'],
        'authorization_url': payment['authorization_url'],
        'paystack_public_key': settings.PAYSTACK_PUBLIC_KEY
    }
    
    return render(request, 'core/subscription/payment.html', context)

@login_required
def cancel_subscription(request):
    """Handle subscription cancellation"""
    if request.method != 'POST':
        logger.warning('Cancel subscription view received non-POST request')
        return redirect('core:subscription_plans')
    
    try:
        result = SubscriptionService.cancel_subscription(request.user)
        
        if result.get('success'):
            messages.success(request, 'Subscription cancelled successfully.')
        else:
            logger.error(f"Failed to cancel subscription: {result.get('error')}")
            messages.error(request, f"Failed to cancel subscription: {result.get('error')}")
    except Exception as e:
        logger.exception("Error cancelling subscription")
        messages.error(request, f"An error occurred while cancelling your subscription: {str(e)}")
    
    return redirect('core:subscription_plans')

@login_required
def subscription_status(request):
    """Get current subscription status"""
    try:
        subscription = request.user.subscription
        return JsonResponse({
            'status': 'success',
            'data': {
                'tier': subscription.tier,
                'is_active': subscription.is_active,
                'end_date': subscription.end_date.isoformat() if subscription.end_date else None,
                'features': SubscriptionService.get_tier_features(subscription.tier)
            }
        })
    except AttributeError:
        return JsonResponse({
            'status': 'error',
            'message': 'No subscription found'
        })

@csrf_exempt
@require_POST
def paystack_webhook(request):
    """Handle Paystack webhook events for subscriptions"""
    payload = request.body
    signature = request.META.get('HTTP_X_PAYSTACK_SIGNATURE')
    
    if not signature:
        return JsonResponse({'error': 'Missing signature'}, status=400)
    
    # Verify Paystack signature
    computed_hmac = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode('utf-8'),
        payload,
        hashlib.sha512
    ).hexdigest()
    
    if computed_hmac != signature:
        return JsonResponse({'error': 'Invalid signature'}, status=400)
    
    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid payload'}, status=400)
    
    # Handle different event types
    event_type = event.get('event')
    
    if event_type == 'charge.success':
        # Handle successful payment
        data = event.get('data', {})
        reference = data.get('reference')
        metadata = data.get('metadata', {})
        
        if reference and reference.startswith('sub_'):
            # This is a subscription payment
            plan = metadata.get('plan')
            user_id = metadata.get('user_id')
            
            if plan and user_id:
                result = SubscriptionService.confirm_subscription(
                    user_id=user_id,
                    plan=plan,
                    payment_reference=reference
                )
                
                if result.get('success'):
                    return JsonResponse({'status': 'success', 'message': 'Subscription confirmed'})
                else:
                    return JsonResponse({'error': result.get('error')}, status=400)
    
    return JsonResponse({'status': 'success', 'message': 'Event processed'}) 