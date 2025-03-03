from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Subquery, OuterRef, Q
from ..models import AppListing, Investment, ShareOwnership
from django.db.models import F, DecimalField, Case, When
from django.db.models.functions import Coalesce
from decimal import Decimal
from django.contrib import messages
from ..models import EscrowTransaction
from ..services.analytics import AnalyticsService
from django.utils import timezone

def format_naira(amount):
    """Format amount in Naira"""
    if amount is None:
        return '-'
    return f"₦{float(amount):,.2f}"

def home(request):
    featured_apps = AppListing.objects.filter(
        status=AppListing.Status.ACTIVE
    )[:6]
    funded_apps = AppListing.objects.filter(
        Q(status=AppListing.Status.FUNDED) |
        Q(status=AppListing.Status.COMPLETED)
    )[:6]
    return render(request, 'core/home.html', {
        'featured_apps': featured_apps,
        'funded_apps': funded_apps
    })

@login_required
def investor_dashboard(request):
    """Enhanced dashboard with advanced analytics"""
    if request.user.is_developer():
        # Get developer's apps and their statistics
        apps = AppListing.objects.filter(developer=request.user)
        
        # Annotate each app with total_released_percentage
        for app in apps:
            total_received = app.total_received
            total_released = app.total_released
            app.total_released_percentage = (total_released / total_received * 100) if total_received > 0 else 0
        
        total_apps = apps.count()
        active_apps = apps.filter(status=AppListing.Status.ACTIVE).count()
        funded_apps = apps.filter(status=AppListing.Status.FUNDED).count()
        
        # Calculate total funding received
        total_funding = Investment.objects.filter(
            app__developer=request.user
        ).aggregate(
            total=Sum('amount_paid')
        )['total'] or 0
        
        return render(request, 'core/dashboard/developer.html', {
            'apps': apps,
            'stats': {
                'total_apps': total_apps,
                'active_apps': active_apps,
                'funded_apps': funded_apps,
                'total_funding': format_naira(total_funding),
            }
        })
    else:
        # Get user's investments with related app data
        investments = Investment.objects.filter(
            investor=request.user
        ).select_related('app').annotate(
            total_percentage=Coalesce(
                Subquery(
                    Investment.objects.filter(
                        investor=request.user,
                        app=OuterRef('app')
                    ).values('app').annotate(
                        total=Sum('percentage_bought')
                    ).values('total')[:1]
                ),
                Decimal('0')
            )
        )
        
        # Calculate current values for investments
        investment_data = []
        for investment in investments:
            current_value = (investment.total_percentage / Decimal('100')) * investment.app.fixed_valuation if investment.app.fixed_valuation else investment.amount_paid or Decimal('0')
            investment_data.append({
                'investment': investment,
                'current_value': current_value,
                'formatted_current_value': format_naira(current_value)
            })
        
        # Get recent investments
        recent_investments = Investment.objects.filter(
            investor=request.user
        ).select_related('app').order_by('-created_at')[:5]
        
        # Calculate current values for recent investments
        recent_investment_data = []
        for investment in recent_investments:
            current_value = (investment.total_percentage / Decimal('100')) * investment.app.fixed_valuation if investment.app.fixed_valuation else investment.amount_paid
            recent_investment_data.append({
                'investment': investment,
                'current_value': current_value,
                'formatted_current_value': format_naira(current_value)
            })
        
        # Get analytics service data
        portfolio_analytics = AnalyticsService.get_portfolio_analytics(request.user)
        
        # Calculate portfolio metrics
        total_invested = Investment.objects.filter(
            investor=request.user
        ).aggregate(
            total=Coalesce(Sum('amount_paid'), Decimal('0'))
        )['total']
        
        # Calculate current portfolio value based on percentage ownership
        portfolio_value = Decimal('0')
        processed_apps = set()
        
        for investment in investments:
            if investment.app.id not in processed_apps:
                if investment.app.fixed_valuation:
                    value = (investment.total_percentage / Decimal('100')) * investment.app.fixed_valuation
                    portfolio_value += value
                else:
                    # If no valuation change, sum up all investments for this app
                    app_investments = sum(inv.amount_paid or Decimal('0') for inv in investments if inv.app.id == investment.app.id)
                    portfolio_value += app_investments
                processed_apps.add(investment.app.id)
        
        # Calculate ROI
        roi = Decimal('0')  # Default to 0% ROI
        if total_invested > 0:
            roi = ((portfolio_value - total_invested) / total_invested * 100)
        
        # Calculate escrow balance
        escrow_query = EscrowTransaction.objects.filter(
            investor=request.user,
            status='COMPLETED'
        )
        print(f"Escrow Query SQL: {escrow_query.query}")
        
        escrow_balance = escrow_query.aggregate(
            balance=Sum(Case(
                When(transaction_type='DEPOSIT', then='amount'),
                When(transaction_type__in=['RELEASE', 'REFUND'], then=-F('amount')),
                default=0,
                output_field=DecimalField()
            ))
        )['balance'] or Decimal('0')
        
        print(f"Escrow Balance: {escrow_balance}")
        print(f"Escrow Balance Type: {type(escrow_balance)}")
        
        # Enhanced analytics
        investment_distribution = Investment.objects.filter(
            investor=request.user
        ).values(
            'app__name'
        ).annotate(
            total=Sum('amount_paid'),
            percentage_bought=Sum('percentage_bought')
        ).order_by('-total')
        
        # Calculate percentages of total investment for chart
        chart_data = []
        category_labels = []
        category_data = []
        
        for item in investment_distribution:
            percentage = (item['total'] / total_invested * 100) if total_invested > 0 else Decimal('0.00')
            chart_data.append({
                'name': item['app__name'],
                'total': format_naira(item['total']),
                'percentage_bought': item['percentage_bought'],
                'percentage': percentage
            })
            category_labels.append(item['app__name'])
            category_data.append(float(item['total']))
        
        # Calculate average investment
        average_investment = total_invested / investments.count() if investments.count() > 0 else Decimal('0')
        
        stats = {
            'total_invested': total_invested,  # Raw value for calculations
            'formatted_total_invested': format_naira(total_invested),
            'portfolio_value': portfolio_value,  # Raw value for calculations
            'formatted_portfolio_value': format_naira(portfolio_value),
            'roi': roi,
            'apps_invested': investments.count(),
            'average_investment': average_investment,  # Raw value for calculations
            'formatted_average_investment': format_naira(average_investment),
            'escrow_balance': escrow_balance,  # Raw value for calculations
            'formatted_escrow_balance': format_naira(escrow_balance)
        }
        
        # Get recent investments for trends chart
        recent_trends = Investment.objects.filter(
            investor=request.user
        ).order_by('created_at')
        
        investment_dates = [investment.created_at.strftime('%Y-%m-%d') for investment in recent_trends]
        investment_amounts = [float(investment.amount_paid) for investment in recent_trends]
        
        context = {
            'investments': investment_data,
            'recent_investments': recent_investment_data,
            'stats': stats,
            'investment_distribution': chart_data,
            'category_labels': category_labels,
            'category_data': category_data,
            'investment_dates': investment_dates,
            'investment_amounts': investment_amounts,
            'portfolio_analytics': portfolio_analytics,
            'analytics': {
                'portfolio_health': {
                    'diversification_score': portfolio_analytics.get('diversification_score', 0),
                    'avg_volatility': portfolio_analytics.get('avg_volatility', 0),
                    'best_performing_app': portfolio_analytics.get('best_performing_app'),
                    'worst_performing_app': portfolio_analytics.get('worst_performing_app'),
                },
                'investment_summary': {
                    'total_return': format_naira(portfolio_value - total_invested),
                    'monthly_trend': portfolio_analytics.get('monthly_investment_trend', []),
                    'category_distribution': portfolio_analytics.get('investments_by_category', [])
                }
            },
            'debug': True
        }
        
        return render(request, 'core/dashboard/investor.html', context)

