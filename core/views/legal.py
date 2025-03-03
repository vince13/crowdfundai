from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.contrib import messages
from django.core.mail import send_mass_mail, send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.contrib.auth import get_user_model
from django.utils.html import strip_tags

from ..models.base import Notification
from ..models.legal import LegalDocument, UserAgreement, LegalAgreement
from core.forms import LegalAgreementForm

User = get_user_model()

def terms_of_service(request):
    """Display the current terms of service."""
    document = LegalDocument.objects.filter(
        document_type='TOS',
        is_active=True
    ).first()
    
    return render(request, 'core/legal/terms.html', {
        'document': document
    })

def privacy_policy(request):
    """Display the current privacy policy."""
    document = LegalDocument.objects.filter(
        document_type='PRIVACY',
        is_active=True
    ).first()
    
    if not document:
        # Create a default privacy policy if none exists
        document = LegalDocument.objects.create(
            document_type='PRIVACY',
            version='1.0',
            is_active=True,
            content='Default Privacy Policy'
        )
    
    context = {
        'document': document,
        'title': 'Privacy Policy',
        'last_updated': document.created_at
    }
    
    return render(request, 'core/legal/privacy.html', context)

@login_required
@require_POST
def accept_agreement(request, document_id):
    """Handle user acceptance of a legal document."""
    try:
        document = LegalDocument.objects.get(id=document_id)
        
        # Create or update user agreement
        UserAgreement.objects.update_or_create(
            user=request.user,
            document=document,
            defaults={
                'accepted_at': timezone.now(),
                'ip_address': request.META.get('REMOTE_ADDR'),
                'user_agent': request.META.get('HTTP_USER_AGENT')
            }
        )
        
        # Check if there are other documents that need acceptance
        needs_privacy = not check_agreement_acceptance(request.user, 'PRIVACY')
        needs_tos = not check_agreement_acceptance(request.user, 'TOS')
        
        # Determine next URL
        if needs_privacy:
            next_url = reverse('core:privacy_policy')
        elif needs_tos:
            next_url = reverse('core:terms_of_service')
        else:
            next_url = reverse('core:dashboard')
        
        return JsonResponse({
            'status': 'success',
            'next_url': next_url,
            'message': 'Agreement accepted successfully'
        })
    except LegalDocument.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Document not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@login_required
@user_passes_test(lambda u: u.is_staff)
def notify_legal_update(request, document_id):
    """Send notifications to users about legal document updates."""
    document = get_object_or_404(LegalDocument, id=document_id)
    
    # Get all users who haven't accepted this version
    users_to_notify = User.objects.exclude(
        useragreement__document=document
    ).distinct()
    
    # Prepare email notifications
    emails = []
    for user in users_to_notify:
        # Create in-app notification
        Notification.objects.create(
            user=user,
            title=f'New {document.get_document_type_display()} Available',
            message=f'Please review and accept the updated {document.get_document_type_display()}.',
            link=reverse('core:terms_of_service' if document.document_type == 'TOS' else 'core:privacy_policy')
        )
        
        # Prepare email content
        context = {
            'user': user,
            'document_type': document.get_document_type_display(),
            'document_version': document.version,
            'site_url': settings.SITE_URL
        }
        
        email_body = render_to_string('core/email/legal_update.html', context)
        emails.append((
            f'New {document.get_document_type_display()} Available',
            email_body,
            settings.DEFAULT_FROM_EMAIL,
            [user.email]
        ))
    
    # Send emails in bulk
    if emails:
        try:
            send_mass_mail(emails)
            messages.success(request, f'Notifications sent to {len(emails)} users.')
        except Exception as e:
            messages.error(request, f'Error sending emails: {str(e)}')
    else:
        messages.info(request, 'No users need to be notified.')
    
    return redirect('admin:core_legaldocument_changelist')

def check_agreement_acceptance(user, document_type):
    """Check if a user has accepted the latest version of a document type."""
    latest_document = LegalDocument.objects.filter(
        document_type=document_type,
        is_active=True
    ).first()
    
    if not latest_document:
        return True  # No document to accept
    
    return UserAgreement.objects.filter(
        user=user,
        document=latest_document
    ).exists()

class RequireAgreementAcceptance:
    """Middleware to ensure users have accepted the latest legal documents."""
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        if request.user.is_authenticated:
            # Skip for legal document pages and acceptance endpoint
            if not any(path in request.path for path in ['/legal/', '/accept-agreement/']):
                # Check Terms of Service
                if not check_agreement_acceptance(request.user, 'TOS'):
                    return redirect('core:terms_of_service')
                
                # Check Privacy Policy
                if not check_agreement_acceptance(request.user, 'PRIVACY'):
                    return redirect('core:privacy_policy')
        
        response = self.get_response(request)
        return response 

def terms(request):
    """View for Terms of Service page"""
    context = {
        'title': 'Terms of Service',
        'last_updated': LegalAgreement.objects.filter(
            agreement_type='terms'
        ).latest('updated_at').updated_at if LegalAgreement.objects.filter(
            agreement_type='terms'
        ).exists() else None
    }
    return render(request, 'core/legal/terms.html', context)

def privacy(request):
    """View for Privacy Policy page"""
    context = {
        'title': 'Privacy Policy',
        'last_updated': LegalAgreement.objects.filter(
            agreement_type='privacy'
        ).latest('updated_at').updated_at if LegalAgreement.objects.filter(
            agreement_type='privacy'
        ).exists() else None
    }
    return render(request, 'core/legal/privacy.html', context)

@login_required
def accept_agreement(request):
    """Handle user acceptance of legal agreements"""
    if request.method == 'POST':
        agreement_type = request.POST.get('agreement_type')
        if agreement_type not in ['terms', 'privacy']:
            return JsonResponse({'error': 'Invalid agreement type'}, status=400)
            
        agreement = LegalAgreement.objects.filter(
            agreement_type=agreement_type
        ).latest('updated_at')
        
        UserAgreement.objects.create(
            user=request.user,
            agreement=agreement,
            accepted_at=timezone.now(),
            ip_address=request.META.get('REMOTE_ADDR', '')
        )
        
        return JsonResponse({'status': 'success'})
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@login_required
def notify_legal_update(request):
    """Notify users about updates to legal agreements"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
        
    if request.method == 'POST':
        agreement_type = request.POST.get('agreement_type')
        if agreement_type not in ['terms', 'privacy']:
            return JsonResponse({'error': 'Invalid agreement type'}, status=400)
            
        # Get users who haven't accepted latest agreement
        latest_agreement = LegalAgreement.objects.filter(
            agreement_type=agreement_type
        ).latest('updated_at')
        
        users_to_notify = [
            user for user in UserAgreement.objects.filter(
                agreement__agreement_type=agreement_type
            ).select_related('user').distinct('user')
            if not UserAgreement.objects.filter(
                user=user,
                agreement=latest_agreement
            ).exists()
        ]
        
        # Send notification emails
        for user in users_to_notify:
            context = {
                'user': user,
                'agreement_type': agreement_type.title(),
                'agreement_url': f"{settings.SITE_URL}/legal/{'terms' if agreement_type == 'terms' else 'privacy'}"
            }
            
            html_message = render_to_string(
                'email/legal_update.html',
                context
            )
            
            send_mail(
                f'Important: {agreement_type.title()} Update',
                strip_tags(html_message),
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                html_message=html_message
            )
        
        return JsonResponse({
            'status': 'success',
            'notified_users': len(users_to_notify)
        })
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)

def terms_of_service(request):
    """Alias for terms view"""
    return terms(request)

def privacy_policy(request):
    """Alias for privacy view"""
    return privacy(request) 