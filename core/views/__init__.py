from .main import home, investor_dashboard
from .auth import register, profile, login_view
from .apps import app_list, app_create, app_detail, app_edit, app_insights_view, ai_assessment
from .investments import invest, portfolio
from .payments import create_payment_intent
from .ads import ad_click, ad_create, ad_list, ad_review, verify_ad_payment, ad_edit, ad_delete
from .admin import (
    admin_dashboard, pending_apps, review_app,
    manage_users, user_details, admin_investments,
    admin_subscriptions, admin_create_plan, admin_edit_plan,
    admin_delete_plan, admin_edit_subscription, admin_cancel_subscription,
    admin_manage_metrics, admin_view_analytics,
    project_requests, project_request_detail
)
from .transactions import transaction_history, investment_analytics
from .notifications import (
    notification_list,
    mark_as_read,
    mark_all_as_read,
    get_unread_count,
    notification_preferences,
    test_notification,
    test_all_notifications,
    manage_templates,
    template_detail,
    recent_notifications
)
from .analytics import (
    analytics_dashboard,
    investment_analytics,
    app_analytics
)
from .search import search_apps, search_suggestions
from .moderation import (
    moderation_dashboard,
    report_list,
    report_detail,
    report_content,
    moderation_log
)
from .reports import (
    investment_report,
    platform_stats_report
)
from .monitoring import MonitoringDashboardView
from .health import health_dashboard, health_check_api
from .backup import backup_dashboard, create_backup, restore_backup
from .rules import (
    rules_dashboard,
    edit_rule,
    delete_rule,
    test_rule
)
from .security import (
    security_dashboard,
    security_logs,
    security_settings
)
from .ai_views import (
    ai_insights,
    app_insights,
    risk_analysis,
    app_valuation,
    investment_recommendations,
    market_trends,
    growth_potential
)
from .pitch_deck import pitch_deck_create, pitch_deck_view, pitch_deck_edit
from . import legal
from .project import (
    project_dashboard,
    milestone_list,
    milestone_detail,
    update_list,
    manage_tags,
    create_tag,
    milestone_samples
)
from .escrow import *
from .release import release_list, release_detail, create_release, approve_release, process_release
from .certificates import (
    certificate_list,
    certificate_detail,
    download_certificate,
    verify_certificate,
    revoke_certificate
)
from . import payments
from . import developer
from . import auth
    
# Import other views if needed
from .transfers import *
    
__all__ = [
    'home', 'investor_dashboard',
    'register', 'profile', 'login_view',
    'app_list', 'app_create', 'app_detail', 'app_edit',
    'app_insights_view', 'ai_assessment',
    'invest', 'portfolio',
    'stripe_webhook', 'create_payment_intent',
    'ad_click', 'ad_create', 'ad_list', 'ad_review', 'verify_ad_payment', 'ad_edit', 'ad_delete',
    'admin_dashboard', 'pending_apps', 'review_app',
    'manage_users', 'user_details', 'admin_investments',
    'admin_subscriptions', 'admin_create_plan', 'admin_edit_plan',
    'admin_delete_plan', 'admin_edit_subscription', 'admin_cancel_subscription',
    'admin_manage_metrics', 'admin_view_analytics',
    'project_requests', 'project_request_detail',
    'transaction_history', 'investment_analytics',
    'notification_list', 'mark_as_read', 'mark_all_as_read',
    'get_unread_count', 'notification_preferences',
    'test_notification', 'test_all_notifications',
    'manage_templates', 'template_detail', 'recent_notifications',
    'search_apps', 'search_suggestions',
    'moderation_dashboard', 'report_list', 'report_detail', 'report_content', 'moderation_log',
    'investment_report', 'platform_stats_report',
    'MonitoringDashboardView',
    'health_dashboard', 'health_check_api',
    'backup_dashboard', 'create_backup', 'restore_backup',
    'rules_dashboard', 'edit_rule', 'delete_rule', 'test_rule',
    'security_dashboard', 'security_logs', 'security_settings',
    'ai_insights',
    'app_insights',
    'risk_analysis',
    'app_valuation',
    'investment_recommendations',
    'market_trends',
    'growth_potential',
    'pitch_deck_create', 'pitch_deck_view', 'pitch_deck_edit',
    'LoginView',
    'LogoutView',
    'RegisterView',
    'PasswordResetView',
    'PasswordResetConfirmView',
    'milestone_samples',
    'release_list', 'release_detail', 'create_release', 'approve_release', 'process_release',
    'certificate_list',
    'certificate_detail',
    'download_certificate',
    'verify_certificate',
    'revoke_certificate',
    'payments',
    'developer',
    'auth'
] 