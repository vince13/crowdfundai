from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

class VerificationDocument(models.Model):
    DOCUMENT_TYPES = [
        ('bank_statement', 'Bank Statement'),
        ('void_check', 'Void Check'),
        ('id_proof', 'ID Proof'),
    ]
    
    payment_info = models.ForeignKey(
        'DeveloperPaymentInfo',
        on_delete=models.CASCADE,
        related_name='verification_documents'
    )
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPES)
    file = models.FileField(upload_to='verification_documents/%Y/%m/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.get_document_type_display()} for {self.payment_info.developer.username}"

class DeveloperPaymentInfo(models.Model):
    PAYMENT_METHODS = [
        ('bank_transfer', 'Bank Transfer'),
        ('paystack', 'Paystack'),
    ]
    
    developer = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payment_info'
    )
    payment_method = models.CharField(
        max_length=50,
        choices=PAYMENT_METHODS,
        default='bank_transfer'
    )
    account_details = models.JSONField(
        help_text='Encrypted account details in JSON format'
    )
    verified = models.BooleanField(default=False)
    verification_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('under_review', 'Under Review'),
            ('verified', 'Verified'),
            ('rejected', 'Rejected')
        ],
        default='pending'
    )
    verification_notes = models.TextField(blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_payment_accounts'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Developer Payment Information'
        verbose_name_plural = 'Developer Payment Information'

    def __str__(self):
        return f"Payment Info for {self.developer.username}"

    def clean(self):
        required_fields = {
            'bank_transfer': ['bank_name', 'account_number', 'account_name'],
            'paystack': ['recipient_code', 'email']
        }
        
        if self.payment_method in required_fields:
            missing_fields = [
                field for field in required_fields[self.payment_method]
                if field not in self.account_details
            ]
            if missing_fields:
                raise ValidationError(
                    f"Missing required fields for {self.payment_method}: {', '.join(missing_fields)}"
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs) 