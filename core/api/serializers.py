from rest_framework import serializers
from ..models import User, AppListing, Investment, Notification, APIRequest, APIError, EscrowTransaction, ProjectMilestone, Deliverable

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'date_joined', 'last_login']
        read_only_fields = ['date_joined', 'last_login']

class AppListingSerializer(serializers.ModelSerializer):
    developer = UserSerializer(read_only=True)
    current_funding = serializers.SerializerMethodField()
    funding_progress = serializers.SerializerMethodField()
    company_valuation = serializers.SerializerMethodField()
    retained_shares = serializers.SerializerMethodField()
    
    class Meta:
        model = AppListing
        fields = [
            'id', 'name', 'description', 'ai_features', 'developer',
            'funding_goal', 'price_per_percentage', 'available_percentage', 'equity_percentage',
            'current_funding', 'funding_progress',
            'company_valuation', 'retained_shares', 'status',
            'created_at', 'updated_at', 'github_url', 'demo_url'
        ]
    
    def get_current_funding(self, obj):
        return obj.get_funded_amount()
    
    def get_funding_progress(self, obj):
        return obj.get_funding_progress()
    
    def get_company_valuation(self, obj):
        return obj.get_company_valuation()
    
    def get_retained_shares(self, obj):
        return obj.get_retained_shares()

class InvestmentSerializer(serializers.ModelSerializer):
    app = AppListingSerializer(read_only=True)
    investor = UserSerializer(read_only=True)
    
    class Meta:
        model = Investment
        fields = [
            'id', 'app', 'investor', 'amount',
            'shares_bought', 'created_at'
        ]

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            'id', 'user', 'title', 'message',
            'notification_type', 'is_read',
            'created_at', 'data'
        ]
        read_only_fields = ['created_at']

    def to_representation(self, instance):
        """Customize the notification representation"""
        data = super().to_representation(instance)
        data['user'] = UserSerializer(instance.user).data
        return data

# Analytics Serializers
class AppAnalyticsSerializer(serializers.Serializer):
    total_investments = serializers.IntegerField()
    total_funding = serializers.DecimalField(max_digits=10, decimal_places=2)
    average_investment = serializers.DecimalField(max_digits=10, decimal_places=2)
    investor_count = serializers.IntegerField()
    funding_progress = serializers.FloatField()
    daily_investments = serializers.DictField(
        child=serializers.DecimalField(max_digits=10, decimal_places=2)
    )

class InvestmentAnalyticsSerializer(serializers.Serializer):
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    investment_count = serializers.IntegerField()
    apps_invested = serializers.IntegerField()
    average_investment = serializers.DecimalField(max_digits=10, decimal_places=2)
    investment_history = serializers.DictField(
        child=serializers.DecimalField(max_digits=10, decimal_places=2)
    )

class PlatformAnalyticsSerializer(serializers.Serializer):
    total_apps = serializers.IntegerField()
    total_investments = serializers.IntegerField()
    total_funding = serializers.DecimalField(max_digits=10, decimal_places=2)
    active_users = serializers.IntegerField()
    recent_activity = serializers.DictField(
        child=serializers.IntegerField()
    )
    growth_metrics = serializers.DictField(
        child=serializers.FloatField()
    )

class APIRequestSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = APIRequest
        fields = [
            'id', 'user', 'endpoint', 'method',
            'response_time', 'status_code', 'timestamp',
            'ip_address'
        ]

class APIErrorSerializer(serializers.ModelSerializer):
    request = APIRequestSerializer(read_only=True)
    
    class Meta:
        model = APIError
        fields = [
            'id', 'request', 'error_type',
            'error_message', 'stack_trace', 'timestamp'
        ]

class DeliverableSerializer(serializers.ModelSerializer):
    class Meta:
        model = Deliverable
        fields = ['id', 'title', 'status', 'due_date', 'created_at']

class MilestoneSerializer(serializers.ModelSerializer):
    deliverables = DeliverableSerializer(many=True, read_only=True)
    
    class Meta:
        model = ProjectMilestone
        fields = [
            'id', 'title', 'status', 'progress', 'target_date',
            'completion_date', 'release_percentage', 'deliverables'
        ]

class EscrowTransactionSerializer(serializers.ModelSerializer):
    milestone = MilestoneSerializer(read_only=True)
    investor_email = serializers.EmailField(source='investor.email', read_only=True)
    app_name = serializers.CharField(source='app.name', read_only=True)
    
    class Meta:
        model = EscrowTransaction
        fields = [
            'id', 'app_name', 'investor_email', 'transaction_type',
            'amount', 'currency', 'status', 'payment_gateway',
            'gateway_reference', 'milestone', 'release_percentage',
            'dispute_status', 'dispute_reason', 'refund_reason',
            'created_at', 'completed_at'
        ]

class MilestonePerformanceSerializer(serializers.Serializer):
    milestone = MilestoneSerializer()
    total_released = serializers.DecimalField(max_digits=15, decimal_places=2)
    deliverables_status = serializers.DictField()

class DisputeAnalyticsSerializer(serializers.Serializer):
    total_disputes = serializers.IntegerField()
    pending_disputes = serializers.IntegerField()
    resolved_disputes = serializers.IntegerField()
    avg_resolution_time = serializers.DurationField()
    resolution_breakdown = serializers.DictField()

class MonthlyReportSerializer(serializers.Serializer):
    period = serializers.DictField()
    transaction_summary = serializers.DictField()
    milestone_summary = serializers.ListField(
        child=serializers.DictField()
    )
    dispute_summary = serializers.DictField()
    ending_balance = serializers.DecimalField(max_digits=15, decimal_places=2) 