from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils import timezone
from django.db.models import Sum, Count
from decimal import Decimal
from .models import (
    User, AppListing, Investment, Transaction, ShareOwnership,
    ShareTransfer, EscrowTransaction, FundingRound, Revenue,
    Distribution, AppInsight, BlogCategory, Blog, Notification,
    NotificationPreference, NotificationGroup, NotificationGroupMembership,
    NotificationAnalytics, NotificationTemplate, NotificationChannel,
    UserNotificationChannel, SecurityAuditLog, APIRequest, APIError,
    AIAssessment, PitchDeck, LegalDocument, UserAgreement,
    ProjectMilestone, CommunityVote, Subscription, SubscriptionFeatureUsage,
    PlatformFeeTransaction, AppComment
)
from .services.escrow import EscrowService
from .services.reporting import EscrowReportingService
from .models.subscription import SubscriptionPlan
from django import forms
from django.shortcuts import render
from django.http import HttpResponse
from django.template.loader import render_to_string
from weasyprint import HTML
import json
from django.contrib import messages
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.admin import helpers
import base64


"""
User Management
"""
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'date_joined')
    list_filter = ('role', 'is_staff', 'is_active')
    fieldsets = UserAdmin.fieldsets + (
        ('Additional Info', {'fields': ('role', 'bio')}),
    )
    actions = ['export_as_pdf', 'export_as_json', 'import_users']

    def export_as_pdf(self, request, queryset):
        """Export selected users as PDF"""
        # Prepare the context with users data
        context = {
            'users': queryset,
            'title': 'Users Export',
            'date': timezone.now()
        }
        
        # Render HTML template
        html_string = render_to_string('admin/user_export_pdf.html', context)
        
        # Create PDF
        html = HTML(string=html_string)
        pdf = html.write_pdf()
        
        # Generate response
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="users_export.pdf"'
        
        return response
    export_as_pdf.short_description = "Export selected users as PDF"

    def export_as_json(self, request, queryset):
        """Export selected users as JSON"""
        users_data = []
        
        for user in queryset:
            # Get user permissions and groups
            permissions = list(user.user_permissions.values_list('codename', flat=True))
            groups = list(user.groups.values_list('name', flat=True))
            
            # Prepare user data
            user_data = {
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_active': user.is_active,
                'is_staff': user.is_staff,
                'is_superuser': user.is_superuser,
                'date_joined': user.date_joined.isoformat(),
                'role': user.role,
                'bio': user.bio,
                'permissions': permissions,
                'groups': groups,
                # Include password hash for import functionality
                'password': base64.b64encode(user.password.encode()).decode(),
            }
            users_data.append(user_data)
        
        # Create JSON response
        response = HttpResponse(
            json.dumps(users_data, cls=DjangoJSONEncoder, indent=2),
            content_type='application/json'
        )
        response['Content-Disposition'] = 'attachment; filename="users_export.json"'
        
        return response
    export_as_json.short_description = "Export selected users as JSON"

    def import_users(self, request, queryset):
        """Import users from JSON file"""
        if request.method == 'POST':
            form = ImportUsersForm(request.POST, request.FILES)
            if form.is_valid():
                import_file = request.FILES['import_file']
                
                try:
                    # Read and parse JSON data
                    data = json.loads(import_file.read().decode('utf-8'))
                    
                    success_count = 0
                    error_count = 0
                    
                    for user_data in data:
                        try:
                            # Check if user already exists
                            if User.objects.filter(email=user_data['email']).exists():
                                error_count += 1
                                continue
                            
                            # Create new user
                            user = User(
                                username=user_data['username'],
                                email=user_data['email'],
                                first_name=user_data.get('first_name', ''),
                                last_name=user_data.get('last_name', ''),
                                is_active=user_data.get('is_active', True),
                                is_staff=user_data.get('is_staff', False),
                                is_superuser=user_data.get('is_superuser', False),
                                role=user_data.get('role', 'USER'),
                                bio=user_data.get('bio', ''),
                            )
                            
                            # Set password hash
                            if 'password' in user_data:
                                user.password = base64.b64decode(user_data['password'].encode()).decode()
                            
                            user.save()
                            
                            # Add permissions and groups
                            if 'permissions' in user_data:
                                user.user_permissions.set(user_data['permissions'])
                            if 'groups' in user_data:
                                user.groups.set(user_data['groups'])
                            
                            success_count += 1
                            
                        except Exception as e:
                            error_count += 1
                            continue
                    
                    self.message_user(
                        request,
                        f"Successfully imported {success_count} users. {error_count} failed.",
                        messages.SUCCESS if error_count == 0 else messages.WARNING
                    )
                    return None
                    
                except json.JSONDecodeError:
                    self.message_user(
                        request,
                        "Invalid JSON file format",
                        messages.ERROR
                    )
                    return None
                
        else:
            form = ImportUsersForm()
        
        context = {
            'title': "Import Users",
            'form': form,
            'opts': self.model._meta,
            'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
        }
        return render(request, 'admin/import_users.html', context)
    import_users.short_description = "Import users from file"


