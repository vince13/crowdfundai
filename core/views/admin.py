from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Sum, Q, Count
from ..models import (
    AppListing, User, Investment, Transaction, Report, 
    ContentModeration, ProjectMilestone, EscrowTransaction, 
    Dispute, Release, Advertisement, DeveloperPaymentInfo, ProjectRequest,
    SubscriptionPlan, Subscription, SubscriptionFeatureUsage, PlatformFeeTransaction,
    CommunityVote, AppComment, EngagementAdjustmentLog, Blog
)
from ..decorators.admin_required import admin_required
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from django.core.mail import send_mail
from django.http import JsonResponse
from ..services.subscription import SubscriptionService
from ..services.analytics import AdvancedAnalyticsService
from django.db.models.functions import TruncMonth
from ..forms import AppEngagementForm  # Import all forms from core/forms.py

def is_admin(user):
    return user.is_authenticated and user.role == User.Role.ADMIN

@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    """Admin dashboard view."""
    # Get platform statistics
    total_users = User.objects.count()
    total_developers = User.objects.filter(role='DEVELOPER').count()
    total_investors = User.objects.filter(role='INVESTOR').count()
    
    # App statistics
    total_apps = AppListing.objects.count()
    pending_apps = AppListing.objects.filter(status='PENDING').count()
    active_apps = AppListing.objects.filter(status='ACTIVE').count()
    funded_apps = AppListing.objects.filter(status='FUNDED').count()
    
    # Investment statistics
    total_investments = Investment.objects.count()
    
    # Get disputes
    disputes = Dispute.objects.all().order_by('-created_at')[:5]
    pending_disputes_count = Dispute.objects.filter(status='PENDING').count()
    escalated_disputes_count = Dispute.objects.filter(status='ESCALATED').count()
    
    # Get release requests
    pending_release_requests = Release.objects.filter(status=Release.Status.PENDING)
    pending_release_requests_count = pending_release_requests.count()
    approved_release_requests_count = Release.objects.filter(status=Release.Status.APPROVED).count()
    pending_release_requests_amount = pending_release_requests.aggregate(total=Sum('amount'))['total'] or 0
    
    # Get unverified payment accounts count
    unverified_payment_accounts_count = DeveloperPaymentInfo.objects.filter(
        verification_status__in=['pending', 'under_review']
    ).count()
    
    # Pending Advertisements
    pending_ads = Advertisement.objects.filter(status='PENDING').order_by('-created_at')
    
    return render(request, 'core/admin/dashboard.html', {
        'stats': {
            'users': {
                'total': total_users,
                'developers': total_developers,
                'investors': total_investors,
            },
            'apps': {
                'total': total_apps,
                'pending': pending_apps,
                'active': active_apps,
                'funded': funded_apps,
            },
            'investments': {
                'total': total_investments,
            }
        },
        'pending_reports_count': Report.objects.filter(status=Report.ReportStatus.PENDING).count(),
        'flagged_content_count': ContentModeration.objects.filter(
            status=ContentModeration.ModerationStatus.FLAGGED
        ).count(),
        'disputes': disputes,
        'pending_disputes_count': pending_disputes_count,
        'escalated_disputes_count': escalated_disputes_count,
        'pending_release_requests_count': pending_release_requests_count,
        'approved_release_requests_count': approved_release_requests_count,
        'pending_release_requests_amount': pending_release_requests_amount,
        'pending_ads': pending_ads,
        'unverified_payment_accounts_count': unverified_payment_accounts_count,
    })

