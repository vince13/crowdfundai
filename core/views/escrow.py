from django.shortcuts import render, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum, Count
from ..models import EscrowTransaction, ProjectMilestone, AppListing
from ..services.escrow import EscrowService
from ..services.reporting import EscrowReportingService
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test

def is_developer(user):
    return user.is_authenticated and user.role == 'DEVELOPER'

@staff_member_required
def escrow_reports_list(request):
    """View for listing escrow reports and analytics."""
    
    # Get overall statistics
    total_transactions = EscrowTransaction.objects.count()
    total_in_escrow = AppListing.objects.aggregate(
        total=Sum('funds_in_escrow')
    )['total'] or 0
    
    # Get transaction statistics
    transaction_stats = EscrowTransaction.objects.values('transaction_type').annotate(
        count=Count('id'),
        total_amount=Sum('amount')
    )
    
    # Get dispute statistics
    dispute_stats = EscrowTransaction.objects.exclude(
        dispute_status='NO_DISPUTE'
    ).values('dispute_status').annotate(
        count=Count('id'),
        total_amount=Sum('amount')
    )
    
    # Get milestone statistics
    milestone_stats = ProjectMilestone.objects.values('status').annotate(
        count=Count('id')
    )
    
    context = {
        'total_transactions': total_transactions,
        'total_in_escrow': total_in_escrow,
        'transaction_stats': transaction_stats,
        'dispute_stats': dispute_stats,
        'milestone_stats': milestone_stats,
        'apps': AppListing.objects.filter(funds_in_escrow__gt=0)
    }
    
    return render(request, 'core/escrow/reports_list.html', context)

@staff_member_required
def transaction_history(request, app_id):
    """View for displaying transaction history for a specific app."""
    app = get_object_or_404(AppListing, id=app_id)
    
    transactions = EscrowTransaction.objects.filter(app=app).select_related(
        'investor', 'milestone'
    ).order_by('-created_at')
    
    context = {
        'app': app,
        'transactions': transactions,
        'escrow_summary': EscrowService.get_escrow_summary(app)
    }
    
    return render(request, 'core/escrow/transaction_history.html', context)

@staff_member_required
def monthly_report(request, app_id):
    """View for displaying monthly escrow report for a specific app."""
    app = get_object_or_404(AppListing, id=app_id)
    
    # Convert year and month to integers, defaulting to current year/month
    current_date = timezone.now()
    year = int(request.GET.get('year', current_date.year))
    month = int(request.GET.get('month', current_date.month))
    
    report = EscrowReportingService.generate_monthly_report(
        app,
        year,
        month
    )
    
    context = {
        'app': app,
        'report': report
    }
    
    return render(request, 'core/escrow/monthly_report.html', context)

@login_required
@user_passes_test(is_developer)
def developer_escrow_balance(request):
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
def developer_transaction_history(request):
    """View for developers to see their transaction history"""
    apps = AppListing.objects.filter(developer=request.user)
    transactions = EscrowTransaction.objects.filter(
        app__in=apps
    ).order_by('-created_at')
    
    return render(request, 'core/escrow/developer_history.html', {
        'transactions': transactions
    })

@login_required
@user_passes_test(is_developer)
def developer_app_transactions(request, app_id):
    """View for developers to see transactions for a specific app"""
    app = get_object_or_404(AppListing, id=app_id, developer=request.user)
    transactions = EscrowTransaction.objects.filter(
        app=app
    ).order_by('-created_at')
    
    return render(request, 'core/escrow/developer_app_transactions.html', {
        'app': app,
        'transactions': transactions
    })

@login_required
def investor_escrow_reports(request):
    """View for investors to see their escrow reports."""
    
    # Get transactions for this investor
    transactions = EscrowTransaction.objects.filter(
        investor=request.user
    ).select_related('app')
    
    # Get overall statistics
    total_transactions = transactions.count()
    total_in_escrow = transactions.filter(
        transaction_type='DEPOSIT',
        status='COMPLETED'
    ).aggregate(
        total=Sum('amount')
    )['total'] or 0
    
    # Get transaction statistics
    transaction_stats = transactions.values('transaction_type').annotate(
        count=Count('id'),
        total_amount=Sum('amount')
    )
    
    # Get apps with escrow
    apps_with_escrow = AppListing.objects.filter(
        escrowtransaction__investor=request.user,
        escrowtransaction__status='COMPLETED'
    ).distinct()
    
    context = {
        'total_transactions': total_transactions,
        'total_in_escrow': total_in_escrow,
        'transaction_stats': transaction_stats,
        'apps': apps_with_escrow
    }
    
    return render(request, 'core/escrow/investor_reports.html', context) 