"""
App and Investment Management
"""
@admin.register(AppListing)
class AppListingAdmin(admin.ModelAdmin):
    list_display = ('name', 'developer', 'listing_type', 'status', 'created_at', 'is_trending', 'view_count')
    list_filter = ('status', 'listing_type', 'created_at', 'deployment_type')
    search_fields = ('name', 'description', 'developer__username', 'suggested_by__username')
    readonly_fields = ('upvote_count', 'like_count', 'is_trending')
    actions = ['manage_engagement_metrics']

    def get_fieldsets(self, request, obj=None):
        fieldsets = [
            ('Basic Information', {
                'fields': ('name', 'description', 'ai_features', 'category', 'demo_video')
            }),
            ('Status', {
                'fields': ('status', 'listing_type', 'development_stage')
            }),
        ]
        
        if obj and obj.listing_type == AppListing.ListingType.COMMUNITY:
            fieldsets.extend([
                ('Community Information', {
                    'fields': ('suggested_by', 'suggestion_date', 'upvote_count', 'like_count', 'is_trending')
                }),
            ])
        elif obj and obj.listing_type == AppListing.ListingType.NOMINATED:
            fieldsets.extend([
                ('Nomination Information', {
                    'fields': ('nominated_by', 'nomination_date', 'nomination_details', 
                             'nomination_budget_breakdown', 'nomination_timeline')
                }),
            ])
        elif obj and obj.listing_type == AppListing.ListingType.FOR_SALE:
            fieldsets.extend([
                ('Sales Information', {
                    'fields': ('sale_price', 'sale_includes_source_code', 'sale_includes_assets',
                             'sale_includes_support', 'support_duration_months')
                }),
                ('App Metrics', {
                    'fields': ('monthly_revenue', 'monthly_users', 'tech_stack', 'deployment_type')
                }),
            ])
        elif obj and obj.listing_type != AppListing.ListingType.COMMUNITY:
            fieldsets.extend([
                ('Funding Details', {
                    'fields': ('funding_goal', 'currency', 'available_percentage',
                              'min_investment_percentage', 'price_per_percentage',
                              'equity_percentage', 'funding_round', 'round_number',
                              'lock_in_period', 'funding_end_date')
                }),
            ])
        
        return fieldsets

    def manage_engagement_metrics(self, request, queryset):
        if 'apply' in request.POST:
            form = AppEngagementForm(request.POST)
            if form.is_valid():
                add_views = form.cleaned_data.get('add_views', 0)
                add_likes = form.cleaned_data.get('add_likes', 0)
                add_upvotes = form.cleaned_data.get('add_upvotes', 0)
                add_comments = form.cleaned_data.get('add_comments', 0)
                engagement_note = form.cleaned_data['engagement_note']

                for app in queryset:
                    # Update view count
                    if add_views:
                        app.view_count += add_views
                        app.save(update_fields=['view_count'])

                    # Add system likes
                    if add_likes:
                        app.system_like_count += add_likes
                        app.save(update_fields=['system_like_count'])

                    # Add system upvotes
                    if add_upvotes:
                        app.system_upvote_count += add_upvotes
                        app.save(update_fields=['system_upvote_count'])

                    # Add system comments
                    if add_comments:
                        for i in range(add_comments):
                            AppComment.objects.create(
                                app=app,
                                user=request.user,
                                content=f"This is a promising initiative! #{i+1}",
                                created_at=timezone.now(),
                                is_system_generated=True
                            )
                        app.system_comment_count = (app.system_comment_count or 0) + add_comments
                        app.save(update_fields=['system_comment_count'])

                    # Log the engagement adjustment
                    EngagementAdjustmentLog.objects.create(
                        app=app,
                        admin=request.user,
                        views_added=add_views,
                        likes_added=add_likes,
                        upvotes_added=add_upvotes,
                        comments_added=add_comments,
                        note=engagement_note
                    )

                self.message_user(request, f"Successfully updated engagement metrics for {len(queryset)} apps")
                return None

        else:
            form = AppEngagementForm()

        return render(
            request,
            'admin/manage_engagement_metrics.html',
            {'apps': queryset, 'form': form, 'title': 'Manage Engagement Metrics'}
        )

    manage_engagement_metrics.short_description = "Manage engagement metrics"


