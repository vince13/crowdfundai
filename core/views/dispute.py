from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q
from django.views.decorators.http import require_POST
from django.urls import reverse

from ..models import Dispute, DisputeEvidence, DisputeComment, Transaction
from ..decorators.staff_required import staff_required

@login_required
def dispute_list(request):
    """List disputes for the current user or all disputes for staff."""
    if request.user.is_staff:
        disputes = Dispute.objects.all()
    else:
        # Show disputes to users who raised them and developers of the disputed apps
        disputes = Dispute.objects.filter(
            Q(raised_by=request.user) |
            Q(transaction__app__developer=request.user)
        ).distinct()

    # Filter parameters
    status = request.GET.get('status', '')
    dispute_type = request.GET.get('type', '')
    search = request.GET.get('search', '')

    # Only apply filters if they have actual values
    if status and status.strip():
        disputes = disputes.filter(status=status)
    if dispute_type and dispute_type.strip():
        disputes = disputes.filter(dispute_type=dispute_type)
    if search and search.strip() and search.lower() != 'none':
        disputes = disputes.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(transaction__app__name__icontains=search) |
            Q(raised_by__username__icontains=search) |
            Q(raised_by__first_name__icontains=search) |
            Q(raised_by__last_name__icontains=search) |
            Q(id__icontains=search)
        ).distinct()

    # Pagination
    paginator = Paginator(disputes.order_by('-created_at'), 10)
    page = request.GET.get('page', 1)
    disputes = paginator.get_page(page)

    context = {
        'disputes': disputes,
        'status_choices': Dispute.Status.choices,
        'type_choices': Dispute.Type.choices,
        'current_status': status,
        'current_type': dispute_type,
        'search_query': search if search.lower() != 'none' else ''
    }
    return render(request, 'core/dispute/list.html', context)

@login_required
def dispute_detail(request, dispute_id):
    """View dispute details and handle comments."""
    if request.user.is_staff:
        dispute = get_object_or_404(Dispute, id=dispute_id)
    else:
        dispute = get_object_or_404(Dispute, id=dispute_id, raised_by=request.user)

    if request.method == 'POST':
        content = request.POST.get('content')
        is_internal = request.POST.get('is_internal') == 'on' and request.user.is_staff
        
        if content:
            DisputeComment.objects.create(
                dispute=dispute,
                author=request.user,
                content=content,
                is_internal=is_internal
            )
            messages.success(request, 'Comment added successfully.')
            return redirect('core:dispute_detail', dispute_id=dispute.id)

    # Get comments based on user role
    if request.user.is_staff:
        comments = dispute.comments.all()
        # Get previous disputes by the same user (excluding current dispute)
        previous_disputes = Dispute.objects.filter(
            raised_by=dispute.raised_by
        ).exclude(
            id=dispute.id
        ).order_by('-created_at')
    else:
        comments = dispute.comments.filter(is_internal=False)
        previous_disputes = None

    context = {
        'dispute': dispute,
        'comments': comments,
        'evidence': dispute.evidence.all(),
        'previous_disputes': previous_disputes
    }
    return render(request, 'core/dispute/detail.html', context)

@login_required
def create_dispute(request):
    """Create a new dispute."""
    if request.method == 'POST':
        transaction_id = request.POST.get('transaction_id')
        transaction = get_object_or_404(Transaction, id=transaction_id, user=request.user)

        dispute = Dispute.objects.create(
            transaction=transaction,
            raised_by=request.user,
            dispute_type=request.POST.get('dispute_type'),
            title=request.POST.get('title'),
            description=request.POST.get('description'),
            amount_in_dispute=request.POST.get('amount_in_dispute')
        )
        
        messages.success(request, 'Dispute created successfully.')
        return redirect('core:dispute_detail', dispute_id=dispute.id)

    context = {
        'type_choices': Dispute.Type.choices,
        'transactions': Transaction.objects.filter(user=request.user).order_by('-created_at')
    }
    return render(request, 'core/dispute/create.html', context)

@login_required
def upload_evidence(request, dispute_id):
    """Upload evidence for a dispute."""
    try:
        if request.user.is_staff:
            dispute = get_object_or_404(Dispute, id=dispute_id)
        else:
            dispute = get_object_or_404(Dispute, id=dispute_id, raised_by=request.user)
        
        if request.method == 'POST' and request.FILES.get('file'):
            evidence = DisputeEvidence.objects.create(
                dispute=dispute,
                uploaded_by=request.user,
                title=request.POST.get('title', 'Evidence'),
                description=request.POST.get('description', ''),
                file=request.FILES['file']
            )
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success',
                    'evidence_id': evidence.id,
                    'file_url': evidence.file.url
                })
                
            messages.success(request, 'Evidence uploaded successfully.')
            return redirect('core:dispute_detail', dispute_id=dispute.id)
            
        return render(request, 'core/dispute/evidence.html', {'dispute': dispute})
        
    except Dispute.DoesNotExist:
        messages.error(request, 'Dispute not found or you do not have permission to access it.')
        return redirect('core:dispute_list')

@login_required
def manage_dispute(request, dispute_id):
    """View for managing disputes by staff and app developers."""
    dispute = get_object_or_404(Dispute, id=dispute_id)
    
    # Check if user has permission to manage this dispute
    if not (request.user.is_staff or dispute.transaction.app.developer == request.user):
        messages.error(request, 'You do not have permission to manage this dispute.')
        return redirect('core:dispute_detail', dispute_id=dispute.id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # Only staff can perform certain actions
        if not request.user.is_staff and action in ['assign', 'escalate', 'close']:
            messages.error(request, 'You do not have permission to perform this action.')
            return redirect('core:dispute_detail', dispute_id=dispute.id)
        
        # Validate state transitions
        if action == 'assign':
            if dispute.status != Dispute.Status.PENDING:
                messages.error(request, 'Only pending disputes can be assigned.')
            else:
                dispute.assign_to(request.user)
                messages.success(request, 'Dispute assigned to you.')
            
        elif action == 'resolve':
            if dispute.status not in [Dispute.Status.IN_REVIEW, Dispute.Status.ESCALATED]:
                messages.error(request, 'Only disputes under review or escalated can be resolved.')
            else:
                resolution_text = request.POST.get('resolution')
                resolution_type = request.POST.get('resolution_type')
                if resolution_text and resolution_type:
                    dispute.resolve(resolution_text, resolution_type, request.user)
                    messages.success(request, 'Dispute resolved successfully.')
            
        elif action == 'escalate':
            if dispute.status != Dispute.Status.IN_REVIEW:
                messages.error(request, 'Only disputes under review can be escalated.')
            else:
                dispute.escalate()
                messages.success(request, 'Dispute escalated.')
            
        elif action == 'close':
            if dispute.status != Dispute.Status.RESOLVED:
                messages.error(request, 'Only resolved disputes can be closed.')
            else:
                dispute.close()
                messages.success(request, 'Dispute closed.')
        
        return redirect('core:dispute_detail', dispute_id=dispute.id)
    
    context = {
        'dispute': dispute,
        'comments': dispute.comments.all(),
        'evidence': dispute.evidence.all(),
        'is_staff': request.user.is_staff
    }
    return render(request, 'core/dispute/manage.html', context)

@require_POST
@staff_required
def delete_evidence(request, evidence_id):
    """Delete dispute evidence (staff only)."""
    evidence = get_object_or_404(DisputeEvidence, id=evidence_id)
    dispute_id = evidence.dispute.id
    evidence.delete()
    
    messages.success(request, 'Evidence deleted successfully.')
    return redirect('core:dispute_detail', dispute_id=dispute_id) 