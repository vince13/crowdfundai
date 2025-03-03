from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from ..services.reporting import EscrowReportingService
from ..models import User

def is_admin(user):
    return user.is_authenticated and user.role == User.Role.ADMIN

@login_required
def investment_report(request):
    """Generate investment report based on user role"""
    if request.method == 'POST':
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')

        if not start_date or not end_date:
            return HttpResponseBadRequest("Start date and end date are required.")

        # For admin, allow specifying a user, otherwise use the current user
        target_user = request.user
        if is_admin(request.user):
            user_id = request.POST.get('user_id')
            if user_id:
                target_user = User.objects.get(id=user_id)

        return EscrowReportingService.generate_investment_report(target_user, start_date, end_date)

    context = {
        'is_admin': is_admin(request.user),
        'users': User.objects.all() if is_admin(request.user) else None
    }
    return render(request, 'core/reports/investment_report.html', context)

@login_required
@user_passes_test(is_admin)
def platform_stats_report(request):
    """Generate platform statistics (admin only)"""
    return EscrowReportingService.generate_platform_stats() 