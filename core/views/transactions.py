from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, F, ExpressionWrapper, DecimalField, Value, Q
from django.db.models.functions import TruncMonth, Coalesce
from django.utils import timezone
from decimal import Decimal
from ..models import Transaction, Investment, ShareOwnership
from django.http import HttpResponse
import csv
from datetime import datetime, timedelta
import numpy as np
from dateutil.relativedelta import relativedelta

@login_required
def transaction_history(request):
    transactions = Transaction.objects.filter(
        user=request.user
    ).select_related('app')
    
    # Filter parameters
    date_range = request.GET.get('date_range')
    transaction_type = request.GET.get('type')
    min_amount = request.GET.get('min_amount')
    max_amount = request.GET.get('max_amount')
    search = request.GET.get('search', '')  # Default to empty string instead of None
    
    print(f"Filter values received:")
    print(f"date_range: {date_range}")
    print(f"transaction_type: {transaction_type}")
    print(f"min_amount: {min_amount}")
    print(f"max_amount: {max_amount}")
    print(f"search: {search}")
    
    # Store filters for template
    filters = {
        'date_range': date_range,
        'transaction_type': transaction_type,
        'min_amount': min_amount,
        'max_amount': max_amount,
        'search': search if search != 'None' else ''  # Convert 'None' string to empty string
    }
    
    # Apply filters
    if date_range:
        today = timezone.now()
        if date_range == '7d':
            start_date = today - timedelta(days=7)
        elif date_range == '30d':
            start_date = today - timedelta(days=30)
        elif date_range == '90d':
            start_date = today - timedelta(days=90)
        elif date_range == '1y':
            start_date = today - timedelta(days=365)
        transactions = transactions.filter(created_at__gte=start_date)
        print(f"After date filter: {transactions.count()} transactions")
    
    if transaction_type:
        transactions = transactions.filter(transaction_type=transaction_type)
        print(f"After type filter: {transactions.count()} transactions")
    
    if min_amount:
        try:
            min_amount_decimal = Decimal(min_amount)
            transactions = transactions.filter(amount__gte=min_amount_decimal)
            print(f"After min amount filter: {transactions.count()} transactions")
        except (ValueError, decimal.InvalidOperation) as e:
            print(f"Error converting min_amount: {e}")
    
    if max_amount:
        try:
            max_amount_decimal = Decimal(max_amount)
            transactions = transactions.filter(amount__lte=max_amount_decimal)
            print(f"After max amount filter: {transactions.count()} transactions")
        except (ValueError, decimal.InvalidOperation) as e:
            print(f"Error converting max_amount: {e}")
    
    if search and search != 'None':  # Only apply search if it's not empty or 'None'
        transactions = transactions.filter(
            Q(app__name__icontains=search) |
            Q(transaction_type__icontains=search)
        )
        print(f"After search filter: {transactions.count()} transactions")
    
    print(f"Final transaction count: {transactions.count()}")
    
    # Order by date
    transactions = transactions.order_by('-created_at')
    
    # Calculate statistics based on filtered data
    monthly_stats = transactions.annotate(
        month=TruncMonth('created_at')
    ).values('month', 'transaction_type').annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('-month', 'transaction_type')
    
    type_totals = transactions.values(
        'transaction_type'
    ).annotate(
        total=Sum('amount'),
        count=Count('id')
    )
    
    # Handle export
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="transactions_{datetime.now().strftime("%Y%m%d")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Date', 'App', 'Type', 'Amount'])
        
        for transaction in transactions:
            writer.writerow([
                transaction.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                transaction.app.name,
                transaction.get_transaction_type_display(),
                f"${transaction.amount:.2f}"
            ])
        
        return response
    
    context = {
        'transactions': transactions,
        'monthly_stats': monthly_stats,
        'type_totals': {
            item['transaction_type']: {
                'total': item['total'],
                'count': item['count']
            } for item in type_totals
        },
        'filters': filters
    }
    
    return render(request, 'core/transactions/history.html', context)