def index(request):
    """Home page view."""
    # Get featured apps
    featured_apps = AppListing.objects.filter(
        status=AppListing.Status.ACTIVE,
        is_featured=True
    ).order_by('-created_at')[:6]
    
    # Get latest apps
    latest_apps = AppListing.objects.filter(
        status=AppListing.Status.ACTIVE
    ).order_by('-created_at')[:6]
    
    # Get trending apps (most investments in last 30 days)
    thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
    trending_apps = AppListing.objects.filter(
        status=AppListing.Status.ACTIVE,
        investments__created_at__gte=thirty_days_ago
    ).annotate(
        investment_count=Count('investments')
    ).order_by('-investment_count')[:6]
    
    # Format amounts in Naira
    for app in featured_apps:
        app.formatted_price = format_naira(app.price_per_percentage)
        app.formatted_funding_goal = format_naira(app.funding_goal)
        
    for app in latest_apps:
        app.formatted_price = format_naira(app.price_per_percentage)
        app.formatted_funding_goal = format_naira(app.funding_goal)
        
    for app in trending_apps:
        app.formatted_price = format_naira(app.price_per_percentage)
        app.formatted_funding_goal = format_naira(app.funding_goal)
    
    return render(request, 'core/index.html', {
        'featured_apps': featured_apps,
        'latest_apps': latest_apps,
        'trending_apps': trending_apps
    }) 