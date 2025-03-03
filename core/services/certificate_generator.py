import os
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from weasyprint import HTML
import qrcode
import base64
from io import BytesIO
from ..models.investment_receipt import InvestmentCertificate
from django.http import HttpResponse
from django.contrib import messages
from django.urls import reverse
from django.urls import reverse_lazy
from django.contrib.humanize.templatetags.humanize import intcomma
# from django.urls import reverse
# from django.urls import reverse_lazy

class CertificateGenerator:
    @staticmethod
    def generate_certificate(investment_certificate):
        """Generate a PDF certificate for an investment."""
        
        # Generate verification URL
        verification_url = f"https://aiapp.marketplace/verify-certificate/{investment_certificate.id}/{investment_certificate.transaction_hash}"
        
        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(verification_url)
        qr.make(fit=True)
        qr_image = qr.make_image(fill_color="black", back_color="white")
        
        # Convert QR code to base64
        buffer = BytesIO()
        qr_image.save(buffer, format="PNG")
        qr_code = base64.b64encode(buffer.getvalue()).decode()
        
        # Format amount with commas before passing to template
        formatted_amount = intcomma(investment_certificate.amount_invested)
        
        # Prepare context for the certificate template
        context = {
            'certificate': investment_certificate,
            'date': timezone.now().strftime('%B %d, %Y'),
            'app_name': investment_certificate.app.name,
            'investor_name': investment_certificate.investor.get_full_name() or investment_certificate.investor.username,
            'percentage': investment_certificate.percentage_owned,
            'amount': formatted_amount,  # Pre-formatted amount
            'transaction_hash': investment_certificate.transaction_hash,
            'qr_code': qr_code
        }
        
        # Render HTML template
        html_string = render_to_string('core/certificates/certificate_template.html', context)
        
        # Generate PDF
        html = HTML(string=html_string)
        
        # Create certificates directory if it doesn't exist
        certificates_dir = os.path.join(settings.MEDIA_ROOT, 'certificates', 
                                      timezone.now().strftime('%Y/%m'))
        os.makedirs(certificates_dir, exist_ok=True)
        
        # Generate filename
        filename = f"certificate_{investment_certificate.transaction_hash}.pdf"
        filepath = os.path.join(certificates_dir, filename)
        
        # Save PDF
        html.write_pdf(filepath)
        
        # Update certificate with PDF path
        relative_path = os.path.join('certificates', timezone.now().strftime('%Y/%m'), filename)
        investment_certificate.pdf_certificate = relative_path
        investment_certificate.save()
        
        return investment_certificate

    @staticmethod
    def validate_certificate(certificate_id, transaction_hash):
        """Validate a certificate's authenticity."""
        try:
            certificate = InvestmentCertificate.objects.get(
                id=certificate_id,
                transaction_hash=transaction_hash,
                is_active=True
            )
            return True, certificate
        except InvestmentCertificate.DoesNotExist:
            return False, None

    @staticmethod
    def download_certificate(request, certificate_id):
        """Download a certificate as a PDF."""
        try:
            certificate = InvestmentCertificate.objects.get(id=certificate_id)
            with open(certificate.pdf_certificate.path, 'rb') as pdf:
                response = HttpResponse(pdf.read(), content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="{certificate.app.name}_certificate.pdf"'
                return response
        except FileNotFoundError:
            messages.error(request, "Certificate file not found. Please try downloading again.")
            return redirect('core:certificate_list') 