@login_required
@user_passes_test(is_admin)
def pending_apps(request):
    # Get pending apps
    apps = AppListing.objects.filter(
        status=AppListing.Status.PENDING
    ).order_by('-created_at')
    
    # Get all apps with filters
    all_apps_query = AppListing.objects.all()
    
    # Apply filters if provided
    status_filter = request.GET.get('status')
    type_filter = request.GET.get('type')
    sort_by = request.GET.get('sort')
    
    if status_filter:
        all_apps_query = all_apps_query.filter(status=status_filter)
    
    if type_filter:
        all_apps_query = all_apps_query.filter(listing_type=type_filter)
    
    # Apply sorting
    if sort_by == 'oldest':
        all_apps_query = all_apps_query.order_by('created_at')
    elif sort_by == 'most_viewed':
        all_apps_query = all_apps_query.order_by('-view_count')
    elif sort_by == 'most_liked':
        all_apps_query = all_apps_query.order_by('-like_count')
    else:  # newest first by default
        all_apps_query = all_apps_query.order_by('-created_at')
    
    return render(request, 'core/admin/pending_apps.html', {
        'apps': apps,
        'all_apps': all_apps_query,
    })

@login_required
@user_passes_test(is_admin)
def review_app(request, pk):
    """Review a pending app listing."""
    app = get_object_or_404(AppListing, pk=pk)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        feedback = request.POST.get('feedback')
        
        if action == 'approve':
            app.status = AppListing.Status.ACTIVE
            app.save()
            
            # Send approval notification
            from ..services.notifications import NotificationService
            NotificationService.notify_app_approval(app)
            
            messages.success(request, f'App "{app.name}" has been approved.')
            if feedback:
                messages.info(request, f'Feedback sent to developer: {feedback}')
        elif action == 'reject':
            app.status = AppListing.Status.REJECTED
            app.save()
            
            # Send rejection notification
            from ..services.notifications import NotificationService
            NotificationService.notify_app_rejection(app, feedback or "No specific feedback provided")
            
            messages.warning(request, f'App "{app.name}" has been rejected.')
            if feedback:
                messages.info(request, f'Feedback sent to developer: {feedback}')
        
        if feedback:
            app.admin_feedback = feedback
            app.save()
        
        return redirect('core:admin_pending_apps')
    
    # Calculate total milestone percentage
    milestone_total = sum(milestone.release_percentage for milestone in app.milestones.all())
    
    context = {
        'app': app,
        'milestone_total': milestone_total,
        'page_title': f'Review App: {app.name}'
    }
    return render(request, 'core/admin/review_app.html', context)

@login_required
@user_passes_test(is_admin)
def manage_users(request):
    users = User.objects.all().order_by('-date_joined')
    return render(request, 'core/admin/users.html', {
        'users': users
    })

@login_required
@user_passes_test(is_admin)
def user_details(request, pk):
    user = get_object_or_404(User, pk=pk)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'activate':
            user.is_active = True
            messages.success(request, f'User {user.username} has been activated.')
        elif action == 'deactivate':
            user.is_active = False
            messages.warning(request, f'User {user.username} has been deactivated.')
        elif action == 'change_role':
            new_role = request.POST.get('role')
            if new_role in [User.Role.ADMIN, User.Role.DEVELOPER, User.Role.INVESTOR]:
                old_role = user.role
                user.role = new_role
                messages.success(request, f'User {user.username} role changed from {old_role} to {new_role}.')
        
        user.save()
        return redirect('core:admin_manage_users')
    
    # Get user statistics
    stats = {
        'apps_created': AppListing.objects.filter(developer=user).count(),
        'investments_made': Investment.objects.filter(investor=user).count(),
        'total_invested': Investment.objects.filter(investor=user).aggregate(
            total=Sum('amount_paid')
        )['total'] or 0,
    }
    
    return render(request, 'core/admin/user_details.html', {
        'user_profile': user,
        'stats': stats,
        'available_roles': User.Role.choices
    })

