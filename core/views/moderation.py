from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.db.models import Count
from django.utils import timezone
from ..models import Report, ContentModeration, ModerationLog
from ..services.moderation import ModerationService

def is_moderator(user):
    return user.is_authenticated and (user.is_staff or user.role == 'ADMIN')

@user_passes_test(is_moderator)
def moderation_dashboard(request):
    """Main moderation dashboard"""
    pending_reports = Report.objects.filter(status=Report.ReportStatus.PENDING)
    flagged_content = ContentModeration.objects.filter(
        status=ContentModeration.ModerationStatus.FLAGGED
    )
    recent_actions = ModerationLog.objects.all()[:10]

    context = {
        'pending_reports_count': pending_reports.count(),
        'flagged_content_count': flagged_content.count(),
        'recent_actions': recent_actions,
        'reports_by_reason': Report.objects.values('reason').annotate(count=Count('id')),
    }
    return render(request, 'core/moderation/dashboard.html', context)

@user_passes_test(is_moderator)
def report_list(request):
    """List all reports"""
    status_filter = request.GET.get('status', 'PENDING')
    reports = Report.objects.all()
    
    if status_filter != 'ALL':
        reports = reports.filter(status=status_filter)
    
    paginator = Paginator(reports, 20)
    page = request.GET.get('page', 1)
    reports = paginator.get_page(page)

    context = {
        'reports': reports,
        'status_filter': status_filter,
        'report_statuses': Report.ReportStatus.choices
    }
    return render(request, 'core/moderation/report_list.html', context)

@user_passes_test(is_moderator)
def report_detail(request, pk):
    """View and handle a specific report"""
    report = get_object_or_404(Report, pk=pk)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        notes = request.POST.get('notes', '')
        
        if action in ['APPROVE', 'REJECT', 'RESOLVE']:
            report.status = action
            report.moderator = request.user
            report.moderation_notes = notes
            report.moderated_at = timezone.now()
            report.save()
            
            # Update content moderation status
            ModerationService.review_content(
                report.content_object,
                request.user,
                ContentModeration.ModerationStatus.REJECTED if action == 'APPROVE' else ContentModeration.ModerationStatus.APPROVED,
                notes
            )
            
            messages.success(request, 'Report has been processed successfully.')
            return redirect('core:moderation_report_list')
    
    context = {
        'report': report,
        'content_object': report.content_object,
        'moderation_history': ModerationLog.objects.filter(
            content_type=report.content_type,
            object_id=report.object_id
        )
    }
    return render(request, 'core/moderation/report_detail.html', context)

@login_required
def report_content(request):
    """Submit a new content report"""
    if request.method == 'POST':
        content_type_id = request.POST.get('content_type')
        object_id = request.POST.get('object_id')
        reason = request.POST.get('reason')
        description = request.POST.get('description')
        
        try:
            content_type = ContentType.objects.get_for_id(content_type_id)
            content_object = content_type.get_object_for_this_type(id=object_id)
            
            report = ModerationService.report_content(
                content_object=content_object,
                reporter=request.user,
                reason=reason,
                description=description
            )
            
            messages.success(request, 'Content has been reported successfully.')
            return JsonResponse({'status': 'success'})
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

@user_passes_test(is_moderator)
def moderation_log(request):
    """View moderation history"""
    logs = ModerationLog.objects.all()
    paginator = Paginator(logs, 50)
    page = request.GET.get('page', 1)
    logs = paginator.get_page(page)
    
    context = {
        'logs': logs
    }
    return render(request, 'core/moderation/log.html', context) 