from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.http import JsonResponse
from django.contrib import messages
from django.urls import reverse
from ..models import Advertisement, AdClick
from ..forms import AdvertisementForm
from ..services.payments import PaymentService
from django.views.decorators.csrf import csrf_exempt
from django.contrib.admin.views.decorators import staff_member_required
from django.conf import settings
import time
import requests

# Get NotificationService lazily to avoid circular imports
def get_notification_service():
    from ..services import get_notification_service
    return get_notification_service()

@login_required
def ad_create(request):
    """View for creating a new advertisement"""
    if request.method == 'POST':
        form = AdvertisementForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                # Save the ad but mark as unpaid
                ad = form.save(commit=False)
                ad.user = request.user
                ad.advertiser = request.user  # Set the advertiser field
                ad.payment_status = 'pending'
                ad.status = 'pending'
                ad.save()
                
                # Calculate payment amount
                days = (ad.end_date - ad.start_date).days + 1
                rate = 5000 if ad.position == 'main' else 3000
                amount = days * rate * 100  # Convert to kobo for Paystack
                
                # Generate unique reference
                reference = f'ad_{ad.id}_{int(time.time())}'
                
                return JsonResponse({
                    'success': True,
                    'payment_required': True,
                    'ad_id': ad.id,
                    'amount': amount,
                    'email': request.user.email,
                    'reference': reference
                })
            except Exception as e:
                # If anything goes wrong, delete the ad if it was created
                if 'ad' in locals():
                    try:
                        ad.delete()
                    except:
                        pass  # Ignore deletion errors
                return JsonResponse({
                    'success': False,
                    'message': str(e)
                }, status=400)
        else:
            return JsonResponse({
                'success': False,
                'errors': form.errors
            }, status=400)
    
    form = AdvertisementForm(initial={
        'company_name': request.user.username,
        'contact_email': request.user.email
    })
    
    return render(request, 'core/ads/form.html', {
        'form': form,
        'paystack_public_key': settings.PAYSTACK_PUBLIC_KEY
    })

@login_required
def verify_ad_payment(request, pk):
    ad = get_object_or_404(Advertisement, pk=pk, user=request.user)
    reference = request.GET.get('reference')
    
    if not reference:
        return JsonResponse({
            'success': False,
            'message': 'No payment reference provided'
        }, status=400)
    
    try:
        # Verify payment with Paystack
        url = f'https://api.paystack.co/transaction/verify/{reference}'
        headers = {
            'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}'
        }
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            response_data = response.json()
            
            if response_data['data']['status'] == 'success':
                # Update ad status
                ad.payment_status = 'paid'
                ad.status = 'pending_review'  # Move to review queue
                ad.payment_reference = reference
                ad.payment_verified_at = timezone.now()
                ad.save()
                
                NotificationService = get_notification_service()
                # Send notification
                NotificationService.send_notification(
                    user=ad.user,
                    title='Payment Successful',
                    message=f'Payment for your advertisement "{ad.title}" has been verified. Your ad is now pending review.',
                    notification_type='payment_success'
                )
                
                # Notify admin about new ad for review
                NotificationService.notify_admin(
                    title='New Advertisement for Review',
                    message=f'A new advertisement "{ad.title}" requires review.',
                    notification_type='ad_review'
                )
                
                return JsonResponse({
                    'success': True,
                    'message': 'Payment verified successfully'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Payment verification failed'
                }, status=400)
        else:
            return JsonResponse({
                'success': False,
                'message': 'Could not verify payment with payment provider'
            }, status=400)
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)

@login_required
def ad_list(request):
    ads = Advertisement.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'core/ads/list.html', {'ads': ads})

@login_required
def ad_review(request, pk):
    """Admin review for advertisements"""
    ad = get_object_or_404(Advertisement, pk=pk)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        notes = request.POST.get('notes', '')
        
        if action == 'approve':
            ad.status = 'active'
            message = f'Your advertisement "{ad.title}" has been approved and is now active.'
        else:
            ad.status = 'rejected'
            message = f'Your advertisement "{ad.title}" has been rejected. Reason: {notes}'
        
        ad.admin_notes = notes
        ad.reviewed_at = timezone.now()
        ad.save()
        
        NotificationService = get_notification_service()
        # Notify user
        NotificationService.send_notification(
            user=ad.user,
            title='Advertisement Review Update',
            message=message,
            notification_type='ad_review_update'
        )
        
        return redirect('core:admin_ads')
    
    return render(request, 'core/ads/review.html', {'ad': ad})

def ad_click(request, pk):
    """Handle ad clicks and redirect to the target URL"""
    ad = get_object_or_404(Advertisement, pk=pk, status='ACTIVE', is_active=True)
    
    # Record the click
    AdClick.objects.create(
        advertisement=ad,
        user=request.user if request.user.is_authenticated else None,
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )
    
    # Update click counts
    if request.user.is_authenticated:
        ad.unique_authenticated_clicks += 1
    else:
        ad.anonymous_clicks += 1
    
    ad.total_clicks += 1
    ad.last_clicked = timezone.now()
    ad.save()
    
    return redirect(ad.target_url)

@login_required
def ad_edit(request, pk):
    """View for editing an existing advertisement"""
    ad = get_object_or_404(Advertisement, pk=pk, user=request.user)
    
    if request.method == 'POST':
        form = AdvertisementForm(request.POST, instance=ad)
        if form.is_valid():
            try:
                # Save the updated ad
                ad = form.save(commit=False)
                
                # Only allow editing if ad is not active
                if ad.status not in ['active', 'pending_review']:
                    ad.save()
                    messages.success(request, 'Advertisement updated successfully.')
                    return redirect('core:ad_list')
                else:
                    messages.error(request, 'Cannot edit an active or pending review advertisement.')
            except Exception as e:
                messages.error(request, f'Error updating advertisement: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = AdvertisementForm(instance=ad)
    
    return render(request, 'core/ads/form.html', {
        'form': form,
        'ad': ad,
        'is_edit': True
    })

@login_required
def ad_delete(request, pk):
    """View for deleting an advertisement"""
    ad = get_object_or_404(Advertisement, pk=pk, user=request.user)
    
    # Only allow deletion if ad is not active
    if ad.status not in ['active', 'pending_review']:
        try:
            ad.delete()
            messages.success(request, 'Advertisement deleted successfully.')
        except Exception as e:
            messages.error(request, f'Error deleting advertisement: {str(e)}')
    else:
        messages.error(request, 'Cannot delete an active or pending review advertisement.')
    
    return redirect('core:ad_list') 