@login_required
def investment_analytics(request):
    # Get user's investments with related app data
    investments = Investment.objects.filter(
        investor=request.user
    ).select_related('app')
    
    # Calculate portfolio metrics
    total_invested = investments.aggregate(
        total=Coalesce(Sum('amount_paid'), Decimal('0'))
    )['total']
    
    total_apps = investments.values('app').distinct().count()
    
    # Calculate average investment
    average_investment = Decimal('0.00')
    if total_apps > 0:
        average_investment = total_invested / total_apps
    
    # Calculate investment distribution by app
    distribution = investments.values(
        'app__name'
    ).annotate(
        total=Sum('amount_paid'),
        share_count=Sum('shares_bought')
    ).order_by('-total')

    # Calculate percentages after getting the distribution
    for item in distribution:
        item['percentage'] = (
            (item['total'] / total_invested * 100)
            if total_invested > 0 
            else Decimal('0.00')
        )
    
    # Get current portfolio value
    share_ownerships = ShareOwnership.objects.filter(
        user=request.user
    ).select_related('app')
    
    portfolio_value = calculate_portfolio_value(share_ownerships)
    
    # Calculate total ROI
    roi = ((portfolio_value - total_invested) / total_invested * 100) if total_invested > 0 else 0
    
    # Get monthly investment trend
    monthly_investments = investments.annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        amount=Sum('amount_paid')
    ).order_by('month')
    
    # Enhanced Analytics
    
    # 1. ROI Trends (Monthly)
    monthly_roi = []
    for ownership in share_ownerships:
        monthly_value_changes = ownership.app.sharepricehistory_set.annotate(
            month=TruncMonth('date')
        ).values('month').annotate(
            avg_price=Avg('price')
        ).order_by('month')
        
        for change in monthly_value_changes:
            roi = calculate_roi(ownership, change)
            monthly_roi.append({
                'month': change['month'],
                'roi': roi,
                'app': ownership.app.name
            })
    
    # 2. Risk Metrics
    risk_metrics = {}
    for ownership in share_ownerships:
        price_history = ownership.app.sharepricehistory_set.values_list('price', flat=True)
        if price_history:
            prices = np.array(price_history)
            risk_metrics[ownership.app.name] = {
                'volatility': np.std(prices) / np.mean(prices) * 100,  # Coefficient of variation
                'max_drawdown': calculate_max_drawdown(prices),
                'sharpe_ratio': calculate_sharpe_ratio(prices),
            }
    
    # 3. Portfolio Diversification Score
    total_investment = sum(ownership.percentage_owned * ownership.app.price_per_percentage for ownership in share_ownerships)
    
    diversification_score = 0
    if total_investment > 0:
        weights = calculate_portfolio_weights(share_ownerships, total_investment)
        diversification_score = (1 - sum(weights)) * 100  # Higher is better
    
    # 4. Performance Metrics by Category
    category_performance = get_investment_stats(request.user)

    # 5. Performance Metrics by AI Feature
    feature_performance = get_investment_stats(request.user)

    # 5. Investment Growth Projection
    growth_projections = calculate_growth_projections(investments)
    
    # Update context with new analytics
    context = {
        'investments': investments,
        'total_invested': total_invested,
        'total_apps': total_apps,
        'average_investment': average_investment,
        'distribution': distribution,
        'portfolio_value': portfolio_value,
        'roi': roi,
        'monthly_investments': monthly_investments,
        'stats': {
            'total_invested': total_invested,
            'portfolio_value': portfolio_value,
            'total_apps': total_apps,
            'roi': roi,
            'average_investment': average_investment
        },
        'monthly_roi': monthly_roi,
        'risk_metrics': risk_metrics,
        'diversification_score': diversification_score,
        'category_performance': category_performance,
        'feature_performance': feature_performance,
        'growth_projections': growth_projections,
        'analytics': {
            'portfolio_health': {
                'diversification_score': diversification_score,
                'avg_volatility': sum(m['volatility'] for m in risk_metrics.values()) / len(risk_metrics) if risk_metrics else 0,
                'best_performing_app': max(monthly_roi, key=lambda x: x['roi'])['app'] if monthly_roi else None,
                'worst_performing_app': min(monthly_roi, key=lambda x: x['roi'])['app'] if monthly_roi else None,
                'top_category': max(category_performance, key=lambda x: x['roi'])['app__category'] if category_performance else None,
                'top_feature': max(feature_performance, key=lambda x: x['roi'])['app__ai_features'] if feature_performance else None,
            },
            'investment_summary': {
                'total_return': portfolio_value - total_invested,
                'annualized_return': calculate_annualized_return(investments, portfolio_value),
                'risk_adjusted_return': calculate_risk_adjusted_return(monthly_roi),
            }
        }
    }
    
    return render(request, 'core/transactions/analytics.html', context)

