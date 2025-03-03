from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse
from django.core.exceptions import ValidationError
from decimal import Decimal, InvalidOperation
from django.utils import timezone

from ..models import EscrowRelease, ProjectMilestone
from ..services.approval import ApprovalService
from ..models.payment_info import DeveloperPaymentInfo
from ..services.payments import PaymentService

@login_required
def release_list(request):
    """List releases based on user role."""
    if request.user.is_staff:
        releases = EscrowRelease.objects.all()
    else:
        # Show releases for apps where user is the developer
        releases = EscrowRelease.objects.filter(
            app__developer=request.user
        ).distinct()

    # Filter parameters
    status = request.GET.get('status')
    search = request.GET.get('search')

    if status:
        releases = releases.filter(status=status)
    if search:
        releases = releases.filter(
            Q(app__name__icontains=search) |
            Q(milestone__title__icontains=search) |
            Q(notes__icontains=search)
        )

    # Pagination
    paginator = Paginator(releases.order_by('-created_at'), 10)
    page = request.GET.get('page', 1)
    releases = paginator.get_page(page)

    context = {
        'releases': releases,
        'status_choices': EscrowRelease.Status.choices,
        'current_status': status,
        'search_query': search
    }
    return render(request, 'core/release/list.html', context)

@login_required
def release_detail(request, release_id):
    """View release details."""
    if request.user.is_staff:
        release = get_object_or_404(EscrowRelease, id=release_id)
    else:
        # For non-staff, ensure they can only view releases they're involved with
        filters = Q(app__developer=request.user)
        release = get_object_or_404(EscrowRelease.objects.filter(filters), id=release_id)

    context = {
        'release': release,
        'can_approve': request.user.has_perm('core.can_approve_release'),
        'can_process': request.user.has_perm('core.can_process_release'),
        'can_request_approval': release.can_request_approval()
    }
    return render(request, 'core/release/detail.html', context)

@login_required
def create_release(request):
    """Create a new fund release request."""
    if request.method == 'POST':
        milestone_id = request.POST.get('milestone_id')
        amount = Decimal(request.POST.get('amount', '0'))
        notes = request.POST.get('notes', '')
        
        try:
            milestone = ProjectMilestone.objects.get(id=milestone_id)
            
            # Validate release request
            can_release, message = milestone.can_request_release(amount)
            if not can_release:
                messages.error(request, message)
                return redirect('core:create_release')
            
            # Create release request
            release = EscrowRelease.objects.create(
                app=milestone.app,
                milestone=milestone,
                amount=amount,
                requested_by=request.user,
                notes=notes
            )
            
            messages.success(request, 'Release request created successfully.')
            return redirect('core:release_detail', release.id)
            
        except ProjectMilestone.DoesNotExist:
            messages.error(request, 'Invalid milestone selected.')
        except Exception as e:
            messages.error(request, f'Error creating release request: {str(e)}')
        
        return redirect('core:create_release')
    
    # Get verified milestones eligible for release
    milestones = ProjectMilestone.objects.filter(
        app__developer=request.user,
        status=ProjectMilestone.Status.VERIFIED
    ).exclude(
        release_percentage=0
    ).select_related('app')
    
    context = {
        'milestones': milestones,
        'page_title': 'Request Fund Release'
    }
    return render(request, 'core/release/request_form.html', context)

@login_required
def request_approval(request, release_id):
    """Request approval for a release."""
    release = get_object_or_404(
        EscrowRelease,
        id=release_id,
        requested_by=request.user,
        status=EscrowRelease.Status.PENDING
    )
    
    try:
        ApprovalService.request_approval(release, request.user)
        messages.success(request, "Approval requested successfully.")
    except ValidationError as e:
        messages.error(request, str(e))
    
    return redirect('core:release_detail', release_id=release.id)

@login_required
@permission_required('core.can_approve_release')
def approve_release(request, release_id):
    """Approve or reject a release request."""
    release = get_object_or_404(EscrowRelease, id=release_id, status=EscrowRelease.Status.PENDING)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        notes = request.POST.get('notes', '')
        
        try:
            if action == 'approve':
                ApprovalService.approve(release, request.user, notes)
                messages.success(request, 'Release request approved successfully.')
            elif action == 'reject':
                ApprovalService.reject(release, request.user, notes)
                messages.success(request, 'Release request rejected.')
            else:
                messages.error(request, 'Invalid action specified.')
        except ValidationError as e:
            messages.error(request, str(e))
        
        return redirect('core:release_detail', release_id=release.id)
    
    context = {
        'release': release
    }
    return render(request, 'core/release/approval.html', context)

@login_required
@permission_required('core.can_process_release')
def process_release(request, release_id):
    """Process an approved release."""
    release = get_object_or_404(EscrowRelease, id=release_id, status=EscrowRelease.Status.APPROVED)
    
    if request.method == 'POST':
        try:
            # Start processing
            release.status = EscrowRelease.Status.PROCESSING
            release.processed_date = timezone.now()
            release.save()

            # Get developer's payment info
            payment_info = release.app.developer.payment_info
            if not payment_info.verified:
                raise ValidationError("Developer's payment account is not verified")

            # Initialize payment service
            payment_service = PaymentService()

            # Process payment based on payment method
            if payment_info.payment_method == 'paystack':
                # Create transfer recipient if needed
                account_details = payment_info.account_details
                if 'recipient_code' not in account_details:
                    recipient = PaymentService.create_transfer_recipient(
                        name=payment_info.developer.get_full_name() or payment_info.developer.username,
                        email=account_details['email'],
                        account_number=account_details['account_number'],
                        bank_code=account_details['bank_code']
                    )
                    if not recipient.get('status'):
                        raise ValidationError(f"Failed to create transfer recipient: {recipient.get('message')}")
                    account_details['recipient_code'] = recipient['data']['recipient_code']
                    payment_info.account_details = account_details
                    payment_info.save()

                # Process payment
                result = payment_service.process_payment(
                    amount=release.amount,
                    currency='NGN',
                    user_id=payment_info.developer.id,
                    description=f"Release #{release.id} for {release.app.name}"
                )

                if not result.get('success'):
                    raise ValidationError(f"Payment processing failed: {result.get('error')}")

                release.reference = result.get('reference')
                release.status = EscrowRelease.Status.COMPLETED
                release.save()
                messages.success(request, f'Release #{release.id} processed successfully. Reference: {release.reference}')

            elif payment_info.payment_method == 'bank_transfer':
                # Manual bank transfer process
                release.reference = f"MANUAL-{timezone.now().strftime('%Y%m%d%H%M%S')}"
                release.status = EscrowRelease.Status.COMPLETED
                release.save()
                messages.success(request, f'Release #{release.id} marked for manual bank transfer.')

            else:
                raise ValidationError(f"Unsupported payment method: {payment_info.payment_method}")
                
        except ValidationError as e:
            release.status = EscrowRelease.Status.FAILED
            release.failure_reason = str(e)
            release.save()
            messages.error(request, str(e))
        except Exception as e:
            release.status = EscrowRelease.Status.FAILED
            release.failure_reason = f"Unexpected error: {str(e)}"
            release.save()
            messages.error(request, f"An unexpected error occurred: {str(e)}")
        
        return redirect('core:release_detail', release_id=release.id)