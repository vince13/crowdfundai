from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, Http404
from django.urls import reverse
from django.core.exceptions import PermissionDenied
from ..models import AppListing, ProjectMilestone, ProjectUpdate, ProjectTag, AppTag, Deliverable, EscrowRelease, ReleaseRequest
from ..forms import ProjectMilestoneForm, DeliverableForm, ProjectUpdateForm, ProjectTagForm, AppTagForm
from django.contrib.auth.decorators import user_passes_test
from decimal import Decimal

def is_admin(user):
    """Check if user is an admin."""
    return user.is_authenticated and user.is_staff

@login_required
def project_dashboard(request, pk):
    """Display project management dashboard for an app."""
    app = get_object_or_404(AppListing, pk=pk, developer=request.user)
    milestones = app.milestones.all()
    updates = app.updates.all()[:5]
    tags = app.tags.all()
    
    context = {
        'app': app,
        'milestones': milestones,
        'updates': updates,
        'tags': tags,
        'page_title': f'Project Dashboard - {app.name}'
    }
    return render(request, 'core/project/dashboard.html', context)

@login_required
def milestone_list(request, pk):
    """Display and manage milestones for an app."""
    try:
        # First try to get the app
        app = AppListing.objects.get(pk=pk)
        
        # Check if user is developer or admin
        if not (request.user.is_staff or request.user == app.developer):
            messages.error(request, "You don't have permission to view this app's milestones.")
            return redirect('core:app_list')
        
        if request.method == 'POST':
            if request.user != app.developer:
                messages.error(request, "Only the app developer can add milestones.")
                return redirect('core:milestone_list', pk=pk)
                
            form = ProjectMilestoneForm(request.POST, app=app)
            if form.is_valid():
                milestone = form.save(commit=False)
                milestone.app = app
                milestone.save()
                messages.success(request, 'Milestone added successfully.')
                return redirect('core:milestone_list', pk=pk)
        else:
            form = ProjectMilestoneForm(app=app)
        
        # Get milestone counts by status
        milestones = app.milestones.all()
        context = {
            'app': app,
            'milestones': milestones,
            'form': form,
            'page_title': f'Milestones - {app.name}',
            'completed_count': milestones.filter(status__in=['COMPLETED', 'VERIFIED']).count(),
            'in_progress_count': milestones.filter(status='IN_PROGRESS').count(),
            'total_count': milestones.count()
        }
        return render(request, 'core/project/milestone_list.html', context)
    except AppListing.DoesNotExist:
        messages.error(request, "The requested app does not exist.")
        return redirect('core:app_list')
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('core:app_list')

@login_required
def milestone_detail(request, pk, milestone_id):
    """Display and manage a specific milestone."""
    # First get the app
    app = get_object_or_404(AppListing, pk=pk)
    
    # Check if user is developer or admin
    if not (request.user.is_staff or request.user == app.developer):
        raise PermissionDenied("You don't have permission to view this milestone")
    
    milestone = get_object_or_404(ProjectMilestone, pk=milestone_id, app=app)
    deliverables = milestone.deliverables.all()
    
    # Only show form to developer
    form = None
    if request.user == app.developer:
        if request.method == 'POST':
            form = DeliverableForm(request.POST)
            if form.is_valid():
                deliverable = form.save(commit=False)
                deliverable.milestone = milestone
                deliverable.save()
                messages.success(request, 'Deliverable added successfully.')
                return redirect('core:milestone_detail', pk=pk, milestone_id=milestone_id)
        else:
            form = DeliverableForm()
    
    context = {
        'app': app,
        'milestone': milestone,
        'deliverables': deliverables,
        'form': form,
        'page_title': f'Milestone: {milestone.title}'
    }
    return render(request, 'core/project/milestone_detail.html', context)

