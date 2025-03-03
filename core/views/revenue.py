from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView, DetailView
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from core.models import AppListing, Revenue
from core.services.revenue.distribution import RevenueDistributionService
from core.services.revenue.tracking import RevenueTrackingService
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.mixins import LoginRequiredMixin
import csv
from decimal import Decimal
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.core.exceptions import ValidationError
import json
from django.utils.dateparse import parse_datetime

@method_decorator(login_required, name='dispatch')
class RevenueDashboardView(TemplateView):
    template_name = 'core/revenue/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get user's apps
        apps = AppListing.objects.filter(developer=self.request.user)
        tracking_service = RevenueTrackingService()
        
        # Calculate revenue metrics for each app
        apps_with_revenue = []
        total_revenue = Decimal('0')
        total_monthly = Decimal('0')
        total_pending = Decimal('0')
        
        for app in apps:
            # Get revenue metrics for this app
            app_total = tracking_service.get_total_revenue(app)
            app_monthly = tracking_service.get_monthly_revenue(app)
            app_pending = tracking_service.get_pending_distributions(app)
            app_failed = tracking_service.get_failed_distributions(app)
            
            # Get current month's revenue
            current_month = timezone.now().strftime('%Y-%m')
            current_month_revenue = app_monthly.get(current_month, Decimal('0'))
            
            # Add revenue data to app object
            app.total_revenue = app_total
            app.monthly_revenue = current_month_revenue
            app.pending_distributions = app_pending
            app.failed_distributions = app_failed
            
            # Add to totals
            total_revenue += app.total_revenue
            total_monthly += app.monthly_revenue
            total_pending += app.pending_distributions
            
            apps_with_revenue.append(app)
        
        # Update context
        context.update({
            'apps': apps_with_revenue,
            'total_revenue': total_revenue,
            'monthly_revenue': total_monthly,
            'pending_distributions': total_pending,
            'currency': 'NGN'  # Default currency
        })
        
        return context

class RevenueDetailView(LoginRequiredMixin, DetailView):
    model = AppListing
    template_name = 'core/revenue/detail.html'
    context_object_name = 'app'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        app = self.get_object()
        
        tracking_service = RevenueTrackingService()
        distribution_service = RevenueDistributionService()
        
        # Get total revenue (all time)
        context['total_revenue'] = tracking_service.get_total_revenue(app)
        
        # Get monthly revenue data
        monthly_revenue = tracking_service.get_monthly_revenue(app)
        
        # Get current month's revenue
        current_month = timezone.now().strftime('%Y-%m')
        context['monthly_revenue'] = monthly_revenue.get(current_month, Decimal('0'))
        
        # Get pending and failed distributions
        pending = tracking_service.get_pending_distributions(app)
        failed = tracking_service.get_failed_distributions(app)
        context['pending_distributions'] = pending + failed
        
        # Format monthly data for charts
        sorted_months = sorted(monthly_revenue.keys())
        context['monthly_labels'] = sorted_months
        context['monthly_data'] = [float(monthly_revenue[month]) for month in sorted_months]
        
        # Get recent distributions
        context['recent_distributions'] = distribution_service.get_distribution_history(app.id)[:5]
        
        # Add currency info
        context['currency'] = 'NGN'  # Default currency
        
        return context

@login_required
def process_distributions(request, pk):
    """Process pending distributions for an app"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
        
    app = get_object_or_404(AppListing, pk=pk, developer=request.user)
    distribution_service = RevenueDistributionService()
    
    try:
        distribution_service.schedule_distributions()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def retry_distribution(request):
    """Retry a failed distribution"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
        
    distribution_id = request.GET.get('id')
    if not distribution_id:
        return JsonResponse({'success': False, 'error': 'Distribution ID required'})
        
    distribution_service = RevenueDistributionService()
    
    try:
        distribution_service.retry_failed_distribution(distribution_id)
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def export_revenue_data(request, pk):
    """Export revenue data to CSV"""
    app = get_object_or_404(AppListing, pk=pk, developer=request.user)
    tracking_service = RevenueTrackingService()
    
    # Get date range from request
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    revenue_type = request.GET.get('revenue_type')
    
    # Get revenue data
    revenues = app.revenues.all()
    
    if start_date:
        revenues = revenues.filter(created_at__gte=start_date)
    if end_date:
        revenues = revenues.filter(created_at__lte=end_date)
    if revenue_type:
        revenues = revenues.filter(source=revenue_type)
        
    # Create the HttpResponse object with CSV header
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{app.name}_revenue_{timezone.now().date()}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Date', 'Amount (NGN)', 'Type', 'Description', 'Customers', 'Status'])
    
    for revenue in revenues:
        writer.writerow([
            revenue.created_at.date(),
            revenue.amount,
            revenue.get_source_display(),
            revenue.description,
            revenue.customer_count,
            'Distributed' if revenue.is_distributed else 'Pending'
        ])
    
    return response

