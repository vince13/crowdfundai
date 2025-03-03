from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.urls import reverse
from ..services.text_formatter import TextFormatter
from django.core.validators import FileExtensionValidator
from core.services.pdf_analyzer import PDFAnalyzer
from core.services.ai_analyzer import AIAnalyzer
from .mixins import UserSecurityMixin, TwoFactorMixin
from django.db.models import Sum, Count, Q, F, Value, Avg
from django.db.models.functions import Coalesce
import pyotp
import qrcode
import base64
from io import BytesIO
from datetime import datetime, date
from django.conf import settings
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.db import transaction
import logging
import random

logger = logging.getLogger(__name__)

class User(AbstractUser, UserSecurityMixin, TwoFactorMixin):
    class Role(models.TextChoices):
        ADMIN = 'ADMIN', 'Admin'
        DEVELOPER = 'DEVELOPER', 'Developer'
        INVESTOR = 'INVESTOR', 'Investor'
    
    email = models.EmailField(unique=True)
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.INVESTOR
    )
    bio = models.TextField(blank=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    
    # Email verification
    is_email_verified = models.BooleanField(default=False)
    
    # Account locking
    failed_login_attempts = models.IntegerField(default=0)
    last_failed_login = models.DateTimeField(null=True, blank=True)
    account_locked_until = models.DateTimeField(null=True, blank=True)
    
    # 2FA fields
    two_factor_enabled = models.BooleanField(default=False)
    two_factor_secret = models.CharField(max_length=32, null=True, blank=True)
    
    # Account deletion fields
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deletion_reason = models.TextField(null=True, blank=True)
    
    # Session management
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    last_login_user_agent = models.CharField(max_length=255, null=True, blank=True)
    
    @property
    def has_active_subscription(self):
        try:
            return hasattr(self, 'subscription') and self.subscription is not None
        except Exception:
            return False

    def save(self, *args, **kwargs):
        # Ensure superusers are always assigned the ADMIN role
        if self.is_superuser:
            self.role = self.Role.ADMIN
        super().save(*args, **kwargs)

    def is_developer(self):
        return self.role == self.Role.DEVELOPER
    
    def is_investor(self):
        return self.role == self.Role.INVESTOR
    
    def get_total_investments(self):
        return self.investment_set.aggregate(
            total=models.Sum('amount_paid')
        )['total'] or 0
    
    def soft_delete(self, reason=None):
        """Soft delete the user account"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deletion_reason = reason
        self.email = f"deleted_{self.id}_{self.email}"  # Preserve email uniqueness
        self.username = f"deleted_{self.id}_{self.username}"  # Preserve username uniqueness
        self.is_active = False
        self.save()
    
    def record_login_attempt(self, success, ip_address=None, user_agent=None):
        """Record login attempt and handle account locking"""
        if success:
            self.failed_login_attempts = 0
            self.last_login_ip = ip_address
            self.last_login_user_agent = user_agent
        else:
            self.failed_login_attempts += 1
            self.last_failed_login = timezone.now()
            
            # Lock account after 5 failed attempts
            if self.failed_login_attempts >= 5:
                self.account_locked_until = timezone.now() + timezone.timedelta(minutes=30)
        
        self.save()
    
    def is_account_locked(self):
        """Check if account is temporarily locked"""
        if self.account_locked_until and self.account_locked_until > timezone.now():
            return True
        return False

    def setup_2fa(self):
        """Set up 2FA for the user"""
        if self.two_factor_enabled:
            return None
            
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        
        # Generate QR code
        provisioning_uri = totp.provisioning_uri(
            name=self.email,
            issuer_name="AI Crowdfunding"
        )
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        # Save the secret
        self.two_factor_secret = secret
        self.two_factor_enabled = True
        self.save()
        
        return {
            'secret': secret,
            'qr_code': qr_code_base64
        }
    
    def verify_2fa_code(self, code):
        """Verify a 2FA code"""
        if not self.two_factor_enabled or not self.two_factor_secret:
            return False
            
        totp = pyotp.TOTP(self.two_factor_secret)
        return totp.verify(code)
    
    def disable_2fa(self):
        """Disable 2FA for the user"""
        if not self.two_factor_enabled:
            return False
            
        self.two_factor_enabled = False
        self.two_factor_secret = None
        self.save()
        return True

    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users' 


# App Listing Model
class AppListing(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        ACTIVE = 'ACTIVE', 'Active'
        FUNDED = 'FUNDED', 'Funded'
        COMPLETED = 'COMPLETED', 'Completed'
        REJECTED = 'REJECTED', 'Rejected'
        IN_DEVELOPMENT = 'IN_DEVELOPMENT', 'In Development'
        BETA = 'BETA', 'Beta Testing'
        LAUNCHED = 'LAUNCHED', 'Launched'
        ON_HOLD = 'ON_HOLD', 'On Hold'
    
    class Category(models.TextChoices):
        ROBOTICS = 'ROBOTICS', 'Robotics'
        HEALTHCARE = 'HEALTHCARE', 'Healthcare'
        FINTECH = 'FINTECH', 'Financial Technology'
        EDTECH = 'EDTECH', 'Educational Technology'
        GAMING = 'GAMING', 'Gaming'
        SECURITY = 'SECURITY', 'Security'
        PRODUCTIVITY = 'PRODUCTIVITY', 'Productivity'
        SOCIAL = 'SOCIAL', 'Social'
        ECOMMERCE = 'ECOMMERCE', 'E-commerce'
        CAREER = 'CAREER', 'Career'
        OTHER = 'OTHER', 'Other'
    
    class Currency(models.TextChoices):
        NGN = 'NGN', 'Nigerian Naira'

    class FundingRound(models.TextChoices):
        PRESEED = 'PRESEED', 'Pre-seed'
        SEED = 'SEED', 'Seed'
        SERIES_A = 'SERIES_A', 'Series A'
        SERIES_B = 'SERIES_B', 'Series B'
        SERIES_C = 'SERIES_C', 'Series C'
    
    class DevelopmentStage(models.TextChoices):
        CONCEPT = 'CONCEPT', 'Concept'
        PROTOTYPE = 'PROTOTYPE', 'Prototype'
        MVP = 'MVP', 'Minimum Viable Product'
        BETA = 'BETA', 'Beta'
        PRODUCTION = 'PRODUCTION', 'Production'
        NOMINATED = 'NOMINATED', 'Nominated'  # Community nominated apps

    class ListingType(models.TextChoices):
        LISTED = 'LISTED', 'Listed'
        NOMINATED = 'NOMINATED', 'Nominated'
        COMMUNITY = 'COMMUNITY', 'Community Suggested'  # New type
        FOR_SALE = 'FOR_SALE', 'For Sale'  # New type for direct sales

    # Basic Information
    name = models.CharField(max_length=100)
    description = models.TextField()
    ai_features = models.TextField()
    demo_video = models.URLField(blank=True, help_text="Link to app demonstration video")
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.OTHER
    )
    
    # Nomination Fields
    listing_type = models.CharField(
        max_length=20,
        choices=ListingType.choices,
        default=ListingType.LISTED,
        help_text="Whether this is a listed app by developer or a community nominated app"
    )
    nomination_details = models.TextField(
        blank=True,
        help_text="Detailed description of the nominated app idea and its potential impact"
    )
    nomination_votes = models.PositiveIntegerField(
        default=0,
        help_text="Number of community votes/support for this nominated app"
    )
    nomination_external_link = models.URLField(
        blank=True,
        null=True,
        help_text="External link (e.g., YouTube video) for the nominated app"
    )
    nomination_budget_breakdown = models.JSONField(
        default=dict,
        blank=True,
        help_text="Detailed breakdown of estimated development costs for nominated apps"
    )
    nomination_timeline = models.JSONField(
        default=dict,
        blank=True,
        help_text="Estimated development timeline and milestones for nominated apps"
    )
    nominated_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nominated_apps',
        help_text="Admin who nominated this app"
    )
    nomination_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this app was nominated"
    )
    
    # Analytics Fields
    view_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times this app has been viewed"
    )
    like_count = models.PositiveIntegerField(
        default=0,
        help_text="Total number of likes (user + system generated)"
    )
    upvote_count = models.PositiveIntegerField(
        default=0,
        help_text="Total number of upvotes (user + system generated)"
    )
    comment_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of community comments and replies"
    )
    
    # System-generated metrics
    system_like_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of system-generated likes"
    )
    system_upvote_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of system-generated upvotes"
    )
    system_comment_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of system-generated comments"
    )
    
    # Project Management Fields
    development_stage = models.CharField(
        max_length=20,
        choices=DevelopmentStage.choices,
        default=DevelopmentStage.CONCEPT
    )
    project_status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    progress = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Overall project progress (0-100)"
    )
    estimated_completion_date = models.DateField(
        null=True,
        blank=True,
        help_text="Estimated project completion date"
    )
    last_update = models.DateTimeField(
        auto_now=True,
        help_text="Last project update timestamp"
    )
    
    # Funding Details
    funding_goal = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    fixed_valuation = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Fixed company valuation at the start of the funding round"
    )
    currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        default=Currency.NGN
    )
    exchange_rate = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        help_text="Exchange rate for currency conversion"
    )
    available_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="Total percentage of equity available for funding"
    )
    min_investment_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('1.00'),
        validators=[MinValueValidator(1)],
        help_text="Minimum percentage that can be purchased (e.g., 1%)"
    )
    remaining_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Percentage of equity still available"
    )
    price_per_percentage = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Price for 1% equity"
    )
    
    # Remove old fields but keep equity_percentage as it's used for total company equity info
    equity_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Total percentage of company equity (not just what's offered for funding)"
    )
    
    # Lock-in Period
    lock_in_period = models.IntegerField(
        default=180,  # 6 months in days
        help_text="Period (in days) before shares can be resold"
    )
    
    # Funding Round Details
    funding_round = models.CharField(
        max_length=20,
        choices=FundingRound.choices,
        default=FundingRound.PRESEED
    )
    round_number = models.PositiveIntegerField(
        default=1,
        help_text="Sequential number of the funding round"
    )
    
    # Use of Funds Breakdown
    use_of_funds = models.JSONField(
        default=dict,
        help_text="Breakdown of how funds will be used (e.g., {'marketing': 30, 'development': 50, 'operations': 20})"
    )
    
    # Escrow Tracking
    funds_in_escrow = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total funds currently held in escrow"
    )
    escrow_status = models.CharField(
        max_length=20,
        choices=[
            ('COLLECTING', 'Collecting Funds'),
            ('RELEASED', 'Funds Released'),
            ('REFUNDED', 'Funds Refunded')
        ],
        default='COLLECTING'
    )
    
    # References
    developer = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    
    # URLs
    github_url = models.URLField(blank=True)
    demo_url = models.URLField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    funding_end_date = models.DateTimeField(
        help_text="Date when funding round ends"
    )
    
    # Community Suggestion Fields
    suggested_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='suggested_apps',
        help_text="Community member who suggested this app"
    )
    suggestion_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this app was suggested by community"
    )
    community_likes = models.PositiveIntegerField(
        default=0,
        help_text="Number of community likes for this suggested app"
    )
    is_trending = models.BooleanField(
        default=False,
        help_text="Whether this app is trending based on community engagement"
    )
    
    # Trending status fields
    manual_trending = models.BooleanField(
        default=False,
        help_text="Manual override for trending status set by admin"
    )
    last_trending_update = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the trending status was last updated"
    )
    
    # Sales-specific fields
    sale_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Fixed price for outright purchase of the app"
    )
    sale_includes_source_code = models.BooleanField(
        default=True,
        help_text="Whether the sale includes full source code"
    )
    sale_includes_assets = models.BooleanField(
        default=True,
        help_text="Whether the sale includes all assets (images, designs, etc.)"
    )
    sale_includes_support = models.BooleanField(
        default=False,
        help_text="Whether post-sale technical support is included"
    )
    support_duration_months = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Duration of included technical support in months"
    )
    monthly_revenue = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Current monthly revenue of the app"
    )
    monthly_users = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Current monthly active users"
    )
    tech_stack = models.JSONField(
        default=dict,
        blank=True,
        help_text="Technologies and frameworks used in the app"
    )
    deployment_type = models.CharField(
        max_length=50,
        choices=[
            ('SAAS', 'Software as a Service'),
            ('SELF_HOSTED', 'Self Hosted'),
            ('MOBILE_APP', 'Mobile App'),
            ('DESKTOP_APP', 'Desktop App'),
            ('OTHER', 'Other')
        ],
        null=True,
        blank=True
    )
    
    def handle_funding_completion(self):
        """Handle tasks when app becomes fully funded."""
        from core.services.payments import PaymentService
        try:
            PaymentService.handle_funding_completion(self)
        except Exception as e:
            logger.error(f"Error handling funding completion: {str(e)}")

    def save(self, *args, **kwargs):
        """Save the app listing with proper locking and validation."""
        if self.pk:  # Only get existing instance if we're updating
            with transaction.atomic():
                app = AppListing.objects.select_for_update().get(pk=self.pk)
                
                # Update fields that need special handling
                if app.status != self.status and self.status == self.Status.FUNDED:
                    self.handle_funding_completion()
                
                # Update remaining percentage if needed
                if app.available_percentage != self.available_percentage:
                    self.remaining_percentage = self.available_percentage
        else:
            # For new instances, set remaining percentage equal to available percentage
            self.remaining_percentage = self.available_percentage
            
            # Calculate price per percentage for new listings
            if self.funding_goal and self.available_percentage:
                self.price_per_percentage = self.funding_goal / self.available_percentage
        
        super().save(*args, **kwargs)
    
    def get_funded_amount(self):
        """Get total amount funded in listing currency."""
        return self.investment_set.aggregate(
            total=models.Sum('amount_paid')
        )['total'] or 0
    
    def get_funding_progress(self):
        """Calculate funding progress as a percentage"""
        if self.funding_goal == 0:
            return Decimal('0.00')
        return (self.get_raised_amount() / self.funding_goal * 100).quantize(Decimal('0.01'))
        
    def is_fully_funded(self):
        """Check if the app has reached its funding goal."""
        return self.status == self.Status.FUNDED or self.get_funding_progress() >= 100
        
    def is_funding_goal_met(self):
        """Check if funding goal has been met"""
        return self.get_raised_amount() >= self.funding_goal
    
    def get_raised_amount(self):
        """Calculate total amount raised"""
        return Investment.objects.filter(app=self).aggregate(
            total=Coalesce(Sum('amount_paid'), Decimal('0.00'))
        )['total']
    
    def get_remaining_amount(self):
        """Calculate remaining amount needed"""
        raised = self.get_raised_amount()
        return self.funding_goal - raised if raised <= self.funding_goal else Decimal('0.00')
                
    def get_company_valuation(self):
        """Calculate company valuation based on funding goal and available percentage."""
        if self.funding_goal and self.available_percentage:
            return (self.funding_goal / self.available_percentage) * Decimal('100.0')
        return None
    
    def get_current_exchange_rate(self):
        """Fetch current NGN exchange rate from API."""
        # TODO: Implement exchange rate API integration
        return Decimal('1.00')  # Default rate for NGN
    
    def check_funding_status(self):
        """Check if funding goal has been reached or deadline passed."""
        if self.get_funding_progress() >= 100:
            self.status = self.Status.FUNDED
            self.escrow_status = 'RELEASED'
            self.save()
        elif self.funding_end_date < timezone.now():
            if self.escrow_status == 'COLLECTING':
                self.escrow_status = 'REFUNDED'
                self.save()
                self.refund_investors()
    
    def refund_investors(self):
        """Refund all investors if funding goal is not met."""
        from .tasks import process_refunds  # Avoid circular import
        process_refunds.delay(self.pk)

    def sync_remaining_percentage(self):
        """Recalculate and sync the remaining percentage based on actual investments."""
        total_invested = self.investment_set.aggregate(
            total=models.Sum('percentage_bought')
        )['total'] or 0
        self.remaining_percentage = self.available_percentage - total_invested
        
        # Update status if fully funded
        if self.remaining_percentage <= Decimal('0'):
            self.status = self.Status.FUNDED
            self.project_status = self.Status.FUNDED
            self.save(update_fields=['remaining_percentage', 'status', 'project_status'])
        else:
            self.save(update_fields=['remaining_percentage'])
            
        return self.remaining_percentage

    def clean(self):
        super().clean()
        if self.status == self.Status.ACTIVE:
            # Check if milestones exist and total 100%
            total_percentage = sum(
                milestone.release_percentage for milestone in self.milestones.all()
            )
            if total_percentage != 100:
                raise ValidationError({
                    'status': 'Milestones must be set and total to 100% before activating the app'
                })
            
            # Ensure minimum required milestones
            if self.milestones.count() < 2:
                raise ValidationError({
                    'status': 'At least 2 milestones must be defined before activating the app'
                })

    def activate(self):
        """Activate the app after validation."""
        self.full_clean()  # This will run the clean method
        self.status = self.Status.ACTIVE
        self.save()

    def get_investor_count(self):
        """Get the count of unique investors for this app."""
        return self.investment_set.values('investor').distinct().count()

    @property
    def upvote_count(self):
        return self.community_votes.filter(vote_type=CommunityVote.VoteType.UPVOTE).count()
    
    @property
    def like_count(self):
        return self.community_votes.filter(vote_type=CommunityVote.VoteType.LIKE).count()
    
    @property
    def comment_count(self):
        """Get total number of comments and replies."""
        base_comments = self.comments.filter(is_system_generated=False).count()
        replies = self.comments.filter(is_system_generated=False).aggregate(
            reply_count=Count('replies')
        )['reply_count'] or 0
        return base_comments + replies + (self.system_comment_count or 0)
    
    @property
    def is_trending(self):
        """
        Get the app's trending status.
        Returns True if either manually set to trending or meets automatic trending criteria.
        """
        if self.manual_trending:
            return True
            
        # Check automatic trending criteria
        recent_votes = self.community_votes.filter(
            created_at__gte=timezone.now() - timezone.timedelta(days=7)
        ).count()
        return recent_votes >= settings.TRENDING_VOTE_THRESHOLD

    def set_trending_status(self, is_trending):
        """
        Set the manual trending status for the app.
        """
        self.manual_trending = is_trending
        self.last_trending_update = timezone.now()
        self.save(update_fields=['manual_trending', 'last_trending_update'])

    def calculate_platform_fee(self):
        """Calculate 5% platform fee based on funding goal"""
        platform_fee_percentage = Decimal('0.05')  # 5%
        return self.funding_goal * platform_fee_percentage
    
    def process_platform_fee(self):
        """Process the platform fee when funding goal is reached"""
        if self.status != self.Status.FUNDED:
            raise ValueError("Can only process fee for funded apps")
            
        # Check if platform fee transaction already exists
        existing_fee = PlatformFeeTransaction.objects.filter(
            app=self,
            status__in=['PENDING', 'COMPLETED']
        ).first()
        
        if existing_fee:
            logger.info(f"Platform fee transaction already exists for app {self.id}")
            return existing_fee.amount
        
        fee_amount = self.calculate_platform_fee()
        
        # Create fee transaction record
        PlatformFeeTransaction.objects.create(
            app=self,
            amount=fee_amount,
            status='PENDING'
        )
        
        # Deduct fee from escrow before releasing funds
        return fee_amount

    def refresh_remaining_percentage(self):
        """Recalculate and update the remaining percentage based on investments."""
        total_invested = Investment.objects.filter(app=self).aggregate(
            total=models.Sum('percentage_bought')
        )['total'] or Decimal('0')
        
        self.remaining_percentage = self.available_percentage - total_invested
        self.save(update_fields=['remaining_percentage'])
        
        # Update status if fully funded
        if self.remaining_percentage <= Decimal('0'):
            self.status = self.Status.FUNDED
            self.project_status = self.Status.FUNDED
            self.save(update_fields=['status', 'project_status'])

    @property
    def total_received(self):
        """Calculate total amount received in escrow."""
        return EscrowTransaction.objects.filter(
            app=self,
            transaction_type=EscrowTransaction.Type.DEPOSIT,
            status='COMPLETED'
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')

    @property
    def total_released(self):
        """Calculate total amount released from escrow."""
        return EscrowTransaction.objects.filter(
            app=self,
            transaction_type__in=[
                EscrowTransaction.Type.RELEASE,
                EscrowTransaction.Type.MILESTONE_RELEASE
            ],
            status='COMPLETED'
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')

    def get_total_likes(self):
        """Get total number of likes including both user and system generated."""
        return self.community_votes.filter(
            vote_type=CommunityVote.VoteType.LIKE,
            is_system_generated=False
        ).count() + self.system_like_count
    
    def get_total_upvotes(self):
        """Get total number of upvotes including both user and system generated."""
        return self.community_votes.filter(
            vote_type=CommunityVote.VoteType.UPVOTE,
            is_system_generated=False
        ).count() + self.system_upvote_count

    def get_total_comments(self):
        """Get total number of comments including both user and system generated."""
        base_comments = self.comments.filter(is_system_generated=False).count()
        replies = self.comments.filter(is_system_generated=False).aggregate(
            reply_count=Count('replies')
        )['reply_count'] or 0
        return base_comments + replies + self.system_comment_count

    @property
    def engagement_score(self):
        """Calculate engagement score based on views, likes, upvotes, and comments."""
        # Get total metrics including both user and system generated
        total_views = self.view_count or 0
        total_likes = self.get_total_likes() or 0
        total_upvotes = self.get_total_upvotes() or 0
        total_comments = self.get_total_comments() or 0
        
        # Define weights for each metric
        VIEW_WEIGHT = 0.2
        LIKE_WEIGHT = 0.3
        UPVOTE_WEIGHT = 0.3
        COMMENT_WEIGHT = 0.2
        
        # Calculate base scores (as percentages of target values)
        view_score = min((total_views / 100) * 100, 100)  # Target: 100 views
        like_score = min((total_likes / 50) * 100, 100)   # Target: 50 likes
        upvote_score = min((total_upvotes / 30) * 100, 100)  # Target: 30 upvotes
        comment_score = min((total_comments / 20) * 100, 100)  # Target: 20 comments
        
        # Calculate weighted average
        weighted_score = (
            (view_score * VIEW_WEIGHT) +
            (like_score * LIKE_WEIGHT) +
            (upvote_score * UPVOTE_WEIGHT) +
            (comment_score * COMMENT_WEIGHT)
        )
        
        return round(weighted_score, 1)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['developer', 'status']),
            models.Index(fields=['currency', 'status']),
        ]

class Investment(models.Model):
    investor = models.ForeignKey(User, on_delete=models.CASCADE)
    app = models.ForeignKey(AppListing, on_delete=models.CASCADE)
    percentage_bought = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_id = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.pk:  # If this is a new instance
            with transaction.atomic():
                # Lock the app for update to prevent race conditions
                app = AppListing.objects.select_for_update().get(pk=self.app.pk)
                
                # Get the fixed company valuation
                company_valuation = app.get_company_valuation()
                if not company_valuation:
                    raise ValueError("Cannot create investment: Company valuation not set")

                # Calculate percentage bought based on amount paid and fixed valuation
                self.percentage_bought = (self.amount_paid / company_valuation * Decimal('100.0')).quantize(Decimal('0.01'))
                
                # Calculate total invested including this investment
                total_invested = Investment.objects.filter(app=app).aggregate(
                    total=models.Sum('percentage_bought')
                )['total'] or Decimal('0')
                
                # Check if investment would exceed available percentage
                if total_invested + self.percentage_bought > app.available_percentage:
                    raise ValueError(f"Cannot invest more than the remaining percentage ({app.remaining_percentage}%)")
                
                # Save the investment first
                super().save(*args, **kwargs)
                
                # Create or update ShareOwnership
                ownership, created = ShareOwnership.objects.get_or_create(
                    user=self.investor,
                    app=app,
                    defaults={'percentage_owned': Decimal('0')}
                )
                ownership.percentage_owned += self.percentage_bought
                ownership.save()
                
                # Create a Transaction record for this investment
                Transaction.objects.create(
                    user=self.investor,
                    app=app,
                    amount=self.amount_paid,
                    transaction_type=Transaction.Type.INVESTMENT,
                    status=Transaction.Status.COMPLETED
                )
                
                # Calculate new remaining percentage
                new_remaining = app.available_percentage - (total_invested + self.percentage_bought)
                app.remaining_percentage = new_remaining
                
                # Update app status if fully funded
                if new_remaining <= Decimal('0'):
                    app.status = AppListing.Status.FUNDED
                    app.project_status = AppListing.Status.FUNDED
                
                app.save()
                
                # Update self.app to use the locked instance
                self.app = app
        else:
            super().save(*args, **kwargs)

class ShareOwnership(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    app = models.ForeignKey(AppListing, on_delete=models.CASCADE)
    percentage_owned = models.DecimalField(max_digits=5, decimal_places=2)

    @property
    def current_value(self):
        """Calculate the current value of the investment based on percentage ownership"""
        app_valuation = self.app.get_company_valuation()
        if app_valuation is None:
            return Decimal('0.00')
        return (self.percentage_owned / Decimal('100.0')) * app_valuation

    class Meta:
        unique_together = ('user', 'app')

class Transaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    app = models.ForeignKey('AppListing', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=20, choices=[
        ('INVESTMENT', 'Investment'),
        ('WITHDRAWAL', 'Withdrawal'),
        ('REFUND', 'Refund')
    ])
    status = models.CharField(max_length=20, choices=[
        ('PENDING', 'Pending'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('REFUNDED', 'Refunded')
    ], default='PENDING')
    
    # Payment Gateway Details
    payment_gateway = models.CharField(max_length=20, choices=[
        ('PAYSTACK', 'Paystack'),
    ], default='PAYSTACK')
    gateway_reference = models.CharField(max_length=100, blank=True, null=True)
    gateway_transaction_id = models.CharField(max_length=100, blank=True, null=True)
    authorization_code = models.CharField(max_length=100, blank=True, null=True)
    card_type = models.CharField(max_length=50, blank=True, null=True)
    card_last4 = models.CharField(max_length=4, blank=True, null=True)
    gateway_response = models.CharField(max_length=100, blank=True, null=True)
    currency = models.CharField(max_length=3, default='NGN')
    metadata = models.JSONField(default=dict, blank=True)
    
    # Webhook Tracking
    webhook_received = models.BooleanField(default=False)
    webhook_received_at = models.DateTimeField(null=True, blank=True)
    webhook_attempts = models.IntegerField(default=0)
    last_webhook_attempt = models.DateTimeField(null=True, blank=True)
    webhook_status = models.CharField(max_length=20, choices=[
        ('PENDING', 'Pending'),
        ('RECEIVED', 'Received'),
        ('FAILED', 'Failed'),
        ('RETRYING', 'Retrying')
    ], default='PENDING')
    webhook_logs = models.JSONField(default=list, blank=True)
    
    # Error Tracking
    error_message = models.TextField(blank=True, null=True)
    error_code = models.CharField(max_length=50, blank=True, null=True)
    retry_count = models.IntegerField(default=0)
    last_retry_at = models.DateTimeField(null=True, blank=True)
    
    # Support and Debugging
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    debug_info = models.JSONField(default=dict, blank=True)
    support_reference = models.CharField(max_length=50, unique=True, null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['gateway_reference']),
            models.Index(fields=['gateway_transaction_id']),
            models.Index(fields=['authorization_code']),
            models.Index(fields=['status']),
            models.Index(fields=['webhook_status']),
            models.Index(fields=['support_reference']),
        ]

    def __str__(self):
        return f"{self.transaction_type} - {self.gateway_reference}"

    def save(self, *args, **kwargs):
        # Generate support reference if not exists
        if not self.support_reference:
            self.support_reference = f"SR{timezone.now().strftime('%y%m%d')}{random.randint(1000, 9999)}"
        
        # Set completed_at when status changes to COMPLETED
        if self.status == 'COMPLETED' and not self.completed_at:
            self.completed_at = timezone.now()
            
        # Update webhook status when webhook is received
        if self.webhook_received and self.webhook_status == 'PENDING':
            self.webhook_status = 'RECEIVED'
            self.webhook_received_at = timezone.now()
            
        super().save(*args, **kwargs)

    def log_webhook_attempt(self, success, response_data=None):
        """Log webhook attempt with timestamp and response data"""
        self.webhook_attempts += 1
        self.last_webhook_attempt = timezone.now()
        
        log_entry = {
            'attempt': self.webhook_attempts,
            'timestamp': self.last_webhook_attempt.isoformat(),
            'success': success,
            'response': response_data
        }
        
        self.webhook_logs.append(log_entry)
        if success:
            self.webhook_received = True
            self.webhook_status = 'RECEIVED'
            self.webhook_received_at = timezone.now()
        elif self.webhook_attempts >= 3:  # Max retry attempts
            self.webhook_status = 'FAILED'
        else:
            self.webhook_status = 'RETRYING'
        
        self.save()

    def record_error(self, error_message, error_code=None):
        """Record error details and increment retry count"""
        self.error_message = error_message
        self.error_code = error_code
        self.retry_count += 1
        self.last_retry_at = timezone.now()
        
        if self.retry_count >= 3:  # Max retry attempts
            self.status = 'FAILED'
        
        self.save()

    def get_transaction_summary(self):
        """Get a complete summary of the transaction for support purposes"""
        return {
            'support_reference': self.support_reference,
            'gateway_reference': self.gateway_reference,
            'transaction_id': self.gateway_transaction_id,
            'authorization_code': self.authorization_code,
            'amount': self.amount,
            'status': self.status,
            'webhook_status': self.webhook_status,
            'created_at': self.created_at,
            'completed_at': self.completed_at,
            'error_info': {
                'message': self.error_message,
                'code': self.error_code,
                'retries': self.retry_count
            },
            'webhook_info': {
                'received': self.webhook_received,
                'attempts': self.webhook_attempts,
                'last_attempt': self.last_webhook_attempt
            }
        }

class Notification(models.Model):
    class Type(models.TextChoices):
        INVESTMENT = 'INVESTMENT', 'Investment Update'
        PRICE = 'PRICE', 'Price Alert'
        SYSTEM = 'SYSTEM', 'System Notification'
        SYSTEM_ERROR = 'SYSTEM_ERROR', 'System Error'
        MILESTONE = 'MILESTONE', 'Portfolio Milestone'
        APP_UPDATE = 'APP_UPDATE', 'App Update'
        FUNDING_GOAL = 'FUNDING_GOAL', 'Funding Goal Reached'
        DIVIDEND = 'DIVIDEND', 'Dividend Payment'
        SECURITY = 'SECURITY', 'Security Alert'
        MAINTENANCE = 'MAINTENANCE', 'System Maintenance'
        NEWS = 'NEWS', 'App News'
        APP_APPROVAL = 'APP_APPROVAL', 'App Approval Status'
        PAYMENT_PENDING = 'PAYMENT_PENDING', 'Payment Processing'
        FUNDING_COMPLETE = 'FUNDING_COMPLETE', 'Funding Complete'
    
    class Severity(models.TextChoices):
        LOW = 'LOW', 'Low'
        MEDIUM = 'MEDIUM', 'Medium'
        HIGH = 'HIGH', 'High'
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=20, choices=Type.choices)
    title = models.CharField(max_length=255)
    message = models.TextField()
    link = models.CharField(max_length=255, blank=True)  # Optional link to relevant page
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.LOW)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.type} - {self.title}"

class NotificationPreference(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_preferences')
    email_notifications = models.BooleanField(default=True)
    push_notifications = models.BooleanField(default=True)
    
    # Notification type preferences
    investment_notifications = models.BooleanField(default=True)
    price_alerts = models.BooleanField(default=True)
    system_notifications = models.BooleanField(default=True)
    milestone_notifications = models.BooleanField(default=True)
    app_update_notifications = models.BooleanField(default=True)
    funding_goal_notifications = models.BooleanField(default=True)
    dividend_notifications = models.BooleanField(default=True)
    security_notifications = models.BooleanField(default=True)
    maintenance_notifications = models.BooleanField(default=True)
    news_notifications = models.BooleanField(default=True)
    app_approval_notifications = models.BooleanField(default=True)  # New preference for app approvals
    
    # Price alert thresholds
    price_alert_threshold = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=5.00,
        help_text="Percentage change to trigger price alerts"
    )
    
    # Add to existing model
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)
    notification_frequency = models.CharField(
        max_length=20,
        choices=[
            ('IMMEDIATE', 'Immediate'),
            ('HOURLY', 'Hourly Digest'),
            ('DAILY', 'Daily Digest'),
            ('WEEKLY', 'Weekly Digest')
        ],
        default='IMMEDIATE'
    )
    minimum_investment_alert = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    class Meta:
        verbose_name = "Notification Preference"
        verbose_name_plural = "Notification Preferences" 

class NotificationGroup(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    is_default = models.BooleanField(default=False)
    
    def __str__(self):
        return self.name

class NotificationGroupMembership(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    group = models.ForeignKey(NotificationGroup, on_delete=models.CASCADE)
    is_muted = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ('user', 'group') 

class NotificationAnalytics(models.Model):
    notification = models.OneToOneField(Notification, on_delete=models.CASCADE)
    delivered_at = models.DateTimeField(null=True)
    read_at = models.DateTimeField(null=True)
    clicked_at = models.DateTimeField(null=True)
    device_info = models.JSONField(default=dict)
    
    class Meta:
        verbose_name_plural = "Notification Analytics"

class NotificationTemplate(models.Model):
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=Notification.Type.choices)
    title_template = models.CharField(max_length=255)
    message_template = models.TextField()
    link_template = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def render(self, context):
        from django.template import Template, Context
        return {
            'title': Template(self.title_template).render(Context(context)),
            'message': Template(self.message_template).render(Context(context)),
            'link': Template(self.link_template).render(Context(context)) if self.link_template else ''
        }
    
    def __str__(self):
        return f"{self.name} ({self.type})" 

class NotificationChannel(models.Model):
    name = models.CharField(max_length=50)
    identifier = models.CharField(max_length=100)
    config = models.JSONField()
    is_active = models.BooleanField(default=True)

class UserNotificationChannel(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    channel = models.ForeignKey(NotificationChannel, on_delete=models.CASCADE)
    is_enabled = models.BooleanField(default=True)
    priority = models.IntegerField(default=0) 

class EscrowTransaction(models.Model):
    class Type(models.TextChoices):
        DEPOSIT = 'DEPOSIT', 'Deposit to Escrow'
        RELEASE = 'RELEASE', 'Release to Developer'
        REFUND = 'REFUND', 'Refund to Investor'
        PARTIAL_REFUND = 'PARTIAL_REFUND', 'Partial Refund'
        MILESTONE_RELEASE = 'MILESTONE_RELEASE', 'Milestone Release'
        DISPUTE_HOLD = 'DISPUTE_HOLD', 'Dispute Hold'
    
    class DisputeStatus(models.TextChoices):
        NO_DISPUTE = 'NO_DISPUTE', 'No Dispute'
        PENDING = 'PENDING', 'Dispute Pending'
        RESOLVED_RELEASE = 'RESOLVED_RELEASE', 'Release'
        RESOLVED_REFUND = 'RESOLVED_REFUND', 'Refund'
    
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'
        REFUNDED = 'REFUNDED', 'Refunded'
        PARTIALLY_REFUNDED = 'PARTIALLY_REFUNDED', 'Partially Refunded'
        DISPUTED = 'DISPUTED', 'Disputed'
    
    app = models.ForeignKey(AppListing, on_delete=models.CASCADE)
    investor = models.ForeignKey(User, on_delete=models.CASCADE)
    transaction_type = models.CharField(max_length=20, choices=Type.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(
        max_length=3,
        choices=AppListing.Currency.choices
    )
    payment_gateway = models.CharField(
        max_length=20,
        choices=[
            ('PAYSTACK', 'Paystack'),
        ]
    )
    gateway_reference = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    
    # New fields for enhanced escrow
    milestone = models.ForeignKey(
        'ProjectMilestone',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Associated milestone for release"
    )
    dispute_status = models.CharField(
        max_length=20,
        choices=DisputeStatus.choices,
        default=DisputeStatus.NO_DISPUTE
    )
    dispute_reason = models.TextField(blank=True)
    dispute_resolution_notes = models.TextField(blank=True)
    dispute_resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_disputes'
    )
    refund_reason = models.TextField(blank=True)
    original_transaction = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='refunds'
    )
    release_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Percentage of total amount to release"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    def clean(self):
        """Validate transaction before saving."""
        super().clean()
        
        if self.transaction_type in [self.Type.RELEASE, self.Type.MILESTONE_RELEASE]:
            # Calculate total deposits
            total_deposits = EscrowTransaction.objects.filter(
                app=self.app,
                transaction_type=self.Type.DEPOSIT,
                status='COMPLETED'
            ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
            
            # Calculate total releases
            total_releases = EscrowTransaction.objects.filter(
                app=self.app,
                transaction_type__in=[self.Type.RELEASE, self.Type.MILESTONE_RELEASE],
                status='COMPLETED'
            ).exclude(pk=self.pk).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
            
            # Check if this release would exceed available funds
            if self.amount > (total_deposits - total_releases):
                raise ValidationError({
                    'amount': f'Release amount (₦{self.amount:,.2f}) exceeds available funds (₦{total_deposits - total_releases:,.2f})'
                })
    
    def save(self, *args, **kwargs):
        if not self.pk:  # New transaction
            self.full_clean()  # Run validation before saving
            
            if self.transaction_type == self.Type.DEPOSIT:
                self.app.funds_in_escrow += self.amount
            elif self.transaction_type in [self.Type.RELEASE, self.Type.MILESTONE_RELEASE]:
                # Calculate release amount based on percentage if specified
                release_amount = self.amount
                if self.release_percentage:
                    release_amount = (self.amount * self.release_percentage) / Decimal('100.0')
                self.app.funds_in_escrow -= release_amount
            
            # Update app's escrow status
            if self.transaction_type == self.Type.DISPUTE_HOLD:
                self.app.escrow_status = 'DISPUTED'
            elif self.transaction_type == self.Type.MILESTONE_RELEASE:
                if self.milestone and self.milestone.status == 'COMPLETED':
                    self.app.escrow_status = 'PARTIALLY_RELEASED'
            
            self.app.save()
            
        super().save(*args, **kwargs)
    
    def initiate_dispute(self, reason):
        """Initiate a dispute for this transaction."""
        if self.dispute_status != self.DisputeStatus.NO_DISPUTE:
            raise ValueError("Dispute already exists")
        
        self.dispute_status = self.DisputeStatus.PENDING
        self.dispute_reason = reason
        self.status = 'DISPUTED'
        self.transaction_type = self.Type.DISPUTE_HOLD
        self.save()
    
    def resolve_dispute(self, resolver, resolution_type, notes):
        """Resolve a dispute with either release or refund."""
        if self.dispute_status != self.DisputeStatus.PENDING:
            raise ValueError("No pending dispute")
        
        self.dispute_status = resolution_type
        self.dispute_resolution_notes = notes
        self.dispute_resolved_by = resolver
        self.save()
        
        # Create appropriate transaction based on resolution
        if resolution_type == self.DisputeStatus.RESOLVED_RELEASE:
            EscrowTransaction.objects.create(
                app=self.app,
                investor=self.investor,
                transaction_type=self.Type.RELEASE,
                amount=self.amount,
                currency=self.currency,
                payment_gateway=self.payment_gateway,
                gateway_reference=self.gateway_reference,
                original_transaction=self
            )
        elif resolution_type == self.DisputeStatus.RESOLVED_REFUND:
            EscrowTransaction.objects.create(
                app=self.app,
                investor=self.investor,
                transaction_type=self.Type.REFUND,
                amount=self.amount,
                currency=self.currency,
                payment_gateway=self.payment_gateway,
                gateway_reference=self.gateway_reference,
                original_transaction=self,
                refund_reason="Dispute resolved in favor of refund"
            )
    
    def process_milestone_release(self, milestone):
        """Process a milestone-based release of funds."""
        if milestone.status != 'COMPLETED':
            raise ValueError("Cannot release funds for incomplete milestone")
        
        release_amount = (self.amount * milestone.release_percentage) / Decimal('100.0')
        
        EscrowTransaction.objects.create(
            app=self.app,
            investor=self.investor,
            transaction_type=self.Type.MILESTONE_RELEASE,
            amount=release_amount,
            currency=self.currency,
            payment_gateway=self.payment_gateway,
            gateway_reference=f"{self.gateway_reference}_milestone_{milestone.id}",
            milestone=milestone,
            release_percentage=milestone.release_percentage,
            original_transaction=self
        )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['app', 'transaction_type', 'status']),
            models.Index(fields=['investor', 'transaction_type']),
            models.Index(fields=['created_at']),
            models.Index(fields=['dispute_status']),
            models.Index(fields=['milestone', 'transaction_type']),
        ]

class FundingRound(models.Model):
    app = models.ForeignKey(AppListing, on_delete=models.CASCADE)
    round_type = models.CharField(
        max_length=20,
        choices=AppListing.FundingRound.choices
    )
    round_number = models.PositiveIntegerField()
    funding_goal = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(
        max_length=3,
        choices=AppListing.Currency.choices
    )
    exchange_rate = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        help_text="Exchange rate at the time of round creation"
    )
    share_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_shares = models.IntegerField()
    equity_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0.01), MaxValueValidator(100.00)]
    )
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    use_of_funds = models.JSONField(
        default=dict,
        help_text="Breakdown of how funds will be used"
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending Approval'),
            ('ACTIVE', 'Active'),
            ('COMPLETED', 'Completed'),
            ('FAILED', 'Failed'),
            ('REJECTED', 'Rejected by Admin')
        ],
        default='PENDING'
    )
    admin_feedback = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def get_valuation(self):
        """Calculate company valuation for this round."""
        total_company_shares = (self.total_shares * 100) / self.equity_percentage
        return total_company_shares * self.share_price
    
    def get_previous_round(self):
        """Get the previous funding round for this app."""
        return FundingRound.objects.filter(
            app=self.app,
            round_number=self.round_number - 1
        ).first()
    
    def get_valuation_change(self):
        """Calculate valuation change from previous round."""
        previous_round = self.get_previous_round()
        if not previous_round:
            return None
        current_valuation = self.get_valuation()
        previous_valuation = previous_round.get_valuation()
        change = ((current_valuation - previous_valuation) / previous_valuation) * 100
        
        return round(change, 2)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['app', 'round_number']
        indexes = [
            models.Index(fields=['app', 'status']),
            models.Index(fields=['round_type', 'status']),
        ]

class ShareTransfer(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        COMPLETED = 'COMPLETED', 'Completed'
        CANCELLED = 'CANCELLED', 'Cancelled'
        REJECTED = 'REJECTED', 'Rejected'
    
    app = models.ForeignKey(AppListing, on_delete=models.CASCADE)
    seller = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='share_sales'
    )
    buyer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='share_purchases',
        null=True,
        blank=True
    )
    percentage_amount = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Percentage amount being transferred"
    )
    price_per_percentage = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Price per percentage point"
    )
    currency = models.CharField(
        max_length=3,
        choices=AppListing.Currency.choices,
        default='NGN'
    )
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Total transaction amount (percentage_amount * price_per_percentage)"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    escrow_transaction = models.ForeignKey(
        EscrowTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    def save(self, *args, **kwargs):
        if not self.pk:  # New transfer
            # Calculate total amount
            self.total_amount = self.percentage_amount * self.price_per_percentage
            
            # Verify seller has enough percentage
            seller_ownership = ShareOwnership.objects.get(
                user=self.seller,
                app=self.app
            )
            if seller_ownership.percentage_owned < self.percentage_amount:
                raise ValueError("Seller does not have enough percentage to transfer")
            
            # Verify lock-in period has passed
            investment = Investment.objects.filter(
                investor=self.seller,
                app=self.app
            ).order_by('created_at').first()
            if investment:
                lock_in_end_date = investment.created_at + timezone.timedelta(
                    days=self.app.lock_in_period
                )
                if timezone.now() < lock_in_end_date:
                    raise ValueError("Investment is still within lock-in period")
        
        super().save(*args, **kwargs)
    
    def complete_transfer(self):
        """Complete the percentage transfer between seller and buyer."""
        if self.status != self.Status.PENDING:
            raise ValueError("Transfer cannot be completed")
        
        # Update seller's ownership
        seller_ownership = ShareOwnership.objects.get(
            user=self.seller,
            app=self.app
        )
        seller_ownership.percentage_owned -= self.percentage_amount
        seller_ownership.save()
        
        # Update or create buyer's ownership
        buyer_ownership, created = ShareOwnership.objects.get_or_create(
            user=self.buyer,
            app=self.app,
            defaults={'percentage_owned': 0}
        )
        buyer_ownership.percentage_owned += self.percentage_amount
        buyer_ownership.save()
        
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.save()
    
    def get_transaction_fee(self):
        """Calculate the transaction fee for this transfer."""
        # Default fee is 5% of the total amount
        fee_percentage = Decimal('0.05')
        return self.total_amount * fee_percentage
    
    def get_total_with_fee(self):
        """Get total amount including transaction fee."""
        return self.total_amount + self.get_transaction_fee()
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['app', 'status']),
            models.Index(fields=['seller', 'status']),
            models.Index(fields=['buyer', 'status']),
        ]

class AIAssessment(models.Model):
    app = models.OneToOneField('AppListing', on_delete=models.CASCADE, related_name='ai_assessment')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # AI Analysis Results
    technical_analysis = models.JSONField(
        null=True, blank=True,
        help_text="AI-extracted technical details including tech stack and AI features"
    )
    market_analysis = models.JSONField(
        null=True, blank=True,
        help_text="AI-extracted market insights including target market and competition"
    )
    team_analysis = models.JSONField(
        null=True, blank=True,
        help_text="AI-extracted team assessment and experience"
    )
    financial_analysis = models.JSONField(
        null=True, blank=True,
        help_text="AI-extracted financial metrics and projections"
    )
    risk_analysis = models.JSONField(
        null=True, blank=True,
        help_text="AI-identified risks and opportunities"
    )
    innovation_score = models.FloatField(
        null=True, blank=True,
        help_text="AI-calculated innovation score (0-100)"
    )
    market_potential_score = models.FloatField(
        null=True, blank=True,
        help_text="AI-calculated market potential score (0-100)"
    )
    execution_capability_score = models.FloatField(
        null=True, blank=True,
        help_text="AI-calculated execution capability score (0-100)"
    )
    overall_score = models.FloatField(
        null=True, blank=True,
        help_text="AI-calculated overall assessment score (0-100)"
    )
    ai_insights = models.TextField(
        null=True, blank=True,
        help_text="Additional AI-generated insights and recommendations"
    )

    def __str__(self):
        return f"AI Assessment for {self.app.name}"

class PitchDeck(models.Model):
    app = models.OneToOneField('AppListing', on_delete=models.CASCADE, related_name='pitch_deck')
    presentation_file = models.FileField(
        upload_to='pitch_decks/%Y/%m/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf'], message="Only PDF files are allowed.")],
        help_text="Upload your pitch deck (PDF only)",
        null=True,
        blank=True
    )
    ai_analysis_status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending'),
            ('IN_PROGRESS', 'In Progress'),
            ('COMPLETED', 'Completed'),
            ('FAILED', 'Failed'),
            ('DISABLED', 'Disabled')
        ],
        default='DISABLED'
    )
    ai_analysis_error = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Pitch Deck for {self.app.name}"

    def generate_ai_assessment(self) -> None:
        """Generate AI assessment for the pitch deck."""
        if not self.presentation_file:
            raise ValueError("No pitch deck file uploaded")

        self.ai_analysis_status = 'IN_PROGRESS'
        self.save(update_fields=['ai_analysis_status'])

        try:
            from ..services.ai_analyzer import PDFAnalyzer, AIAnalyzer
            from .ai_assessment import AIAssessment

            # Extract text from PDF
            pdf_analyzer = PDFAnalyzer(self.presentation_file.path)
            text_content = pdf_analyzer.extract_text()
            sections = pdf_analyzer.categorize_sections(text_content)

            # Generate AI insights
            ai_analyzer = AIAnalyzer()
            analysis_results = ai_analyzer.analyze_pitch_deck(sections)

            # Update or create AIAssessment
            assessment, created = AIAssessment.objects.get_or_create(app=self.app)
            assessment.technical_analysis = analysis_results.get('technical', {})
            assessment.market_analysis = analysis_results.get('market', {})
            assessment.team_analysis = analysis_results.get('team', {})
            assessment.financial_analysis = analysis_results.get('financial', {})
            assessment.risk_analysis = analysis_results.get('risks', {})
            
            # Calculate scores
            assessment.innovation_score = analysis_results.get('scores', {}).get('innovation', 0)
            assessment.market_potential_score = analysis_results.get('scores', {}).get('market', 0)
            assessment.execution_capability_score = analysis_results.get('scores', {}).get('execution', 0)
            assessment.overall_score = analysis_results.get('scores', {}).get('overall', 0)
            assessment.ai_insights = analysis_results.get('insights', '')
            assessment.save()

            self.ai_analysis_status = 'COMPLETED'
            self.ai_analysis_error = None
            self.save(update_fields=['ai_analysis_status', 'ai_analysis_error'])

        except Exception as e:
            self.ai_analysis_status = 'FAILED'
            self.ai_analysis_error = str(e)
            self.save(update_fields=['ai_analysis_status', 'ai_analysis_error'])
            raise

    def save(self, *args, **kwargs):
        # Don't automatically trigger AI analysis
        super().save(*args, **kwargs)

class Revenue(models.Model):
    """Model for tracking app revenue"""
    class RevenueType(models.TextChoices):
        SUBSCRIPTION = 'SUBSCRIPTION', 'Subscription'
        ONE_TIME = 'ONE_TIME', 'One-time Purchase'
        IN_APP = 'IN_APP', 'In-app Purchase'
        API_USAGE = 'API_USAGE', 'API Usage'
        CONSULTING = 'CONSULTING', 'Consulting Services'
        SUPPORT = 'SUPPORT', 'Support Services'
        OTHER = 'OTHER', 'Other'

    class Currency(models.TextChoices):
        NGN = 'NGN', 'Nigerian Naira'

    app = models.ForeignKey('AppListing', on_delete=models.CASCADE, related_name='revenues')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.NGN)
    source = models.CharField(max_length=50, choices=RevenueType.choices, default=RevenueType.ONE_TIME)
    description = models.TextField(blank=True)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    is_distributed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Additional tracking fields
    customer_count = models.PositiveIntegerField(
        default=1,
        help_text="Number of customers contributing to this revenue"
    )
    recurring_interval = models.CharField(
        max_length=20,
        choices=[
            ('NONE', 'Non-recurring'),
            ('MONTHLY', 'Monthly'),
            ('QUARTERLY', 'Quarterly'),
            ('ANNUALLY', 'Annually')
        ],
        default='NONE'
    )
    is_recurring = models.BooleanField(
        default=False,
        help_text="Whether this revenue is part of a recurring series"
    )
    parent_revenue = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Parent revenue for recurring series"
    )
    metadata = models.JSONField(
        default=dict,
        help_text="Additional revenue metadata (e.g., platform, region, etc.)"
    )
    exchange_rate = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        help_text="Exchange rate at the time of revenue recording"
    )

    def clean(self):
        """Validate revenue record"""
        errors = {}

        if self.amount <= 0:
            errors['amount'] = "Revenue amount must be positive"

        if self.period_start and self.period_end and self.period_start >= self.period_end:
            errors['period_start'] = "Period start must be before period end"

        if self.currency not in [choice[0] for choice in self.Currency.choices]:
            errors['currency'] = "Invalid currency code"

        # Validate minimum amount for Naira
        if self.currency == self.Currency.NGN and self.amount < 100:
            errors['amount'] = "Minimum amount for NGN is 100"

        if errors:
            raise ValidationError(errors)

        return super().clean()

    def save(self, *args, **kwargs):
        if not self.pk:  # New revenue record
            # Set exchange rate if currency is different from NGN
            if self.currency != self.Currency.NGN:
                self.exchange_rate = self.app.get_current_exchange_rate()
        self.full_clean()
        super().save(*args, **kwargs)

    def get_amount_usd(self):
        """Get revenue amount in USD"""
        if self.currency == self.Currency.USD:
            return self.amount
        return self.amount / (self.exchange_rate or self.app.get_current_exchange_rate())

    def get_distribution_status(self):
        """Get detailed distribution status"""
        if not self.is_distributed:
            return "Pending"
        distributions = self.distributions.all()
        completed = distributions.filter(status=Distribution.Status.COMPLETED).count()
        total = distributions.count()
        return f"Distributed ({completed}/{total} completed)"

    def get_formatted_amount(self):
        """Format the amount with currency symbol and proper formatting"""
        currency_symbols = {
            'NGN': '₦',
            'USD': '$',
            'EUR': '€',
            'GBP': '£',
            'JPY': '¥'
        }
        
        # Get symbol from metadata or default mapping
        symbol = self.metadata.get('display_symbol', currency_symbols.get(self.currency, ''))
        
        # Format amount based on currency
        if self.currency == 'JPY':
            # Japanese Yen has no decimal places
            formatted = f"{int(self.amount):,}"
        else:
            # Other currencies use 2 decimal places
            formatted = f"{self.amount:,.2f}"
            
        return f"{symbol}{formatted}"

    def clean_fields(self, exclude=None):
        """Validate individual fields"""
        super().clean_fields(exclude=exclude)
        
        if not exclude or 'exchange_rate' not in exclude:
            if self.exchange_rate and self.exchange_rate <= 0:
                raise ValidationError({
                    'exchange_rate': "Exchange rate must be positive"
                })

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['app', 'created_at'], name='rev_app_date_idx'),
            models.Index(fields=['is_distributed'], name='rev_dist_idx'),
            models.Index(fields=['currency', 'created_at'], name='rev_curr_date_idx'),
            models.Index(fields=['is_recurring', 'recurring_interval'], name='rev_recur_idx'),
            models.Index(fields=['source', 'created_at'], name='rev_src_date_idx')
        ]

class Distribution(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PROCESSING = 'PROCESSING', 'Processing'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'

    revenue = models.ForeignKey(Revenue, on_delete=models.CASCADE, related_name='distributions')
    recipient = models.ForeignKey('User', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    share_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    distributed_at = models.DateTimeField(null=True, blank=True)
    transaction_id = models.CharField(max_length=255, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ['-distributed_at']
        indexes = [
            models.Index(fields=['status', 'distributed_at'], name='dist_stat_date_idx'),
            models.Index(fields=['recipient', 'status'], name='dist_recp_stat_idx'),
        ]

class AppInsight(models.Model):
    """Model for storing AI-generated insights about apps"""
    
    INSIGHT_TYPES = (
        ('VALUATION', 'Valuation'),
        ('RISK', 'Risk Assessment'),
        ('GROWTH', 'Growth Potential'),
        ('MARKET', 'Market Analysis'),
    )
    
    app = models.ForeignKey('AppListing', on_delete=models.CASCADE, related_name='insights')
    insight_type = models.CharField(max_length=20, choices=INSIGHT_TYPES)
    value = models.FloatField()
    confidence = models.FloatField(validators=[MinValueValidator(0), MaxValueValidator(1)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.insight_type} insight for {self.app.name}"

class BlogCategory(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    meta_keywords = models.CharField(max_length=255, blank=True, help_text="Comma-separated keywords for SEO")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Blog Categories"
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

class Blog(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('published', 'Published'),
    )

    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    category = models.ForeignKey(BlogCategory, on_delete=models.PROTECT)
    content = models.TextField()
    source_url = models.URLField(blank=True, help_text="URL of the source article (optional)")
    target_word_count = models.PositiveIntegerField(default=500, help_text="Target word count for AI-generated content")
    is_ai_generated = models.BooleanField(default=False)
    featured_image = models.ImageField(upload_to='blog/images/%Y/%m/', blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    
    # SEO Fields
    meta_title = models.CharField(max_length=100, blank=True, help_text="Max 60 characters for SEO")
    meta_description = models.CharField(max_length=160, blank=True, help_text="Max 160 characters for SEO")
    meta_keywords = models.CharField(max_length=255, blank=True, help_text="Comma-separated keywords for SEO")
    
    # Social Sharing
    social_title = models.CharField(max_length=100, blank=True, help_text="Title for social media sharing")
    social_description = models.CharField(max_length=200, blank=True, help_text="Description for social media sharing")
    
    # Analytics
    view_count = models.PositiveIntegerField(default=0)
    read_time = models.PositiveIntegerField(default=5, help_text="Estimated reading time in minutes")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-published_at', '-created_at']
        indexes = [
            models.Index(fields=['-published_at', '-created_at']),
            models.Index(fields=['status', '-published_at']),
            models.Index(fields=['author', '-published_at']),
        ]
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        # Only set the slug if it's not already set
        if not self.slug:
            self.slug = slugify(self.title)
        
        if self.status == 'published' and not self.published_at:
            self.published_at = timezone.now()
            
        # Calculate read time based on word count
        word_count = len(self.content.split())
        self.read_time = max(1, round(word_count / 200))  # Assuming 200 words per minute
            
        super().save(*args, **kwargs)
    
    def get_formatted_content(self):
        """Returns the content formatted for display"""
        return TextFormatter.format_blog_content(self.content)
    
    def get_formatted_title(self):
        """Returns the title formatted for display"""
        return TextFormatter.format_title(self.title)
    
    def get_formatted_excerpt(self, length=200):
        """Returns a formatted excerpt of the content"""
        return TextFormatter.format_excerpt(self.content, length)
    
    def get_absolute_url(self):
        return reverse('core:blog_detail', kwargs={'slug': self.slug})
    
    def increment_view_count(self):
        self.view_count += 1
        self.save()

class Advertisement(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('PAID', 'Paid'),
        ('ACTIVE', 'Active'),
        ('EXPIRED', 'Expired')
    ]
    
    POSITION_CHOICES = [
        ('main', 'Main Content'),
        ('sidebar', 'Sidebar'),
    ]
    
    title = models.CharField(max_length=200)
    content = models.TextField(help_text="HTML content for the advertisement")
    image = models.ImageField(upload_to='ads/', help_text="Advertisement image (recommended size: 800x400px for main, 400x400px for sidebar)", null=True, blank=True)
    position = models.CharField(max_length=20, choices=POSITION_CHOICES)
    target_url = models.URLField()
    company_name = models.CharField(max_length=200)
    contact_email = models.EmailField()
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # User and status fields
    advertiser = models.ForeignKey(User, on_delete=models.CASCADE, related_name='advertisements')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_status = models.CharField(
        max_length=20,
        choices=[
            ('UNPAID', 'Unpaid'),
            ('PROCESSING', 'Processing'),
            ('PAID', 'Paid'),
            ('FAILED', 'Failed')
        ],
        default='UNPAID'
    )
    payment_id = models.CharField(max_length=255, blank=True, null=True)
    admin_notes = models.TextField(blank=True, help_text="Notes from admin review")
    rejection_reason = models.TextField(blank=True)
    app = models.ForeignKey(
        'AppListing',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='advertisements',
        help_text="Associated app if this is an app promotion"
    )
    
    # Click tracking fields
    total_clicks = models.PositiveIntegerField(default=0, help_text="Total clicks from all users")
    unique_authenticated_clicks = models.PositiveIntegerField(default=0, help_text="Unique clicks from authenticated users")
    anonymous_clicks = models.PositiveIntegerField(default=0, help_text="Clicks from anonymous users")
    impressions = models.PositiveIntegerField(default=0)
    last_clicked = models.DateTimeField(null=True, blank=True)
    clicked_by = models.ManyToManyField(
        User,
        related_name='clicked_ads',
        blank=True,
        help_text="Authenticated users who have clicked this ad"
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.company_name} - {self.position} ({self.start_date} to {self.end_date})"

    @property
    def is_current(self):
        now = timezone.now()
        # Convert dates to datetime if needed
        start = timezone.make_aware(datetime.combine(self.start_date, datetime.min.time())) if isinstance(self.start_date, date) else self.start_date
        end = timezone.make_aware(datetime.combine(self.end_date, datetime.max.time())) if isinstance(self.end_date, date) else self.end_date
        
        return (
            self.is_active and 
            self.status == 'ACTIVE' and 
            self.payment_status == 'PAID' and
            start <= now <= end
        )
    
    def calculate_price(self):
        """Calculate price based on position and duration"""
        days = (self.end_date - self.start_date).days
        base_price = 5000 if self.position == 'main' else 3000  # NGN per day
        return base_price * days
    
    def save(self, *args, **kwargs):
        if not self.pk:  # New advertisement
            self.price = self.calculate_price()
        super().save(*args, **kwargs)
    
    def track_click(self, user=None):
        """Track a click on this advertisement
        
        Args:
            user (User, optional): The user who clicked, if authenticated
        """
        self.total_clicks += 1
        self.last_clicked = timezone.now()
        
        if user and user.is_authenticated:
            # Track authenticated user clicks
            if user not in self.clicked_by.all():
                self.unique_authenticated_clicks += 1
                self.clicked_by.add(user)
        else:
            # Track anonymous user clicks
            self.anonymous_clicks += 1
        
        self.save()


class AdClick(models.Model):
    advertisement = models.ForeignKey(Advertisement, on_delete=models.CASCADE, related_name='click_records')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    clicked_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    
    class Meta:
        ordering = ['-clicked_at']
        
    def __str__(self):
        return f"Click on {self.advertisement.title} at {self.clicked_at}"

class CommunityVote(models.Model):
    class VoteType(models.TextChoices):
        LIKE = 'LIKE', 'Like'
        UPVOTE = 'UPVOTE', 'Upvote'
    
    user = models.ForeignKey('User', on_delete=models.CASCADE)
    app = models.ForeignKey('AppListing', on_delete=models.CASCADE, related_name='community_votes')
    vote_type = models.CharField(
        max_length=10,
        choices=VoteType.choices
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_system_generated = models.BooleanField(
        default=False,
        help_text="Whether this vote was generated by the system"
    )

    class Meta:
        unique_together = ('user', 'app', 'vote_type')
        indexes = [
            models.Index(fields=['app', 'vote_type']),
            models.Index(fields=['user', 'app']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.vote_type} - {self.app.name}"

class AppComment(models.Model):
    app = models.ForeignKey('AppListing', on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='app_comments')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_private = models.BooleanField(
        default=False,
        help_text="If True, only visible to the developer and commenter"
    )
    is_system_generated = models.BooleanField(
        default=False,
        help_text="Whether this comment was generated by the system"
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies'
    )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['app', 'created_at']),
            models.Index(fields=['user', 'created_at']),
        ]
        
    def __str__(self):
        return f"Comment by {self.user.username} on {self.app.name}"
        
    def is_visible_to(self, user):
        """Check if the comment is visible to the given user."""
        if not self.is_private:
            return True
        return user == self.user or user == self.app.developer

class PlatformFeeTransaction(models.Model):
    app = models.ForeignKey(AppListing, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending'),
            ('COMPLETED', 'Completed'),
            ('FAILED', 'Failed')
        ],
        default='PENDING'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True)
    transaction_reference = models.CharField(max_length=255, blank=True)
    payment_gateway = models.CharField(
        max_length=20,
        choices=[('PAYSTACK', 'Paystack')],
        default='PAYSTACK'
    )
    gateway_response = models.JSONField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['app', 'status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Platform Fee - {self.app.name} - {self.amount}"

class AppTeamMember(models.Model):
    ROLE_CHOICES = [
        ('DEVELOPER', 'Developer'),
        ('CMO', 'CMO'),
        ('CEO', 'CEO'),
        ('QA', 'Quality Assurance'),
        ('DEVOPS', 'DevOps Engineer'),
        ('OTHER', 'Other'),
    ]

    app = models.ForeignKey('AppListing', on_delete=models.CASCADE, related_name='team_members')
    name = models.CharField(max_length=100)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    custom_role = models.CharField(max_length=50, blank=True, null=True, help_text="Specify role if 'Other' is selected")
    email = models.EmailField(blank=True, null=True)
    github_profile = models.URLField(blank=True, null=True)
    linkedin_profile = models.URLField(blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    contribution_details = models.TextField(help_text="Describe the team member's contributions to the app")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.name} - {self.get_role_display()} at {self.app.name}"

    def get_display_role(self):
        if self.role == 'OTHER' and self.custom_role:
            return self.custom_role
        return self.get_role_display()

class EngagementAdjustmentLog(models.Model):
    """Log for tracking admin adjustments to engagement metrics."""
    app = models.ForeignKey('AppListing', on_delete=models.CASCADE, related_name='engagement_adjustments')
    admin = models.ForeignKey('User', on_delete=models.CASCADE, related_name='engagement_adjustments')
    views_added = models.PositiveIntegerField(default=0)
    likes_added = models.PositiveIntegerField(default=0)
    upvotes_added = models.PositiveIntegerField(default=0)
    comments_added = models.PositiveIntegerField(default=0)
    note = models.TextField(help_text="Reason for the adjustment")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['app', '-created_at']),
            models.Index(fields=['admin', '-created_at']),
        ]

    def __str__(self):
        return f"Engagement adjustment for {self.app.name} by {self.admin.username}"

class AppMessage(models.Model):
    app = models.ForeignKey('AppListing', on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey('User', on_delete=models.CASCADE, related_name='sent_messages')
    recipient = models.ForeignKey('User', on_delete=models.CASCADE, related_name='received_messages')
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False, help_text="Whether the message has been archived")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['app', '-created_at']),
            models.Index(fields=['sender', '-created_at']),
            models.Index(fields=['recipient', '-created_at']),
        ]

    def __str__(self):
        return f"Message from {self.sender.username} to {self.recipient.username} about {self.app.name}"

__all__ = [
    'User',
    'AppListing',
    'Investment',
    'ShareOwnership',
    'Transaction',
    'Notification',
    'NotificationPreference',
    'NotificationGroup',
    'NotificationGroupMembership',
    'NotificationAnalytics',
    'NotificationTemplate',
    'NotificationChannel',
    'UserNotificationChannel',
    'EscrowTransaction',
    'FundingRound',
    'ShareTransfer',
    'AIAssessment',
    'PitchDeck',
    'Revenue',
    'Distribution',
    'AppInsight',
    'BlogCategory',
    'Blog',
    'Advertisement',
    'AdClick',
    'CommunityVote',
    'AppComment',
    'PlatformFeeTransaction',
    'AppTeamMember',
    'EngagementAdjustmentLog',
    'AppMessage',
] 