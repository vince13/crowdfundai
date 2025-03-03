from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from core.services import AIInsightService
from django.shortcuts import get_object_or_404, render
from django.core.exceptions import ValidationError
import logging
from ..decorators.subscription import require_subscription_feature
from ..models import AppListing

logger = logging.getLogger(__name__)
ai_service = AIInsightService()

def handle_ai_request(func):
    """Decorator to handle AI request errors"""
    def wrapper(request, app_id):
        try:
            return func(request, app_id)
        except AppListing.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'App not found'
            }, status=404)
        except ValidationError as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
        except Exception as e:
            logger.error(f"AI insight error: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': 'An error occurred processing the request'
            }, status=500)
    return wrapper

@login_required
@require_subscription_feature('basic_ai_insights')
def app_insights(request, app_id):
    """View for basic AI insights"""
    app = get_object_or_404(AppListing, id=app_id)
    insights = ai_service.generate_app_insights(app)
    return render(request, 'core/apps/insights.html', {
        'app': app,
        'insights': insights
    })

# Alias for backward compatibility
ai_insights = app_insights

@login_required
@require_subscription_feature('detailed_risk_analysis')
def risk_analysis(request, app_id):
    """Get detailed risk analysis for an app (Pro feature)"""
    app = get_object_or_404(AppListing, id=app_id)
    analysis = ai_service.get_detailed_risk_analysis(app)
    return JsonResponse({
        'status': 'success',
        'data': analysis
    })

@login_required
@require_subscription_feature('advanced_ai_assessment')
def tech_evaluation(request, app_id):
    """Get technical evaluation of app (Developer Pro feature)"""
    app = get_object_or_404(AppListing, id=app_id)
    evaluation = ai_service.evaluate_technology(app)
    return JsonResponse({
        'status': 'success',
        'data': evaluation
    })

@login_required
@require_subscription_feature('market_trends')
def market_analysis(request, app_id):
    """Get market analysis and trends (Pro feature)"""
    app = get_object_or_404(AppListing, id=app_id)
    analysis = ai_service.analyze_market(app)
    return JsonResponse({
        'status': 'success',
        'data': analysis
    })

# Alias for backward compatibility
market_trends = market_analysis

@login_required
@require_subscription_feature('portfolio_optimization')
def portfolio_insights(request):
    """Get portfolio optimization insights (Investor Pro feature)"""
    insights = ai_service.analyze_portfolio(request.user)
    return JsonResponse({
        'status': 'success',
        'data': insights
    })

@login_required
@handle_ai_request
def app_valuation(request, app_id):
    """Get AI-powered valuation estimate"""
    app = get_object_or_404(AppListing, id=app_id)
    valuation = ai_service.estimate_valuation(app)
    return JsonResponse({
        'status': 'success',
        'data': {
            'valuation': valuation,
            'factors': {
                'market_size': ai_service._analyze_market_size(app),
                'revenue_potential': ai_service._estimate_revenue_potential(app),
                'technology_value': ai_service._assess_technology_value(app),
                'team_strength': ai_service._evaluate_team_strength(app)
            }
        }
    })

@login_required
@handle_ai_request
def investment_recommendations(request, app_id):
    """Get personalized investment recommendations"""
    app = get_object_or_404(AppListing, id=app_id)
    recommendation = ai_service.get_investment_recommendation(app)
    return JsonResponse({
        'status': 'success',
        'data': recommendation
    })

@login_required
@handle_ai_request
def growth_potential(request, app_id):
    """Get growth potential analysis"""
    app = get_object_or_404(AppListing, id=app_id)
    potential = ai_service.assess_growth_potential(app)
    return JsonResponse({
        'status': 'success',
        'data': potential
    }) 