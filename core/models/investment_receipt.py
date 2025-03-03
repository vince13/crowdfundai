from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from .base import AppListing

class InvestmentCertificate(models.Model):
    investor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='certificates'
    )
    app = models.ForeignKey(
        'core.AppListing',
        on_delete=models.PROTECT,
        related_name='certificates'
    )
    percentage_owned = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[
            MinValueValidator(0.01),
            MaxValueValidator(100.00)
        ],
        help_text='Percentage ownership in the app'
    )
    transaction_hash = models.CharField(
        max_length=255,
        unique=True,
        help_text='Unique transaction identifier'
    )
    amount_invested = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Amount invested in USD'
    )
    issue_date = models.DateTimeField(auto_now_add=True)
    pdf_certificate = models.FileField(
        upload_to='certificates/%Y/%m/',
        null=True,
        blank=True
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Whether this certificate is currently valid'
    )

    class Meta:
        verbose_name = 'Investment Certificate'
        verbose_name_plural = 'Investment Certificates'
        ordering = ['-issue_date']

    def __str__(self):
        return f"{self.investor.username}'s {self.percentage_owned}% in {self.app.name}"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('certificate_detail', kwargs={'pk': self.pk}) 