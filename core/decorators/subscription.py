from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse

def require_subscription_feature(feature_name):
    """
    Decorator to check if user has access to a specific subscription feature.
    Redirects to upgrade page if feature is not available.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('core:login')
            
            try:
                subscription = request.user.subscription
                if not subscription.is_active:
                    messages.warning(request, 'Your subscription is inactive. Please renew to access this feature.')
                    return redirect('core:subscription_plans')
                
                if not subscription.has_feature(feature_name):
                    messages.info(request, 'This feature requires a Pro subscription. Please upgrade to access it.')
                    return redirect('core:subscription_plans')
                
                # Track feature usage
                usage, _ = subscription.feature_usage.get_or_create(feature_name=feature_name)
                usage.usage_count += 1
                usage.save()
                
                return view_func(request, *args, **kwargs)
            except AttributeError:
                # User has no subscription, create free tier
                from core.models.subscription import Subscription
                Subscription.objects.create(user=request.user)
                messages.info(request, 'This feature requires a Pro subscription. Please upgrade to access it.')
                return redirect('core:subscription_plans')
            
        return _wrapped_view
    return decorator 