@staff_member_required
def verify_milestone(request, milestone_id):
    """Admin view to verify milestone completion and approve fund release."""
    milestone = get_object_or_404(ProjectMilestone, pk=milestone_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'approve':
            can_complete, message = milestone.verify_completion()
            if can_complete:
                # Mark milestone as completed
                milestone.mark_completed()
                
                # Process fund release
                escrow_transactions = milestone.app.escrowtransaction_set.filter(
                    transaction_type='DEPOSIT',
                    status='COMPLETED'
                )
                
                for transaction in escrow_transactions:
                    try:
                        transaction.process_milestone_release(milestone)
                    except Exception as e:
                        messages.error(request, f'Error processing release: {str(e)}')
                        return redirect('admin:verify_milestone', milestone_id=milestone_id)
                
                messages.success(request, 'Milestone verified and funds released successfully')
            else:
                messages.error(request, f'Cannot complete milestone: {message}')
        
        elif action == 'reject':
            reason = request.POST.get('rejection_reason')
            if not reason:
                messages.error(request, 'Rejection reason is required')
                return redirect('admin:verify_milestone', milestone_id=milestone_id)
            
            # Update milestone status and notify developer
            milestone.status = 'DELAYED'
            milestone.save()
            
            # Add rejection note (implement notification system)
            # notify_developer(milestone, reason)
            
            messages.success(request, 'Milestone verification rejected')
        
        return redirect('admin:index')
    
    context = {
        'milestone': milestone,
        'app': milestone.app,
        'deliverables': milestone.deliverables.all(),
        'release_amount': milestone.calculate_remaining_funds()
    }
    
    return render(request, 'admin/verify_milestone.html', context)

@staff_member_required
def admin_investments(request):
    """View for admins to see all investments"""
    # Get all investments with related data
    investments = Investment.objects.select_related(
        'investor', 
        'app'
    ).order_by('-created_at')
    
    # Handle search
    search_query = request.GET.get('search', '')
    if search_query:
        investments = investments.filter(
            Q(investor__username__icontains=search_query) |
            Q(investor__email__icontains=search_query) |
            Q(app__name__icontains=search_query)
        )
    
    # Handle filters
    app_filter = request.GET.get('app')
    if app_filter:
        investments = investments.filter(app_id=app_filter)
        
    investor_filter = request.GET.get('investor')
    if investor_filter:
        investments = investments.filter(investor_id=investor_filter)
    
    # Get unique apps and investors for filter dropdowns
    apps = AppListing.objects.filter(
        id__in=Investment.objects.values('app_id').distinct()
    )
    investors = User.objects.filter(
        id__in=Investment.objects.values('investor_id').distinct()
    )
    
    # Calculate totals
    total_invested = investments.aggregate(
        total=Sum('amount_paid')
    )['total'] or 0
    
    context = {
        'investments': investments,
        'apps': apps,
        'investors': investors,
        'total_invested': total_invested,
        'search_query': search_query,
        'app_filter': app_filter,
        'investor_filter': investor_filter
    }
    
    return render(request, 'core/admin/investments.html', context)

@login_required
@user_passes_test(is_admin)
def verify_payment_accounts(request):
    """Admin view for verifying developer payment accounts."""
    # Get accounts by status
    unverified_accounts = DeveloperPaymentInfo.objects.filter(
        verification_status__in=['pending', 'under_review']
    ).select_related('developer')
    
    verified_accounts = DeveloperPaymentInfo.objects.filter(
        verification_status='verified'
    ).select_related('developer')
    
    rejected_accounts = DeveloperPaymentInfo.objects.filter(
        verification_status='rejected'
    ).select_related('developer')
    
    if request.method == 'POST':
        account_id = request.POST.get('account_id')
        action = request.POST.get('action')
        notes = request.POST.get('notes', '')
        
        if account_id and action:
            try:
                payment_info = DeveloperPaymentInfo.objects.get(id=account_id)
                
                if action == 'verify':
                    payment_info.verified = True
                    payment_info.verification_status = 'verified'
                    payment_info.verification_notes = notes
                    payment_info.verified_by = request.user
                    payment_info.verified_at = timezone.now()
                    payment_info.save()
                    
                    # Send email notification to developer
                    send_mail(
                        'Payment Account Verified',
                        f'Your payment account has been verified. You can now receive payments through our platform.',
                        'noreply@example.com',
                        [payment_info.developer.email],
                        fail_silently=True,
                    )
                    
                    messages.success(request, f'Payment account for {payment_info.developer.username} has been verified.')
                    
                elif action == 'reject':
                    if not notes:
                        messages.error(request, 'Please provide rejection reason')
                        return redirect('core:verify_payment_accounts')
                        
                    payment_info.verification_status = 'rejected'
                    payment_info.verification_notes = notes
                    payment_info.rejected_by = request.user
                    payment_info.rejected_at = timezone.now()
                    payment_info.save()
                    
                    # Send email notification to developer
                    send_mail(
                        'Payment Account Verification Failed',
                        f'Your payment account verification was rejected. Reason: {notes}',
                        'noreply@example.com',
                        [payment_info.developer.email],
                        fail_silently=True,
                    )
                    
                    messages.success(request, f'Payment account for {payment_info.developer.username} has been rejected.')
                    
            except DeveloperPaymentInfo.DoesNotExist:
                messages.error(request, 'Payment account not found.')
    
    return render(request, 'core/admin/verify_payments.html', {
        'unverified_accounts': unverified_accounts,
        'verified_accounts': verified_accounts,
        'rejected_accounts': rejected_accounts
    })

@user_passes_test(is_admin)
def project_requests(request):
    """View all project requests"""
    requests = ProjectRequest.objects.all()
    
    # Filter by status if provided
    status = request.GET.get('status')
    if status:
        requests = requests.filter(status=status)
    
    return render(request, 'core/admin/project_requests.html', {
        'requests': requests,
        'current_status': status,
        'statuses': ProjectRequest.Status.choices
    })

@user_passes_test(is_admin)
def project_request_detail(request, pk):
    """View and manage a single project request"""
    project_request = get_object_or_404(ProjectRequest, pk=pk)
    
    if request.method == 'POST':
        # Update status and notes
        status = request.POST.get('status')
        notes = request.POST.get('admin_notes')
        
        if status:
            project_request.status = status
        if notes is not None:
            project_request.admin_notes = notes
            
        project_request.save()
        messages.success(request, 'Project request updated successfully.')
        
        return redirect('core:admin_project_request_detail', pk=pk)
    
    return render(request, 'core/admin/project_request_detail.html', {
        'request': project_request,
        'statuses': ProjectRequest.Status.choices
    })

@login_required
@user_passes_test(is_admin)
def admin_subscriptions(request):
    """View for managing subscriptions and subscription plans"""
    subscription_plans = SubscriptionPlan.objects.all().order_by('tier', '-price')
    user_subscriptions = Subscription.objects.select_related('user').all().order_by('-start_date')
    
    # Get usage records
    usage_records = SubscriptionFeatureUsage.objects.select_related(
        'subscription', 'subscription__user'
    ).order_by('-last_used')

    # Get usage analytics
    analytics = {}
    for record in usage_records:
        feature = record.feature_name
        if feature not in analytics:
            analytics[feature] = {
                'total_daily_usage': 0,
                'total_monthly_usage': 0,
                'users_near_limit': 0,
                'users_at_limit': 0
            }
        
        analytics[feature]['total_daily_usage'] += record.daily_usage
        analytics[feature]['total_monthly_usage'] += record.monthly_usage
        
        # Calculate status
        limits = record.get_usage_limits()
        daily_limit = limits['daily_limit']
        record.status = 'normal'
        record.status_class = 'success'
        
        if record.daily_usage >= daily_limit:
            analytics[feature]['users_at_limit'] += 1
            record.status = 'at_limit'
            record.status_class = 'danger'
        elif record.daily_usage >= (daily_limit * 0.85):
            analytics[feature]['users_near_limit'] += 1
            record.status = 'near_limit'
            record.status_class = 'warning'
    
    # Get plan metrics
    subscription_service = SubscriptionService()
    metrics = subscription_service.get_plan_metrics()
    revenue_data = subscription_service.get_subscription_revenue()
    
    context = {
        'subscription_plans': subscription_plans,
        'user_subscriptions': user_subscriptions,
        'usage_records': usage_records,
        'analytics': analytics,
        'plan_metrics': metrics.get('metrics', []),
        'total_revenue': revenue_data.get('total_revenue', 0),
        'revenue_by_tier': revenue_data.get('revenue_by_tier', {})
    }
    
    return render(request, 'core/admin/subscriptions.html', context)

@login_required
@user_passes_test(is_admin)
def admin_create_plan(request):
    """Create a new subscription plan"""
    if request.method == 'POST':
        try:
            features = request.POST.get('features').split('\n')
            features = [f.strip() for f in features if f.strip()]
            
            plan = SubscriptionPlan.objects.create(
                name=request.POST.get('name'),
                tier=request.POST.get('tier'),
                price=request.POST.get('price'),
                description=request.POST.get('description'),
                features=features,
                is_active=request.POST.get('is_active') == 'on'
            )
            messages.success(request, f'Successfully created plan: {plan.name}')
        except Exception as e:
            messages.error(request, f'Failed to create plan: {str(e)}')
    
    return redirect('core:admin_subscriptions')

@login_required
@user_passes_test(is_admin)
def admin_edit_plan(request, plan_id):
    """Edit an existing subscription plan"""
    plan = get_object_or_404(SubscriptionPlan, id=plan_id)
    
    if request.method == 'POST':
        try:
            features = request.POST.get('features').split('\n')
            features = [f.strip() for f in features if f.strip()]
            
            plan.name = request.POST.get('name')
            plan.tier = request.POST.get('tier')
            plan.price = request.POST.get('price')
            plan.description = request.POST.get('description')
            plan.features = features
            plan.is_active = request.POST.get('is_active') == 'on'
            plan.save()
            
            messages.success(request, f'Successfully updated plan: {plan.name}')
        except Exception as e:
            messages.error(request, f'Failed to update plan: {str(e)}')
    
    return redirect('core:admin_subscriptions')

@login_required
@user_passes_test(is_admin)
def admin_delete_plan(request, plan_id):
    """Delete a subscription plan"""
    plan = get_object_or_404(SubscriptionPlan, id=plan_id)
    
    if request.method == 'POST':
        try:
            name = plan.name
            plan.delete()
            messages.success(request, f'Successfully deleted plan: {name}')
        except Exception as e:
            messages.error(request, f'Failed to delete plan: {str(e)}')
    
    return redirect('core:admin_subscriptions')

@login_required
@user_passes_test(is_admin)
def admin_edit_subscription(request, subscription_id):
    """Edit a user's subscription"""
    subscription = get_object_or_404(Subscription, id=subscription_id)
    
    if request.method == 'POST':
        try:
            subscription.tier = request.POST.get('tier')
            subscription.is_active = request.POST.get('is_active') == 'on'
            subscription.auto_renew = request.POST.get('auto_renew') == 'on'
            
            end_date = request.POST.get('end_date')
            if end_date:
                subscription.end_date = end_date
            
            subscription.save()
            messages.success(request, f'Successfully updated subscription for {subscription.user.email}')
        except Exception as e:
            messages.error(request, f'Failed to update subscription: {str(e)}')
    
    return redirect('core:admin_subscriptions')

@login_required
@user_passes_test(is_admin)
def admin_cancel_subscription(request, subscription_id):
    """Cancel a user's subscription"""
    if request.method == 'POST':
        subscription = get_object_or_404(Subscription, id=subscription_id)
        try:
            subscription_service = SubscriptionService()
            result = subscription_service.cancel_subscription(subscription)
            
            if result.get('success'):
                messages.success(request, f'Successfully cancelled subscription for {subscription.user.email}')
                return JsonResponse({'success': True})
            else:
                return JsonResponse({
                    'success': False, 
                    'error': result.get('error', 'Failed to cancel subscription')
                })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
@user_passes_test(is_admin)
def subscription_usage_tracking(request):
    """Admin view for subscription usage tracking."""
    # Get all feature usage records
    usage_records = SubscriptionFeatureUsage.objects.select_related(
        'subscription', 'subscription__user'
    ).order_by('-last_used')

    # Get usage analytics
    analytics = {}
    
    # Process each record and add status
    for record in usage_records:
        # Get feature analytics
        feature = record.feature_name
        if feature not in analytics:
            analytics[feature] = {
                'total_daily_usage': 0,
                'total_monthly_usage': 0,
                'users_near_limit': 0,
                'users_at_limit': 0
            }
        
        analytics[feature]['total_daily_usage'] += record.daily_usage
        analytics[feature]['total_monthly_usage'] += record.monthly_usage
        
        # Calculate status
        limits = record.get_usage_limits()
        daily_limit = limits['daily_limit']
        near_limit_threshold = daily_limit * 0.85
        
        if record.daily_usage >= daily_limit:
            analytics[feature]['users_at_limit'] += 1
            record.status = 'at_limit'
            record.status_class = 'danger'
        elif record.daily_usage >= near_limit_threshold:
            analytics[feature]['users_near_limit'] += 1
            record.status = 'near_limit'
            record.status_class = 'warning'
        else:
            record.status = 'normal'
            record.status_class = 'success'

    return render(request, 'core/admin/subscription_usage.html', {
        'usage_records': usage_records,
        'analytics': analytics
    })

@login_required
@user_passes_test(is_admin)
def subscription_analytics(request):
    """Advanced subscription analytics view."""
    analytics_service = AdvancedAnalyticsService()
    
    context = {
        'churn_metrics': analytics_service.get_churn_metrics(),
        'retention_metrics': analytics_service.get_retention_metrics(),
        'clv_metrics': analytics_service.get_customer_lifetime_value(),
        'growth_trends': analytics_service.get_growth_trends()
    }
    
    return render(request, 'core/admin/subscription_analytics.html', context)

@login_required
@user_passes_test(is_admin)
def platform_fee_dashboard(request):
    """Admin view for platform fee management."""
    # Get all platform fee transactions
    platform_fees = PlatformFeeTransaction.objects.all()
    
    # Calculate total fees
    total_fees = platform_fees.aggregate(
        total=Sum('amount'),
        count=Count('id')
    )
    
    # Calculate fees by status
    fees_by_status = platform_fees.values('status').annotate(
        total=Sum('amount'),
        count=Count('id')
    )
    
    # Get monthly fee trends
    monthly_fees = platform_fees.annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('-month')
    
    # Get recent fee transactions
    recent_transactions = platform_fees.select_related('app').order_by('-created_at')[:10]
    
    # Calculate collection rate
    total_expected = platform_fees.count()
    total_collected = platform_fees.filter(status='COMPLETED').count()
    collection_rate = (total_collected / total_expected * 100) if total_expected > 0 else 0
    
    context = {
        'total_fees': total_fees,
        'fees_by_status': fees_by_status,
        'monthly_fees': monthly_fees,
        'recent_transactions': recent_transactions,
        'collection_rate': collection_rate,
        'stats': {
            'pending': platform_fees.filter(status='PENDING').aggregate(
                total=Sum('amount'),
                count=Count('id')
            ),
            'completed': platform_fees.filter(status='COMPLETED').aggregate(
                total=Sum('amount'),
                count=Count('id')
            ),
            'failed': platform_fees.filter(status='FAILED').aggregate(
                total=Sum('amount'),
                count=Count('id')
            )
        }
    }
    
    return render(request, 'core/admin/platform_fees.html', context)

@login_required
@admin_required
def base_template_view(request):
    """View for managing base template settings."""
    context = {
        'page_title': 'Base Template Management',
        'active_section': 'base_template'
    }
    return render(request, 'core/admin/base_template.html', context)

@login_required
@user_passes_test(is_admin)
def admin_manage_metrics(request, pk):
    """Manage engagement metrics for an app."""
    app = get_object_or_404(AppListing, pk=pk)
    
    if request.method == 'POST':
        if 'update_trending' in request.POST:
            is_trending = request.POST.get('is_trending') == 'on'
            app.manual_trending = is_trending
            app.last_trending_update = timezone.now()
            app.save(update_fields=['manual_trending', 'last_trending_update'])
            status = "trending" if is_trending else "not trending"
            messages.success(request, f"Successfully updated {app.name} to {status}")
            return redirect('core:admin_manage_metrics', pk=pk)
        elif 'update_video' in request.POST:
            # Handle video link update
            video_link = request.POST.get('nomination_external_link')
            app.nomination_external_link = video_link
            app.save(update_fields=['nomination_external_link'])
            messages.success(request, f"Successfully updated video link for {app.name}")
            return redirect('core:admin_manage_metrics', pk=pk)
        else:
            form = AppEngagementForm(request.POST)
            if form.is_valid():
                add_views = form.cleaned_data.get('add_views', 0)
                add_likes = form.cleaned_data.get('add_likes', 0)
                add_upvotes = form.cleaned_data.get('add_upvotes', 0)
                add_comments = form.cleaned_data.get('add_comments', 0)
                engagement_note = form.cleaned_data.get('engagement_note', '')

                # Update view count
                if add_views:
                    app.view_count += add_views

                # Add system likes
                if add_likes:
                    app.system_like_count += add_likes

                # Add system upvotes
                if add_upvotes:
                    app.system_upvote_count += add_upvotes

                # Add system comments
                if add_comments:
                    for i in range(add_comments):
                        AppComment.objects.create(
                            app=app,
                            user=request.user,
                            content=f"This is a promising initiative! #{i+1}",
                            created_at=timezone.now(),
                            is_system_generated=True
                        )
                    app.system_comment_count = (app.system_comment_count or 0) + add_comments
                
                # Save all the updated counts
                update_fields = ['view_count', 'system_like_count', 'system_upvote_count']
                if add_comments:
                    update_fields.append('system_comment_count')
                
                app.save(update_fields=update_fields)

                # Log the engagement adjustment
                EngagementAdjustmentLog.objects.create(
                    app=app,
                    admin=request.user,
                    views_added=add_views,
                    likes_added=add_likes,
                    upvotes_added=add_upvotes,
                    comments_added=add_comments,
                    note=engagement_note
                )

                messages.success(request, f"Successfully updated engagement metrics for {app.name}")
                return redirect('core:admin_manage_metrics', pk=pk)
    else:
        form = AppEngagementForm()

    # Calculate current metrics
    likes_count = app.get_total_likes()
    upvotes_count = app.get_total_upvotes()
    
    # Get recent adjustments
    adjustment_logs = EngagementAdjustmentLog.objects.filter(
        app=app
    ).order_by('-created_at')[:5]

    # Get all published blog posts
    blog_posts = Blog.objects.filter(status='published').order_by('-published_at')

    return render(request, 'core/admin/manage_engagement_metrics.html', {
        'app': app,
        'form': form,
        'page_title': f'Manage Metrics: {app.name}',
        'like_count': likes_count,
        'upvote_count': upvotes_count,
        'adjustment_logs': adjustment_logs,
        'blog_posts': blog_posts  # Add blog posts to context
    })

@login_required
@user_passes_test(is_admin)
def admin_view_analytics(request, pk):
    """View analytics for a specific app."""
    app = get_object_or_404(AppListing, pk=pk)
    
    # Get analytics data
    analytics_service = AdvancedAnalyticsService()
    analytics_data = analytics_service.get_app_analytics(app)
    
    context = {
        'app': app,
        'analytics': analytics_data,
        'page_title': f'Analytics: {app.name}'
    }
    return render(request, 'core/admin/view_analytics.html', context) 