@admin.register(Investment)
class InvestmentAdmin(admin.ModelAdmin):
    list_display = ('investor', 'app', 'percentage_bought', 'amount_paid', 'created_at')
    list_filter = ('created_at', 'app')
    search_fields = ('investor__username', 'app__name')
    date_hierarchy = 'created_at'


@admin.register(ShareOwnership)
class ShareOwnershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'app', 'percentage_owned', 'current_value')
    list_filter = ('app',)
    search_fields = ('user__username', 'app__name')


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        'support_reference', 'user', 'app', 'amount', 'status',
        'webhook_status', 'payment_gateway', 'card_info', 'created_at'
    )
    list_filter = (
        'status', 'webhook_status', 'payment_gateway',
        'webhook_received', 'currency', 'created_at'
    )
    search_fields = (
        'user__username', 'app__name', 'gateway_reference',
        'gateway_transaction_id', 'authorization_code',
        'support_reference', 'card_last4'
    )
    readonly_fields = (
        'created_at', 'updated_at', 'completed_at',
        'webhook_received_at', 'last_webhook_attempt',
        'webhook_attempts', 'retry_count', 'last_retry_at',
        'support_reference'
    )
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'support_reference', 'user', 'app', 'amount', 'currency',
                'transaction_type', 'status'
            )
        }),
        ('Payment Gateway Details', {
            'fields': (
                'payment_gateway', 'gateway_reference',
                'gateway_transaction_id', 'authorization_code',
                'card_type', 'card_last4', 'gateway_response'
            )
        }),
        ('Webhook Monitoring', {
            'fields': (
                'webhook_status', 'webhook_received',
                'webhook_received_at', 'webhook_attempts',
                'last_webhook_attempt', 'webhook_logs'
            ),
            'classes': ('collapse',)
        }),
        ('Error Tracking', {
            'fields': (
                'error_message', 'error_code', 'retry_count',
                'last_retry_at'
            ),
            'classes': ('collapse',)
        }),
        ('Debug Information', {
            'fields': (
                'ip_address', 'user_agent', 'debug_info'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'completed_at'),
            'classes': ('collapse',)
        })
    )

    def card_info(self, obj):
        if obj.card_type and obj.card_last4:
            return f"{obj.card_type} (*{obj.card_last4})"
        return "-"
    card_info.short_description = "Card Info"

    def has_add_permission(self, request):
        return False  # Prevent manual creation of transactions

    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing an existing object
            return self.readonly_fields + ('user', 'app', 'amount', 'currency', 'transaction_type')
        return self.readonly_fields

    actions = ['retry_failed_webhooks', 'mark_webhook_as_received']

    def retry_failed_webhooks(self, request, queryset):
        from core.tasks import retry_webhook_delivery
        count = 0
        for transaction in queryset.filter(webhook_status__in=['FAILED', 'RETRYING']):
            retry_webhook_delivery.delay(transaction.id)
            count += 1
        self.message_user(request, f"Scheduled {count} webhook retries")
    retry_failed_webhooks.short_description = "Retry failed webhooks"

    def mark_webhook_as_received(self, request, queryset):
        updated = queryset.update(
            webhook_received=True,
            webhook_status='RECEIVED',
            webhook_received_at=timezone.now()
        )
        self.message_user(request, f"Marked {updated} transactions as received")