@login_required
def update_list(request, pk):
    """Display and manage project updates."""
    app = get_object_or_404(AppListing, pk=pk, developer=request.user)
    
    if request.method == 'POST':
        form = ProjectUpdateForm(app=app, data=request.POST)
        if form.is_valid():
            update = form.save(commit=False)
            update.app = app
            update.save()
            messages.success(request, 'Update posted successfully.')
            return redirect('core:update_list', pk=pk)
    else:
        form = ProjectUpdateForm(app=app)
    
    updates = app.updates.all()
    context = {
        'app': app,
        'updates': updates,
        'form': form,
        'page_title': f'Updates - {app.name}'
    }
    return render(request, 'core/project/update_list.html', context)

@login_required
def manage_tags(request, pk):
    """Manage project tags."""
    app = get_object_or_404(AppListing, pk=pk, developer=request.user)
    
    if request.method == 'POST':
        form = AppTagForm(request.POST)
        if form.is_valid():
            # Clear existing tags
            AppTag.objects.filter(app=app).delete()
            # Add new tags
            for tag in form.cleaned_data['tags']:
                AppTag.objects.create(app=app, tag=tag)
            messages.success(request, 'Tags updated successfully.')
            return redirect('core:manage_tags', pk=pk)
    else:
        form = AppTagForm(initial={'tags': app.tags.all()})
    
    tag_form = ProjectTagForm()  # For creating new tags
    
    context = {
        'app': app,
        'form': form,
        'tag_form': tag_form,
        'page_title': f'Manage Tags - {app.name}'
    }
    return render(request, 'core/project/manage_tags.html', context)

@login_required
def create_tag(request):
    """AJAX view to create a new tag."""
    if request.method == 'POST':
        form = ProjectTagForm(request.POST)
        if form.is_valid():
            tag = form.save()
            return JsonResponse({
                'status': 'success',
                'tag_id': tag.id,
                'tag_name': tag.name
            })
    return JsonResponse({'status': 'error'}, status=400)

def milestone_samples(request):
    """Display sample milestone structures and guidelines."""
    return render(request, 'core/project/milestone_samples.html')

@login_required
def request_milestone_verification(request, pk, milestone_id):
    """Developer requests verification for a completed milestone."""
    app = get_object_or_404(AppListing, pk=pk, developer=request.user)
    milestone = get_object_or_404(ProjectMilestone, pk=milestone_id, app=app)
    
    if request.method == 'POST':
        if milestone.request_verification():
            messages.success(request, 'Verification request submitted successfully.')
        else:
            messages.error(request, 'Unable to request verification. Ensure milestone is 100% complete.')
    
    return redirect('core:milestone_detail', pk=pk, milestone_id=milestone_id)

@login_required
@user_passes_test(is_admin)
def verify_milestone(request, pk, milestone_id):
    """Admin verifies a milestone and approves fund release."""
    app = get_object_or_404(AppListing, pk=pk)
    milestone = get_object_or_404(ProjectMilestone, pk=milestone_id, app=app)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        notes = request.POST.get('notes', '')
        
        if action == 'verify':
            if milestone.verify(request.user, notes):
                messages.success(request, 'Milestone verified successfully. Fund release request created.')
            else:
                messages.error(request, 'Unable to verify milestone.')
        elif action == 'reject':
            if milestone.reject(request.user, notes):
                messages.warning(request, 'Milestone verification rejected.')
            else:
                messages.error(request, 'Unable to reject milestone verification.')
    
    return redirect('core:milestone_detail', pk=pk, milestone_id=milestone_id)

@login_required
@user_passes_test(is_admin)
def manage_escrow_releases(request):
    """Admin view to manage escrow release requests."""
    pending_verifications = ProjectMilestone.objects.filter(
        status=ProjectMilestone.Status.VERIFICATION_REQUESTED
    ).order_by('-verification_requested_at')
    
    pending_releases = EscrowRelease.objects.filter(
        status=EscrowRelease.Status.PENDING
    ).order_by('-created_at')
    
    completed_releases = EscrowRelease.objects.exclude(
        status=EscrowRelease.Status.PENDING
    ).order_by('-updated_at')[:10]
    
    context = {
        'pending_verifications': pending_verifications,
        'pending_releases': pending_releases,
        'completed_releases': completed_releases,
        'page_title': 'Manage Escrow & Verifications'
    }
    return render(request, 'core/admin/escrow_releases.html', context)