@login_required
def transaction_detail(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id, user=request.user)
    
    context = {
        'transaction': transaction,
    }
    
    return render(request, 'core/transactions/detail.html', context)

# Helper functions for analytics calculations
def calculate_max_drawdown(prices):
    """Calculate the maximum drawdown from peak to trough."""
    peak = prices[0]
    max_drawdown = 0
    
    for price in prices:
        if price > peak:
            peak = price
        drawdown = (peak - price) / peak * 100
        max_drawdown = max(max_drawdown, drawdown)
    
    return max_drawdown

def calculate_sharpe_ratio(prices, risk_free_rate=0.02):
    """Calculate the Sharpe ratio using price history."""
    returns = np.diff(prices) / prices[:-1]
    excess_returns = returns - (risk_free_rate / 252)  # Daily risk-free rate
    if len(excess_returns) > 0:
        return np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)
    return 0

def calculate_growth_projections(investments):
    """Calculate investment growth projections."""
    projections = []
    current_month = timezone.now().date().replace(day=1)
    
    for months in [3, 6, 12, 24]:
        projection_date = current_month + relativedelta(months=months)
        projected_value = 0
        
        for investment in investments:
            # Simple projection using historical growth rate
            historical_growth = investment.app.sharepricehistory_set.aggregate(
                growth=ExpressionWrapper(
                    (F('price__max') - F('price__min')) * 100.0 / F('price__min'),
                    output_field=DecimalField(max_digits=10, decimal_places=2)
                )
            )['growth'] or 0
            
            monthly_growth = historical_growth / 12
            projected_growth = (1 + monthly_growth/100) ** months
            projected_value += investment.amount_paid * projected_growth
        
        projections.append({
            'months': months,
            'date': projection_date,
            'value': projected_value
        })
    
    return projections

def calculate_annualized_return(investments, current_value):
    """Calculate annualized return rate."""
    if not investments:
        return 0
    
    initial_investment = investments.aggregate(
        total=Sum('amount_paid')
    )['total'] or 0
    
    if initial_investment == 0:
        return 0
    
    # Get the age of the oldest investment in years
    oldest_investment = investments.order_by('created_at').first()
    if not oldest_investment:
        return 0
    
    years = (timezone.now() - oldest_investment.created_at).days / 365.25
    if years == 0:
        return 0
    
    return ((current_value / initial_investment) ** (1/years) - 1) * 100

def calculate_risk_adjusted_return(monthly_roi):
    """Calculate risk-adjusted return using Sortino ratio."""
    if not monthly_roi:
        return 0
    
    returns = [m['roi'] for m in monthly_roi]
    avg_return = np.mean(returns)
    downside_returns = [r for r in returns if r < 0]
    
    if not downside_returns:
        return avg_return
    
    downside_std = np.std(downside_returns)
    if downside_std == 0:
        return 0
    
    return avg_return / downside_std 

def calculate_portfolio_value(ownerships):
    """Calculate total portfolio value"""
    total_value = Decimal('0.00')
    for ownership in ownerships:
        total_value += ownership.percentage_owned * ownership.app.price_per_percentage
    return total_value

def calculate_roi(ownership, change):
    """Calculate ROI for an ownership"""
    if not ownership.initial_price_per_percentage:
        return 0
    roi = ((change['avg_price'] - ownership.initial_price_per_percentage) /
           ownership.initial_price_per_percentage * 100)
    return round(roi, 2)

def calculate_portfolio_weights(ownerships, total_investment):
    """Calculate portfolio weights for risk analysis"""
    if not total_investment:
        return []
    weights = []
    for ownership in ownerships:
        investment_value = ownership.percentage_owned * ownership.app.price_per_percentage
        weight = (investment_value / total_investment) ** 2
        weights.append(weight)
    return weights

def get_investment_stats(user):
    """Get investment statistics"""
    return Investment.objects.filter(investor=user).aggregate(
        total_invested=Sum('amount_paid'),
        current_value=Sum(F('percentage_bought') * F('app__price_per_percentage')),
        total_investments=Count('id')
    )

def get_portfolio_stats(user):
    """Get portfolio statistics"""
    return ShareOwnership.objects.filter(user=user).aggregate(
        total_invested=Sum('initial_investment'),
        current_value=Sum(F('percentage_owned') * F('app__price_per_percentage')),
        total_apps=Count('id')
    ) 