"""
Security and API Monitoring
"""
@admin.register(SecurityAuditLog)
class SecurityAuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action', 'status', 'ip_address')
    list_filter = ('action', 'status', 'timestamp')
    search_fields = ('user__username', 'action', 'ip_address')
    readonly_fields = ('timestamp',)
    ordering = ('-timestamp',)

    def has_add_permission(self, request):
        return False  # Prevent manual creation of audit logs

    def has_change_permission(self, request, obj=None):
        return False  # Prevent editing of audit logs 


@admin.register(APIRequest)
class APIRequestAdmin(admin.ModelAdmin):
    list_display = ('method', 'endpoint', 'user', 'status_code', 'response_time', 'timestamp')
    list_filter = ('method', 'status_code', 'timestamp')
    search_fields = ('endpoint', 'user__username', 'ip_address')
    readonly_fields = ('timestamp',)
    ordering = ('-timestamp',)


@admin.register(APIError)
class APIErrorAdmin(admin.ModelAdmin):
    list_display = ('error_type', 'request', 'timestamp')
    list_filter = ('error_type', 'timestamp')
    search_fields = ('error_type', 'error_message', 'request__endpoint')
    readonly_fields = ('timestamp',)
    ordering = ('-timestamp',)


"""
Blog Management
"""
@admin.register(BlogCategory)
class BlogCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'post_count', 'created_at')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('name',)

    def post_count(self, obj):
        return obj.blog_set.count()
    post_count.short_description = 'Number of Posts'


@admin.register(Blog)
class BlogAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'category', 'status', 'is_ai_generated', 'view_count', 'published_at')
    list_filter = ('status', 'is_ai_generated', 'category', 'created_at', 'published_at')
    search_fields = ('title', 'content', 'meta_keywords')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('view_count', 'read_time', 'created_at', 'updated_at', 'published_at')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'slug', 'author', 'category', 'content', 'featured_image', 'status')
        }),
        ('AI Generation', {
            'fields': ('is_ai_generated', 'source_url', 'target_word_count'),
            'classes': ('collapse',)
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description', 'meta_keywords'),
            'classes': ('collapse',)
        }),
        ('Social Media', {
            'fields': ('social_title', 'social_description'),
            'classes': ('collapse',)
        }),
        ('Analytics', {
            'fields': ('view_count', 'read_time'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'published_at'),
            'classes': ('collapse',)
        }),
    )

    def view_on_site(self, obj):
        return reverse('core:blog_detail', kwargs={'slug': obj.slug})

    def save_model(self, request, obj, form, change):
        if not change:  # If creating new object
            obj.author = request.user
        super().save_model(request, obj, form, change)


"""
Revenue and Distribution Management
"""
@admin.register(Revenue)
class RevenueAdmin(admin.ModelAdmin):
    list_display = ('app', 'amount', 'currency', 'source', 'is_distributed', 'created_at')
    list_filter = ('currency', 'source', 'is_distributed', 'created_at')
    search_fields = ('app__name', 'description')
    ordering = ('-created_at',)


@admin.register(Distribution)
class DistributionAdmin(admin.ModelAdmin):
    list_display = ('revenue', 'recipient', 'amount', 'status', 'distributed_at')
    list_filter = ('status', 'distributed_at')
    search_fields = ('recipient__username', 'revenue__app__name')
    ordering = ('-distributed_at',)


"""
AI and Analytics Management
"""
@admin.register(AIAssessment)
class AIAssessmentAdmin(admin.ModelAdmin):
    list_display = ['app', 'overall_score', 'innovation_score', 'created_at']
    list_filter = ['created_at']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(PitchDeck)
class PitchDeckAdmin(admin.ModelAdmin):
    list_display = ('app', 'created_at', 'updated_at')
    search_fields = ('app__name', 'problem_statement', 'solution_overview')
    ordering = ('-created_at',)


@admin.register(AppInsight)
class AppInsightAdmin(admin.ModelAdmin):
    list_display = ('app', 'insight_type', 'value', 'confidence', 'created_at')
    list_filter = ('insight_type', 'created_at')
    search_fields = ('app__name',)
    ordering = ('-created_at',)


