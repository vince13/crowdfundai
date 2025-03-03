from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.conf import settings
from django.db import transaction
from django.db.models import Sum, Case, When, DecimalField, F, Exists, OuterRef, Subquery
from django.db.models.functions import Coalesce
from ..models import AppListing, Investment, ShareOwnership, EscrowTransaction, Notification
from ..forms import InvestmentForm
from ..utils import convert_currency, get_exchange_rate
from ..services.payments import PaymentService
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

def invest(request, app_id):
    """Handle investment in an app"""
    app = get_object_or_404(AppListing, pk=app_id)
    
    # Check if app is properly configured for investment
    if app.price_per_percentage is None or app.remaining_percentage is None:
        messages.error(request, 'App listing is not properly configured for investments')
        return redirect('core:app_detail', pk=app_id)
    
    # For POST requests (actual investment), require login
    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect('core:login')
            
        form = InvestmentForm(request.POST)
        if form.is_valid():
            try:
                percentage = Decimal(request.POST.get('percentage', '0'))
                
                # Validate percentage is within bounds
                if percentage < app.min_investment_percentage:
                    messages.error(request, f'Minimum investment is {app.min_investment_percentage}%')
                    return redirect('core:app_detail', pk=app_id)
                
                if percentage > app.available_percentage:
                    messages.error(request, f'Maximum investment is {app.available_percentage}%')
                    return redirect('core:app_detail', pk=app_id)
                
                # Calculate amount
                amount = app.price_per_percentage * percentage
                
                # Check minimum investment amount
                if amount < app.price_per_percentage:
                    messages.error(request, 'Investment amount must be at least equal to the price per percentage')
                    return redirect('core:app_detail', pk=app_id)
                
                # Check if total investment would exceed available percentage
                total_invested = Investment.objects.filter(
                    investor=request.user
                ).aggregate(
                    total=Sum('percentage_bought')
                )['total'] or Decimal('0')
                
                if total_invested + percentage > app.available_percentage:
                    messages.error(request, f'Not enough percentage available. Only {app.remaining_percentage}% remaining.')
                    return redirect('core:app_detail', pk=app_id)
                    
                # Create investment
                investment = Investment.objects.create(
                    investor=request.user,
                    app=app,
                    percentage_bought=percentage,
                    amount_paid=amount
                )
                
                messages.success(request, f'Investment of {percentage}% in {app.name} successful!')
                return redirect('core:portfolio')
                
            except ValueError as e:
                messages.error(request, str(e))
                return redirect('core:app_detail', pk=app_id)
            except Exception as e:
                logger.error(f"Investment failed: {str(e)}")
                messages.error(request, f'Investment failed: {str(e)}')
                return redirect('core:app_detail', pk=app_id)
    
    # For GET requests, allow viewing without authentication
    context = {
        'app': app,
        'paystack_public_key': settings.PAYSTACK_PUBLIC_KEY,
        'total_amount': app.price_per_percentage,  # Default to price of 1%
        'total_with_fee': app.price_per_percentage  # Default to price of 1%
    }
    
    return render(request, 'core/investments/invest.html', context)

