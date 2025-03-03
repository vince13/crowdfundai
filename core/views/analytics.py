from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from ..services.analytics import AnalyticsService
from ..models import AppListing

@login_required
def analytics_dashboard(request):
    """Main analytics dashboard view"""
    context = {
        'investment_trends': AnalyticsService.get_investment_trends(),
        'user_engagement': AnalyticsService.get_user_engagement_metrics(),
        'app_performance': AnalyticsService.get_app_performance_metrics(),
        'portfolio_analytics': AnalyticsService.get_portfolio_analytics(request.user)
    }
    return render(request, 'core/analytics/dashboard.html', context)

@login_required
def investment_analytics(request):
    """Investment analytics view"""
    context = {
        'investment_trends': AnalyticsService.get_investment_trends(),
        'portfolio_analytics': AnalyticsService.get_portfolio_analytics(request.user)
    }
    return render(request, 'core/analytics/investments.html', context)

@login_required
def app_analytics(request, pk):
    """Analytics for a specific app"""
    app = get_object_or_404(AppListing, pk=pk)
    context = {
        'app': app,
        'metrics': AnalyticsService.get_app_performance_metrics()
    }
    return render(request, 'core/apps/detail.html', context) 