"""
Share and Funding Management
"""
@admin.register(ShareTransfer)
class ShareTransferAdmin(admin.ModelAdmin):
    list_display = ('app', 'seller', 'buyer', 'percentage_amount', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('app__name', 'seller__username', 'buyer__username')
    ordering = ('-created_at',)


@admin.register(FundingRound)
class FundingRoundAdmin(admin.ModelAdmin):
    list_display = ('app', 'round_type', 'funding_goal', 'status', 'created_at')
    list_filter = ('round_type', 'status', 'created_at')
    search_fields = ('app__name',)
    ordering = ('-created_at',)


@admin.register(EscrowTransaction)
class EscrowTransactionAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'app_link', 'investor_link', 'transaction_type', 'amount',
        'currency', 'status', 'dispute_status', 'created_at', 'completed_at'
    ]
    list_filter = [
        'transaction_type', 'status', 'dispute_status', 'currency',
        'payment_gateway', 'created_at'
    ]
    search_fields = [
        'app__name', 'investor__email', 'gateway_reference',
        'dispute_reason', 'refund_reason'
    ]
    readonly_fields = [
        'created_at', 'completed_at', 'original_transaction',
        'escrow_summary', 'milestone_info'
    ]
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'app', 'investor', 'transaction_type', 'amount', 'currency',
                'payment_gateway', 'gateway_reference', 'status'
            )
        }),
        ('Milestone Information', {
            'fields': ('milestone', 'release_percentage', 'milestone_info'),
            'classes': ('collapse',)
        }),
        ('Dispute Information', {
            'fields': (
                'dispute_status', 'dispute_reason', 'dispute_resolution_notes',
                'dispute_resolved_by'
            ),
            'classes': ('collapse',)
        }),
        ('Refund Information', {
            'fields': ('refund_reason', 'original_transaction'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'completed_at')
        }),
        ('Escrow Summary', {
            'fields': ('escrow_summary',),
            'classes': ('collapse',)
        })
    )
    
    def app_link(self, obj):
        url = reverse('admin:core_applisting_change', args=[obj.app.id])
        return format_html('<a href="{}">{}</a>', url, obj.app.name)
    app_link.short_description = 'App'
    
    def investor_link(self, obj):
        url = reverse('admin:core_user_change', args=[obj.investor.id])
        return format_html('<a href="{}">{}</a>', url, obj.investor.email)
    investor_link.short_description = 'Investor'
    
    def escrow_summary(self, obj):
        summary = EscrowService.get_escrow_summary(obj.app)
        return format_html(
            '<div style="margin: 10px 0;">'
            '<strong>Total Deposits:</strong> {}<br>'
            '<strong>Total Releases:</strong> {}<br>'
            '<strong>Total Refunds:</strong> {}<br>'
            '<strong>Funds in Dispute:</strong> {}<br>'
            '<strong>Available Balance:</strong> {}'
            '</div>',
            summary['total_deposits'],
            summary['total_releases'],
            summary['total_refunds'],
            summary['funds_in_dispute'],
            summary['available_balance']
        )
    escrow_summary.short_description = 'Escrow Summary'
    
    def milestone_info(self, obj):
        if not obj.milestone:
            return "No milestone associated"
            
        deliverables = obj.milestone.get_deliverables_status()
        return format_html(
            '<div style="margin: 10px 0;">'
            '<strong>Title:</strong> {}<br>'
            '<strong>Status:</strong> {}<br>'
            '<strong>Progress:</strong> {}%<br>'
            '<strong>Deliverables:</strong> {} of {} completed ({}%)'
            '</div>',
            obj.milestone.title,
            obj.milestone.get_status_display(),
            obj.milestone.progress,
            deliverables['completed'],
            deliverables['total'],
            deliverables['percentage']
        )
    milestone_info.short_description = 'Milestone Details'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'app', 'investor', 'milestone', 'dispute_resolved_by',
            'original_transaction'
        )
    
    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of completed transactions
        # if obj and obj.status == 'COMPLETED':
        #     return False
        # return super().has_delete_permission(request, obj)
        # Allow deletion of all transactions
        return True
    
    class Media:
        css = {
            'all': ('admin/css/escrow.css',)
        }
        js = ('admin/js/escrow.js',)


