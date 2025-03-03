from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum
from ..models import AppListing, EscrowTransaction

def is_developer(user):
    return user.is_authenticated and user.role == 'DEVELOPER'

@login_required
@user_passes_test(is_developer)
def escrow_balance(request):
    """View for developers to see their total escrow balance across all apps"""
    apps = AppListing.objects.filter(developer=request.user)
    
    # Calculate total escrow balance
    total_balance = sum(app.funds_in_escrow for app in apps)
    
    # Get recent transactions
    recent_transactions = EscrowTransaction.objects.filter(
        app__in=apps
    ).order_by('-created_at')[:10]
    
    return render(request, 'core/escrow/developer_balance.html', {
        'total_balance': total_balance,
        'apps': apps,
        'recent_transactions': recent_transactions
    })

@login_required
@user_passes_test(is_developer)
def transaction_history(request):
    """View for developers to see their transaction history"""
    apps = AppListing.objects.filter(developer=request.user)
    transactions = EscrowTransaction.objects.filter(
        app__in=apps
    ).select_related('app', 'milestone').order_by('-created_at')
    
    print(f"Developer: {request.user.username}")
    print(f"Apps found: {apps.count()}")
    print(f"Transactions found: {transactions.count()}")
    
    return render(request, 'core/escrow/developer_history.html', {
        'transactions': transactions,
        'apps': apps,
        'debug': {
            'user': request.user.username,
            'apps_count': apps.count(),
            'transactions_count': transactions.count()
        }
    })

@login_required
@user_passes_test(is_developer)
def app_transactions(request, app_id):
    """View for developers to see transactions for a specific app"""
    app = get_object_or_404(AppListing, id=app_id, developer=request.user)
    transactions = EscrowTransaction.objects.filter(
        app=app
    ).order_by('-created_at')
    
    return render(request, 'core/escrow/developer_app_transactions.html', {
        'app': app,
        'transactions': transactions
    }) 