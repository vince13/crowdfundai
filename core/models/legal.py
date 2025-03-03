from django.db import models
from django.utils import timezone
from django.conf import settings

class LegalDocument(models.Model):
    DOCUMENT_TYPES = (
        ('TOS', 'Terms of Service'),
        ('PRIVACY', 'Privacy Policy'),
        ('USER_AGREEMENT', 'User Agreement'),
        ('SHARE_TRANSFER', 'Share Transfer Agreement'),
        ('INVESTMENT', 'Investment Agreement'),
    )
    
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    version = models.CharField(max_length=10)
    content = models.TextField()
    effective_date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    # New fields for document comparison
    previous_version = models.ForeignKey(
        'self', 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL,
        related_name='next_version'
    )
    change_summary = models.TextField(blank=True)
    
    class Meta:
        unique_together = ['document_type', 'version']
        ordering = ['-effective_date']
    
    def __str__(self):
        return f"{self.get_document_type_display()} - v{self.version}"
    
    def save(self, *args, **kwargs):
        if self.is_active:
            # Deactivate other versions of the same document type
            LegalDocument.objects.filter(
                document_type=self.document_type,
                is_active=True
            ).update(is_active=False)
        super().save(*args, **kwargs)
    
    def get_changes_from_previous(self):
        """Get a summary of changes from the previous version."""
        if not self.previous_version:
            return "Initial version"
        return self.change_summary or "No change summary provided"

class UserAgreement(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    document = models.ForeignKey(LegalDocument, on_delete=models.PROTECT)
    accepted_at = models.DateTimeField(default=timezone.now)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    
    class Meta:
        unique_together = ['user', 'document']
        ordering = ['-accepted_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.document}"

class ShareTransferAgreement(models.Model):
    """Model for tracking share transfer agreements between users."""
    transfer = models.OneToOneField('core.ShareTransfer', on_delete=models.CASCADE)
    legal_document = models.ForeignKey(LegalDocument, on_delete=models.PROTECT)
    seller_agreement = models.ForeignKey(
        UserAgreement,
        on_delete=models.PROTECT,
        related_name='share_transfers_as_seller'
    )
    buyer_agreement = models.ForeignKey(
        UserAgreement,
        on_delete=models.PROTECT,
        related_name='share_transfers_as_buyer',
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Transfer Agreement {self.transfer.id}"
    
    @property
    def is_complete(self):
        return bool(self.buyer_agreement and self.completed_at)
    
    def complete_agreement(self, buyer_agreement):
        """Complete the share transfer agreement with buyer's acceptance."""
        self.buyer_agreement = buyer_agreement
        self.completed_at = timezone.now()
        self.save()

class InvestmentAgreement(models.Model):
    """Model for tracking investment-specific agreements."""
    investment = models.OneToOneField('core.Investment', on_delete=models.CASCADE)
    legal_document = models.ForeignKey(LegalDocument, on_delete=models.PROTECT)
    investor_agreement = models.ForeignKey(
        UserAgreement,
        on_delete=models.PROTECT,
        related_name='investment_agreements'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Investment Agreement {self.investment.id}"

class LegalAgreement(models.Model):
    """Model for storing different versions of legal agreements"""
    AGREEMENT_TYPES = [
        ('terms', 'Terms of Service'),
        ('privacy', 'Privacy Policy'),
    ]
    
    agreement_type = models.CharField(max_length=20, choices=AGREEMENT_TYPES)
    version = models.CharField(max_length=10)
    content = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    effective_date = models.DateTimeField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_agreements'
    )
    
    class Meta:
        ordering = ['-created_at']
        get_latest_by = 'created_at'
        unique_together = ['agreement_type', 'version']
    
    def __str__(self):
        return f"{self.get_agreement_type_display()} - v{self.version}"
    
    def save(self, *args, **kwargs):
        if not self.effective_date:
            self.effective_date = timezone.now()
        if self.is_active:
            # Deactivate other active agreements of the same type
            LegalAgreement.objects.filter(
                agreement_type=self.agreement_type,
                is_active=True
            ).exclude(id=self.id).update(is_active=False)
        super().save(*args, **kwargs) 