"""
Notification System Management
"""
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'type', 'title', 'is_read', 'created_at')
    list_filter = ('type', 'is_read', 'created_at')
    search_fields = ('user__username', 'title', 'message')
    ordering = ('-created_at',)


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'is_active', 'created_at')
    list_filter = ('type', 'is_active')
    search_fields = ('name', 'title_template', 'message_template')
    ordering = ('name',)


"""
Additional Notification Components
"""
# Register notification-related models with default admin interface
admin.site.register(NotificationPreference)
admin.site.register(NotificationGroup)
admin.site.register(NotificationGroupMembership)
admin.site.register(NotificationAnalytics)
admin.site.register(NotificationChannel)
admin.site.register(UserNotificationChannel)


"""
Legal Document Management
"""
@admin.register(LegalDocument)
class LegalDocumentAdmin(admin.ModelAdmin):
    list_display = ('document_type', 'version', 'effective_date', 'is_active', 'created_at', 'acceptance_count', 'actions_buttons')
    list_filter = ('document_type', 'is_active', 'effective_date')
    search_fields = ('document_type', 'version', 'content')
    readonly_fields = ('created_at',)
    ordering = ('-effective_date',)
    
    def acceptance_count(self, obj):
        return UserAgreement.objects.filter(document=obj).count()
    acceptance_count.short_description = 'Acceptances'
    
    def actions_buttons(self, obj):
        buttons = []
        
        # View button
        buttons.append(
            f'<a class="button" href="{reverse("admin:core_legaldocument_change", args=[obj.pk])}">'
            f'View</a>'
        )
        
        # Create New Version button
        buttons.append(
            f'<a class="button" href="{reverse("admin:core_legaldocument_add")}?clone={obj.pk}">'
            f'New Version</a>'
        )
        
        # Notify Users button (only for active documents)
        if obj.is_active:
            buttons.append(
                f'<a class="button" href="{reverse("core:notify_legal_update", args=[obj.pk])}">'
                f'Notify Users</a>'
            )
        
        return format_html('&nbsp;'.join(buttons))
    actions_buttons.short_description = 'Actions'
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if request.GET.get('clone'):
            try:
                clone_id = int(request.GET['clone'])
                clone_obj = LegalDocument.objects.get(id=clone_id)
                form.base_fields['document_type'].initial = clone_obj.document_type
                form.base_fields['content'].initial = clone_obj.content
                # Auto-increment version number
                current_version = float(clone_obj.version)
                form.base_fields['version'].initial = f"{current_version + 0.1:.1f}"
                form.base_fields['effective_date'].initial = timezone.now()
            except (ValueError, LegalDocument.DoesNotExist):
                pass
        return form
    
    def save_model(self, request, obj, form, change):
        if obj.is_active:
            # Deactivate other versions of the same document type
            LegalDocument.objects.filter(
                document_type=obj.document_type,
                is_active=True
            ).exclude(pk=obj.pk).update(is_active=False)
        super().save_model(request, obj, form, change)

@admin.register(UserAgreement)
class UserAgreementAdmin(admin.ModelAdmin):
    list_display = ('user', 'document', 'accepted_at', 'ip_address')
    list_filter = ('document__document_type', 'accepted_at')
    search_fields = ('user__email', 'document__document_type')
    ordering = ('-accepted_at',)
    readonly_fields = ('user', 'document', 'accepted_at', 'ip_address', 'user_agent') 

@admin.register(ProjectMilestone)
class ProjectMilestoneAdmin(admin.ModelAdmin):
    list_display = ('title', 'app', 'status', 'target_date', 'progress', 'release_percentage')
    list_filter = ('status', 'target_date')
    search_fields = ('title', 'description', 'app__name')
    raw_id_fields = ('app',)
    readonly_fields = ('verified_by', 'verified_at', 'verification_requested_at') 

@admin.register(CommunityVote)
class CommunityVoteAdmin(admin.ModelAdmin):
    list_display = ('app', 'user', 'vote_type', 'created_at')
    list_filter = ('vote_type', 'created_at')
    search_fields = ('app__name', 'user__username')
    date_hierarchy = 'created_at' 