@login_required
@user_passes_test(is_admin)
def process_escrow_release(request, release_id):
    """Admin processes an escrow release request."""
    release = get_object_or_404(EscrowRelease, pk=release_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        notes = request.POST.get('notes', '')
        
        if action == 'approve':
            if release.approve(request.user, notes):
                messages.success(request, f'Funds released successfully: ₦{release.amount:,.2f}')
            else:
                messages.error(request, 'Unable to process fund release.')
        elif action == 'reject':
            if release.reject(request.user, notes):
                messages.warning(request, 'Fund release request rejected.')
            else:
                messages.error(request, 'Unable to reject fund release.')
        elif action == 'retry':
            if release.status != EscrowRelease.Status.FAILED:
                messages.error(request, 'Only failed releases can be retried.')
            else:
                if release.retry(request.user, notes):
                    messages.success(request, f'Release retried successfully: ₦{release.amount:,.2f}')
                else:
                    messages.error(request, 'Unable to retry fund release.')
    
    return redirect('core:manage_escrow_releases')

@login_required
def update_milestone_progress(request, pk, milestone_id):
    """Update the progress of a milestone."""
    app = get_object_or_404(AppListing, pk=pk, developer=request.user)
    milestone = get_object_or_404(ProjectMilestone, pk=milestone_id, app=app)
    
    if request.method == 'POST' and milestone.status == 'IN_PROGRESS':
        try:
            progress = int(request.POST.get('progress', 0))
            if 0 <= progress <= 100:
                milestone.progress = progress
                milestone.save()
                messages.success(request, 'Milestone progress updated successfully.')
            else:
                messages.error(request, 'Progress must be between 0 and 100.')
        except ValueError:
            messages.error(request, 'Invalid progress value.')
    
    return redirect('core:milestone_detail', pk=pk, milestone_id=milestone_id)

@login_required
def request_release(request):
    """Handle fund release requests for verified milestones."""
    # Get all verified milestones for the developer's apps
    eligible_milestones = ProjectMilestone.objects.filter(
        app__developer=request.user,
        status='VERIFIED'
    ).select_related('app')
    
    context = {
        'eligible_milestones': eligible_milestones,
        'page_title': 'Request Fund Release'
    }
    
    if request.method == 'POST':
        milestone_id = request.POST.get('milestone_id')
        amount = request.POST.get('amount')
        notes = request.POST.get('notes')
        
        try:
            milestone = eligible_milestones.get(id=milestone_id)
            remaining_funds = milestone.calculate_remaining_funds()
            
            if remaining_funds <= 0:
                messages.error(request, 'This milestone has no remaining funds to release.')
                return redirect('core:request_release')
                
            if milestone.release_percentage <= 0:
                messages.error(request, 'This milestone has no release percentage set.')
                return redirect('core:request_release')
                
            amount = Decimal(amount)
            if amount > remaining_funds:
                messages.error(request, f'The requested amount exceeds the remaining funds (₦{remaining_funds:,.2f}).')
                return redirect('core:request_release')
            
            # Create release request
            release_request = ReleaseRequest.objects.create(
                milestone=milestone,
                amount=amount,
                notes=notes,
                requested_by=request.user
            )
            
            messages.success(request, 'Release request submitted successfully.')
            return redirect('core:release_list')
            
        except ProjectMilestone.DoesNotExist:
            messages.error(request, 'Invalid milestone selected.')
        except (ValueError, decimal.InvalidOperation):
            messages.error(request, 'Invalid amount specified.')
        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}')
    
    return render(request, 'core/release/request_form.html', context) 