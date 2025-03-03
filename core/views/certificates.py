from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse, Http404
from django.contrib import messages
from ..models.investment_receipt import InvestmentCertificate
from ..services.certificate_generator import CertificateGenerator

__all__ = ['certificate_list', 'certificate_detail', 'download_certificate', 'verify_certificate', 'revoke_certificate']

@login_required
def certificate_list(request):
    """View for listing all certificates for a user."""
    if request.user.is_staff:
        # Admin users can see all certificates
        certificates = InvestmentCertificate.objects.all().select_related('app', 'investor')
    else:
        # Regular users only see their active certificates
        certificates = InvestmentCertificate.objects.filter(
            investor=request.user,
            is_active=True
        ).select_related('app')
    
    return render(request, 'core/certificates/certificate_list.html', {
        'certificates': certificates,
        'is_admin': request.user.is_staff
    })

@login_required
def certificate_detail(request, pk):
    """View for showing certificate details."""
    # For admin users, allow viewing any certificate
    if request.user.is_staff:
        certificate = get_object_or_404(
            InvestmentCertificate,
            pk=pk
        )
    else:
        certificate = get_object_or_404(
            InvestmentCertificate,
            pk=pk,
            investor=request.user,
            is_active=True
        )
    
    return render(request, 'core/certificates/certificate_detail.html', {
        'certificate': certificate,
        'is_admin': request.user.is_staff
    })

@login_required
def download_certificate(request, pk):
    """View for downloading the PDF certificate."""
    certificate = get_object_or_404(
        InvestmentCertificate,
        pk=pk,
        investor=request.user,
        is_active=True
    )
    
    if not certificate.pdf_certificate:
        # Generate certificate if it doesn't exist
        CertificateGenerator.generate_certificate(certificate)
        certificate.refresh_from_db()
    
    try:
        with open(certificate.pdf_certificate.path, 'rb') as pdf:
            response = HttpResponse(pdf.read(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{certificate.app.name}_certificate.pdf"'
            return response
    except FileNotFoundError:
        messages.error(request, "Certificate file not found. Please contact support.")
        return redirect('certificate_detail', pk=pk)

def verify_certificate(request, certificate_id, transaction_hash):
    """Public view for verifying certificate authenticity."""
    is_valid, certificate = CertificateGenerator.validate_certificate(
        certificate_id,
        transaction_hash
    )
    
    return render(request, 'core/certificates/verify.html', {
        'is_valid': is_valid,
        'certificate': certificate
    })

@user_passes_test(lambda u: u.is_staff)
def revoke_certificate(request, pk):
    """View for revoking a certificate. Only accessible by admin users."""
    if request.method != 'POST':
        return Http404()
        
    certificate = get_object_or_404(InvestmentCertificate, pk=pk)
    
    # Deactivate the certificate
    certificate.is_active = False
    certificate.save()
    
    messages.success(request, f'Certificate for {certificate.app.name} has been revoked successfully.')
    return redirect('core:certificate_detail', pk=pk) 