@login_required
def record_revenue_form(request, app_id):
    """View for rendering the revenue recording form"""
    app = get_object_or_404(AppListing, pk=app_id, developer=request.user)
    return render(request, 'core/revenue/record.html', {'app': app})

@ensure_csrf_cookie
@require_http_methods(["POST"])
@login_required
def record_app_revenue(request, app_id):
    """API endpoint for recording app revenue"""
    try:
        # First check if app exists
        try:
            app = AppListing.objects.get(pk=app_id)
        except AppListing.DoesNotExist:
            return JsonResponse({'error': 'App not found'}, status=404)
            
        # Then check if user is the developer
        if app.developer != request.user:
            return JsonResponse({'error': 'Not authorized to record revenue for this app'}, status=403)
            
        data = json.loads(request.body)
        
        # Validate required fields
        if 'amount' not in data or 'source' not in data:
            return JsonResponse({
                'error': 'Amount and source are required fields'
            }, status=400)
        
        # Get required fields
        try:
            amount = Decimal(str(data.get('amount')))
        except (TypeError, ValueError, InvalidOperation):
            return JsonResponse({
                'error': 'Invalid amount value'
            }, status=400)
            
        source = data.get('source')
        if not source:
            return JsonResponse({
                'error': 'Source is required'
            }, status=400)
            
        description = data.get('description', '')
        
        # Handle date fields - convert from YYYY-MM-DD to datetime
        period_start = data.get('period_start')
        period_end = data.get('period_end')
        
        try:
            if period_start:
                period_start = timezone.datetime.strptime(period_start, '%Y-%m-%d')
                period_start = timezone.make_aware(period_start)
            else:
                period_start = timezone.now()
                
            if period_end:
                period_end = timezone.datetime.strptime(period_end, '%Y-%m-%d')
                period_end = timezone.make_aware(period_end)
            else:
                period_end = period_start + timezone.timedelta(days=1)  # Default to next day
                
            if period_start >= period_end:
                return JsonResponse({
                    'error': 'Period start must be before period end'
                }, status=400)
        except ValueError:
            return JsonResponse({
                'error': 'Invalid date format. Use YYYY-MM-DD'
            }, status=400)
        
        # Create revenue record
        try:
            revenue = Revenue.objects.create(
                app=app,
                amount=amount,
                currency='NGN',  # Hardcode to NGN
                source=source,
                description=description,
                period_start=period_start,
                period_end=period_end,
                metadata={'recorded_by': request.user.username},
                exchange_rate=Decimal('1.0')  # Default to 1.0 for NGN
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Revenue recorded successfully',
                'revenue_id': revenue.id
            })
        except ValidationError as e:
            return JsonResponse({'error': str(e)}, status=400)
            
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
@login_required
def verify_revenue(request, revenue_id):
    """Verify a revenue entry with proof"""
    try:
        revenue = get_object_or_404(Revenue, 
            id=revenue_id, 
            app__developer=request.user
        )
        
        data = json.loads(request.body)
        proof = data.get('proof')
        
        if not proof:
            return JsonResponse({
                'success': False,
                'error': 'Proof of revenue is required'
            }, status=400)
            
        # Update revenue with verification
        revenue.verification_proof = proof
        revenue.is_verified = True
        revenue.verified_at = timezone.now()
        revenue.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Revenue verified successfully'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@require_http_methods(["GET"])
@login_required
def revenue_sources(request):
    """Get available revenue sources"""
    return JsonResponse({
        'sources': [
            {'id': 'SUBSCRIPTION', 'name': 'Subscription'},
            {'id': 'ONE_TIME', 'name': 'One-time Purchase'},
            {'id': 'IN_APP', 'name': 'In-app Purchase'},
            {'id': 'API_USAGE', 'name': 'API Usage'},
            {'id': 'OTHER', 'name': 'Other'}
        ]
    }) 