"""
Subscription Management
"""
@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'tier', 'price', 'is_active', 'updated_at')
    list_filter = ('tier', 'is_active')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Plan Details', {
            'fields': ('tier', 'name', 'price', 'description', 'is_active')
        }),
        ('Features', {
            'fields': ('features',),
            'description': 'Enter features as a list, one per line'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def save_model(self, request, obj, form, change):
        # Convert features from string to list if needed
        if isinstance(obj.features, str):
            obj.features = [f.strip() for f in obj.features.split('\n') if f.strip()]
        super().save_model(request, obj, form, change)

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'tier', 'is_active', 'start_date', 'end_date', 'auto_renew')
    list_filter = ('tier', 'is_active', 'auto_renew')
    search_fields = ('user__email', 'user__username')
    readonly_fields = ('start_date',)
    fieldsets = (
        ('Subscription Info', {
            'fields': ('user', 'tier', 'is_active', 'auto_renew')
        }),
        ('Dates', {
            'fields': ('start_date', 'end_date')
        }),
        ('Payment Info', {
            'fields': ('last_payment_date', 'next_payment_date', 'payment_method'),
            'classes': ('collapse',)
        })
    )
    actions = ['cancel_subscriptions', 'enable_auto_renew', 'disable_auto_renew']

    def cancel_subscriptions(self, request, queryset):
        from .services.subscription import SubscriptionService
        count = 0
        for subscription in queryset:
            result = SubscriptionService.cancel_subscription(subscription.user)
            if result.get('success'):
                count += 1
        self.message_user(request, f'Successfully cancelled {count} subscriptions.')
    cancel_subscriptions.short_description = 'Cancel selected subscriptions'

    def enable_auto_renew(self, request, queryset):
        queryset.update(auto_renew=True)
        self.message_user(request, f'Enabled auto-renew for {queryset.count()} subscriptions.')
    enable_auto_renew.short_description = 'Enable auto-renew'

    def disable_auto_renew(self, request, queryset):
        queryset.update(auto_renew=False)
        self.message_user(request, f'Disabled auto-renew for {queryset.count()} subscriptions.')
    disable_auto_renew.short_description = 'Disable auto-renew'

@admin.register(SubscriptionFeatureUsage)
class SubscriptionFeatureUsageAdmin(admin.ModelAdmin):
    list_display = ('subscription', 'feature_name', 'daily_usage', 'monthly_usage', 'last_used')
    list_filter = ('feature_name', 'subscription__tier')
    search_fields = ('subscription__user__email', 'feature_name')
    readonly_fields = ('daily_reset_at', 'monthly_reset_at', 'last_used') 

@admin.register(PlatformFeeTransaction)
class PlatformFeeTransactionAdmin(admin.ModelAdmin):
    list_display = ['id', 'app', 'amount', 'status', 'created_at', 'completed_at', 'payment_gateway']
    list_filter = ['status', 'payment_gateway', 'created_at']
    search_fields = ['app__name', 'transaction_reference']
    readonly_fields = ['created_at', 'completed_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('app', 'amount', 'status', 'payment_gateway')
        }),
        ('Transaction Details', {
            'fields': ('transaction_reference', 'gateway_response')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'completed_at')
        }),
        ('Additional Information', {
            'fields': ('failure_reason',),
            'classes': ('collapse',)
        })
    )

    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing an existing object
            return self.readonly_fields + ('app', 'amount')
        return self.readonly_fields 

class AppEngagementForm(forms.Form):
    add_views = forms.IntegerField(required=False, min_value=0, help_text="Number of views to add")
    add_likes = forms.IntegerField(required=False, min_value=0, help_text="Number of likes to add")
    add_upvotes = forms.IntegerField(required=False, min_value=0, help_text="Number of upvotes to add")
    add_comments = forms.IntegerField(required=False, min_value=0, help_text="Number of comments to add")
    engagement_note = forms.CharField(widget=forms.Textarea, required=True, 
                                    help_text="Reason for adjusting engagement metrics")

class ImportUsersForm(forms.Form):
    import_file = forms.FileField(
        label='Select file to import',
        help_text='Supported formats: JSON'
    ) 