@login_required
def portfolio(request):
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
    
    # Calculate total investment value
    total_invested = Investment.objects.filter(
        investor=request.user
    ).aggregate(
        total=Coalesce(Sum('amount_paid'), Decimal('0'))
    )['total']
    
    # Calculate current portfolio value based on percentage ownership and app valuation
    portfolio_value = Decimal('0')
    processed_apps = set()
    
    for investment in investments:
        if investment.app.id not in processed_apps:
            if investment.app.fixed_valuation:
                # Calculate value based on total percentage of total app valuation
                value = (investment.total_percentage / Decimal('100')) * investment.app.fixed_valuation
                portfolio_value += value
            else:
                # If no valuation change, sum up all investments for this app
                app_investments = sum(inv.amount_paid or Decimal('0') for inv in investments if inv.app.id == investment.app.id)
                portfolio_value += app_investments
            processed_apps.add(investment.app.id)
    
    # Calculate ROI
    if total_invested and total_invested > 0:
        roi = ((portfolio_value - total_invested) / total_invested) * Decimal('100')
    else:
        roi = Decimal('0')
    
    # Calculate escrow balance
    escrow_balance = EscrowTransaction.objects.filter(
        investor=request.user,
        status='COMPLETED'
    ).aggregate(
        balance=Sum(Case(
            When(transaction_type='DEPOSIT', then='amount'),
            When(transaction_type__in=['RELEASE', 'REFUND'], then=-F('amount')),
            default=0,
            output_field=DecimalField()
        ))
    )['balance'] or Decimal('0')
    
    # Calculate average investment
    average_investment = total_invested / investments.count() if investments.count() > 0 else Decimal('0')
    
    stats = {
        'total_invested': total_invested,
        'portfolio_value': portfolio_value,
        'roi': roi,
        'apps_invested': investments.count(),
        'average_investment': average_investment,
        'escrow_balance': escrow_balance,
        'total_return': portfolio_value - total_invested
    }
    
    context = {
        'investments': investments,
        'stats': stats,
        'currency': 'NGN'
    }
    return render(request, 'core/portfolio.html', context)

@login_required
def api_portfolio_stats(request):
    """API endpoint to get portfolio stats"""
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
    
    # Calculate total investment value
    total_invested = Investment.objects.filter(
        investor=request.user
    ).aggregate(
        total=Coalesce(Sum('amount_paid'), Decimal('0'))
    )['total']
    
    # Calculate current portfolio value based on percentage ownership and app valuation
    portfolio_value = Decimal('0')
    processed_apps = set()
    
    for investment in investments:
        if investment.app.id not in processed_apps:
            if investment.app.fixed_valuation:
                # Calculate value based on total percentage of total app valuation
                value = (investment.total_percentage / Decimal('100')) * investment.app.fixed_valuation
                portfolio_value += value
            else:
                # If no valuation change, sum up all investments for this app
                app_investments = sum(inv.amount_paid or Decimal('0') for inv in investments if inv.app.id == investment.app.id)
                portfolio_value += app_investments
            processed_apps.add(investment.app.id)
    
    # Calculate ROI
    if total_invested and total_invested > 0:
        roi = ((portfolio_value - total_invested) / total_invested) * Decimal('100')
    else:
        roi = Decimal('0')
    
    # Calculate escrow balance
    escrow_balance = EscrowTransaction.objects.filter(
        investor=request.user,
        status='COMPLETED'
    ).aggregate(
        balance=Sum(Case(
            When(transaction_type='DEPOSIT', then='amount'),
            When(transaction_type__in=['RELEASE', 'REFUND'], then=-F('amount')),
            default=0,
            output_field=DecimalField()
        ))
    )['balance'] or Decimal('0')
    
    # Calculate average investment
    average_investment = total_invested / investments.count() if investments.count() > 0 else Decimal('0')
    
    # Prepare investment data for the table
    investment_data = []
    for investment in investments:
        current_value = (investment.total_percentage / Decimal('100')) * investment.app.fixed_valuation if investment.app.fixed_valuation else Decimal('0')
        investment_data.append({
            'app': {
                'pk': investment.app.id,
                'name': investment.app.name,
                'status': investment.app.status,
                'price_per_percentage': float(investment.app.price_per_percentage) if investment.app.price_per_percentage else 0
            },
            'total_percentage': float(investment.total_percentage) if investment.total_percentage else 0,
            'amount_paid': float(investment.amount_paid) if investment.amount_paid else 0,
            'current_value': float(current_value)
        })
    
    return JsonResponse({
        'total_invested': float(total_invested) if total_invested else 0,
        'portfolio_value': float(portfolio_value) if portfolio_value else 0,
        'roi': float(roi) if roi else 0,
        'apps_invested': investments.count(),
        'average_investment': float(average_investment) if average_investment else 0,
        'escrow_balance': float(escrow_balance) if escrow_balance else 0,
        'total_return': float(portfolio_value - total_invested) if (portfolio_value and total_invested) else 0,
        'investments': investment_data
    })