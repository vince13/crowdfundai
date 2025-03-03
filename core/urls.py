from django.urls import path, include, reverse_lazy
from django.contrib.auth import views as auth_views
from . import views
from .views import transfers, ai_views, apps, pitch_deck, revenue, blog, legal, project, escrow, dispute, developer_escrow, contact, ads, notifications, admin as admin_views, support, investments, community
from .api import blog as blog_api
from rest_framework.routers import DefaultRouter
from .api.insights import AppInsightViewSet
from .views.monitoring import (
    MonitoringDashboardView,
    UpdateThresholdsView,
    ExportMetricsView
)
from .api.views import monitoring as monitoring_api
from .api.views import auth as auth_api
from .api.escrow import EscrowReportingViewSet
from .views.developer import payment_settings
from .views import auth as custom_auth_views
from .views import subscription
from .api.views import views as api_views
from .views.auth import CustomPasswordResetView

app_name = 'core'

router = DefaultRouter()
router.register(r'insights', AppInsightViewSet, basename='app-insights')
router.register(r'escrow-reports', EscrowReportingViewSet, basename='escrow-reports')

urlpatterns = [
    # Home and Dashboard
    path('', views.home, name='home'),
    path('hire-us/', apps.hire_us, name='hire_us'),
    path('dashboard/', views.investor_dashboard, name='dashboard'),
    path('developer/dashboard/', views.investor_dashboard, name='developer_dashboard'),
    
    # Authentication
    path('register/', views.register, name='register'),
    path('login/', 
         auth_views.LoginView.as_view(
             template_name='core/auth/login.html',
             next_page='core:dashboard'
         ), 
         name='login'),
    path('logout/', 
         auth_views.LogoutView.as_view(
             next_page='core:home'
         ), 
         name='logout'),
    path('profile/', views.profile, name='profile'),
    path('profile/<int:user_id>/', views.profile, name='profile'),
    
    # Password Reset URLs
    path('password/reset/', 
         CustomPasswordResetView.as_view(
             success_url=reverse_lazy('core:password_reset_done')
         ),
         name='password_reset'),
    path('password/reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='core/auth/password_reset_done.html'
         ),
         name='password_reset_done'),
    path('password/reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='core/auth/password_reset_confirm.html',
             success_url=reverse_lazy('core:password_reset_complete')
         ),
         name='password_reset_confirm'),
    path('password/reset/complete/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='core/auth/password_reset_complete.html'
         ),
         name='password_reset_complete'),
    
    path('password/change/', 
         auth_views.PasswordChangeView.as_view(
             template_name='core/auth/password_change.html',
             success_url='/password/change/done/'
         ), 
         name='password_change'),
    path('password/change/done/', 
         auth_views.PasswordChangeDoneView.as_view(
             template_name='core/auth/password_change_done.html'
         ), 
         name='password_change_done'),
    
    # App Listing URLs
    path('apps/for-sale/', apps.apps_for_sale, name='apps_for_sale'),
    path('apps/for-sale/create/', apps.app_for_sale_create, name='app_for_sale_create'),
    path('apps/', views.app_list, name='app_list'),
    path('apps/create/', views.app_create, name='app_create'),
    path('apps/<int:pk>/', views.app_detail, name='app_detail'),
    path('apps/<int:pk>/edit/', views.app_edit, name='app_edit'),
    path('apps/<int:pk>/shareholders/', apps.app_shareholders, name='app_shareholders'),
    path('apps/<int:pk>/shareholders/export/', apps.export_shareholders, name='export_shareholders'),
    path('apps/<int:pk>/pitch-deck-template/', apps.pitch_deck_template, name='pitch_deck_template'),
    path('apps/<int:pk>/contact-seller/', apps.contact_seller, name='contact_seller'),
    path('apps/<int:pk>/messages/', apps.app_messages, name='app_messages'),
    path('messages/<int:message_id>/mark-read/', apps.mark_message_read, name='mark_message_read'),
    path('messages/<int:message_id>/reply/', apps.reply_message, name='reply_message'),
    path('messages/<int:message_id>/archive/', apps.archive_message, name='archive_message'),
    path('messages/<int:message_id>/delete/', apps.delete_message, name='delete_message'),
    
    # Team Member URLs
    path('apps/<int:pk>/team/add/', apps.AppTeamMemberCreateView.as_view(), name='add_team_member'),
    path('apps/<int:pk>/team/<int:member_pk>/edit/', apps.AppTeamMemberUpdateView.as_view(), name='edit_team_member'),
    path('apps/<int:pk>/team/<int:member_pk>/delete/', apps.AppTeamMemberDeleteView.as_view(), name='delete_team_member'),
    
    # Community URLs
    path('community/suggest/', community.suggest_app, name='suggest_app'),
    path('community/leaderboard/', community.community_leaderboard, name='community_leaderboard'),
    path('apps/<int:pk>/vote/', community.vote_app, name='vote_app'),
    path('apps/<int:pk>/comments/', community.get_comments, name='get_comments'),
    path('apps/<int:pk>/comments/add/', community.add_comment, name='add_comment'),
    path('apps/<int:pk>/comments/<int:comment_id>/delete/', community.delete_comment, name='delete_comment'),
    path('apps/<int:pk>/comment-count/', community.get_comment_count, name='get_comment_count'),
    
    # Investment URLs
    path('apps/<int:app_id>/invest/', views.invest, name='invest'),
    path('portfolio/', views.portfolio, name='portfolio'),
    path('api/portfolio/stats/', views.investments.api_portfolio_stats, name='api_portfolio_stats'),
    
    # Payment URLs
    path('payments/', include([
        path('create-intent/', views.payments.create_payment_intent, name='create_payment_intent'),
        path('webhook/', views.payments.paystack_webhook, name='paystack_webhook'),
        path('verify/', views.payments.verify_payment, name='verify_payment'),
    ])),
    
    # Payment webhook URL
    path('webhooks/payment/', views.payments.payment_webhook, name='payment_webhook'),
    
    # Admin URLs - rename from 'admin/' to 'administration/'
    path('administration/dashboard/', admin_views.admin_dashboard, name='admin_dashboard'),
    path('administration/platform-fees/', admin_views.platform_fee_dashboard, name='platform_fee_dashboard'),
    path('administration/verify-payments/', admin_views.verify_payment_accounts, name='verify_payment_accounts'),
    path('administration/apps/pending/', admin_views.pending_apps, name='admin_pending_apps'),
    path('administration/apps/<int:pk>/review/', admin_views.review_app, name='admin_review_app'),
    path('administration/apps/<int:pk>/metrics/', admin_views.admin_manage_metrics, name='admin_manage_metrics'),
    path('administration/apps/<int:pk>/analytics/', admin_views.admin_view_analytics, name='admin_view_analytics'),
    path('administration/users/', admin_views.manage_users, name='admin_manage_users'),
    path('administration/users/<int:pk>/', admin_views.user_details, name='admin_user_details'),
    path('administration/investments/', admin_views.admin_investments, name='admin_investments'),
    
    # Subscription Management URLs
    path('administration/subscriptions/', admin_views.admin_subscriptions, name='admin_subscriptions'),
    path('administration/subscriptions/plans/create/', admin_views.admin_create_plan, name='admin_create_plan'),
    path('administration/subscriptions/plans/<int:plan_id>/edit/', admin_views.admin_edit_plan, name='admin_edit_plan'),
    path('administration/subscriptions/plans/<int:plan_id>/delete/', admin_views.admin_delete_plan, name='admin_delete_plan'),
    path('administration/subscriptions/<int:subscription_id>/edit/', admin_views.admin_edit_subscription, name='admin_edit_subscription'),
    path('administration/subscriptions/<int:subscription_id>/cancel/', admin_views.admin_cancel_subscription, name='admin_cancel_subscription'),
    path('administration/subscriptions/usage/', admin_views.subscription_usage_tracking, name='subscription_usage_tracking'),
    path('administration/subscriptions/analytics/', admin_views.subscription_analytics, name='subscription_analytics'),
    
    # Project Request Management
    path('administration/project-requests/', admin_views.project_requests, name='admin_project_requests'),
    path('administration/project-requests/<int:pk>/', admin_views.project_request_detail, name='admin_project_request_detail'),
    
    # Transaction & Analytics URLs
    path('transactions/', views.transactions.transaction_history, name='transaction_history'),
    path('transactions/<int:transaction_id>/', views.transactions.transaction_detail, name='transaction_detail'),
    path('analytics/', views.analytics_dashboard, name='analytics_dashboard'),
    path('analytics/investments/', views.investment_analytics, name='investment_analytics'),
    path('analytics/apps/<int:pk>/', views.app_analytics, name='app_analytics'),
    
    # Notification URLs
    path('notifications/', views.notifications.notification_list, name='notifications'),
    path('notifications/test/', views.notifications.test_notification, name='test_notification'),
    path('notifications/mark-read/<int:pk>/', views.notifications.mark_as_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.notifications.mark_all_as_read, name='mark_all_read'),
    path('notifications/unread-count/', views.notifications.get_unread_count, name='unread_count'),
    path('notifications/preferences/', views.notifications.notification_preferences, name='notification_preferences'),
    path('notifications/test-all/', views.notifications.test_all_notifications, name='test_all_notifications'),
    path('notifications/templates/', views.notifications.manage_templates, name='manage_templates'),
    path('notifications/templates/<int:pk>/', views.notifications.template_detail, name='template_detail'),
    path('notifications/recent/', views.notifications.recent_notifications, name='recent_notifications'),
    path('notifications/stream/', views.notifications.notification_stream, name='notification_stream'),
    path('notifications/delete/<int:pk>/', notifications.delete_notification, name='delete_notification'),
    path('notifications/delete-all/', notifications.delete_all_notifications, name='delete_all_notifications'),
    path('search/', views.search_apps, name='search_apps'),
    path('search/suggestions/', views.search_suggestions, name='search_suggestions'),
    path('administration/moderation/', views.moderation_dashboard, name='moderation_dashboard'),
    path('administration/moderation/reports/', views.report_list, name='moderation_report_list'),
    path('administration/moderation/reports/<int:pk>/', views.report_detail, name='moderation_report_detail'),
    path('administration/moderation/log/', views.moderation_log, name='moderation_log'),
    path('report-content/', views.report_content, name='report_content'),
    path('reports/investment/', views.investment_report, name='investment_report'),
    path('reports/platform-stats/', views.platform_stats_report, name='platform_stats_report'),
    path('administration/monitoring/', MonitoringDashboardView.as_view(), name='monitoring_dashboard'),
    path('administration/monitoring/update-thresholds/', UpdateThresholdsView.as_view(), name='update_thresholds'),
    path('administration/monitoring/export/', ExportMetricsView.as_view(), name='export_metrics'),
    path('api/monitoring/metrics/', monitoring_api.get_metrics, name='monitoring_metrics'),
    path('administration/health/', views.health_dashboard, name='health_dashboard'),
    path('api/health/status/', views.health_check_api, name='health_check_api'),
    # Backup Management
    path('administration/backup/', views.backup_dashboard, name='backup_dashboard'),
    path('administration/backup/create/', views.create_backup, name='create_backup'),
    path('administration/backup/restore/<str:backup_type>/<str:filename>/', 
         views.restore_backup, name='restore_backup'),
    # Rules Management
    path('administration/rules/', views.rules_dashboard, name='rules_dashboard'),
    path('administration/rules/<str:rule_type>/new/', views.edit_rule, name='new_rule'),
    path('administration/rules/<str:rule_type>/<int:rule_id>/edit/', views.edit_rule, name='edit_rule'),
    path('administration/rules/delete/<int:rule_id>/', views.delete_rule, name='delete_rule'),
    path('administration/rules/test/', views.test_rule, name='test_rule'),
    # Security Management
    path('administration/security/', views.security_dashboard, name='security_dashboard'),
    path('administration/security/logs/', views.security_logs, name='security_logs'),
    path('administration/security/settings/', views.security_settings, name='security_settings'),
    # Share Transfer URLs
    path('transfers/', transfers.share_transfer_list, name='share_transfer_list'),
    path('transfers/create/<int:app_id>/', transfers.create_transfer, name='create_transfer'),
    path('transfers/purchase/<int:transfer_id>/', transfers.purchase_transfer, name='purchase_transfer'),
    path('transfers/cancel/<int:transfer_id>/', transfers.cancel_transfer, name='cancel_transfer'),
    
    # Legal URLs
    path('terms/', legal.terms, name='terms'),
    path('privacy/', legal.privacy, name='privacy'),
    path('terms-of-service/', legal.terms_of_service, name='terms_of_service'),
    path('privacy-policy/', legal.privacy_policy, name='privacy_policy'),
    path('legal/accept-agreement/<int:document_id>/', legal.accept_agreement, name='accept_agreement'),
    path('legal/notify-update/', views.legal.notify_legal_update, name='notify_legal_update'),
    
    path('api/', include(router.urls)),
    # AI Insights URLs
    path('api/ai/', include([
        path('insights/<int:app_id>/', ai_views.ai_insights, name='ai_insights'),
        path('risk-analysis/<int:app_id>/', ai_views.risk_analysis, name='risk_analysis'),
        path('valuation/<int:app_id>/', ai_views.app_valuation, name='app_valuation'),
        path('recommendations/<int:app_id>/', ai_views.investment_recommendations, name='investment_recommendations'),
        path('market-trends/<int:app_id>/', ai_views.market_trends, name='market_trends'),
        path('growth-potential/<int:app_id>/', ai_views.growth_potential, name='growth_potential'),
    ])),
    path('apps/<int:pk>/insights/', apps.app_insights_view, name='app_insights'),
    path('apps/<int:pk>/ai-assessment/', apps.ai_assessment, name='ai_assessment'),
    # Pitch Deck URLs
    path('apps/<int:app_id>/pitch-deck/create/', pitch_deck.pitch_deck_create, name='pitch_deck_create'),
    path('apps/<int:app_id>/pitch-deck/view/', pitch_deck.pitch_deck_view, name='pitch_deck_view'),
    path('apps/<int:app_id>/pitch-deck/edit/', pitch_deck.pitch_deck_edit, name='pitch_deck_edit'),
    path('apps/<int:app_id>/pitch-deck/trigger-analysis/', pitch_deck.trigger_ai_analysis, name='trigger_ai_analysis'),
    
    # Revenue URLs
    path('revenue/', revenue.RevenueDashboardView.as_view(), name='revenue_dashboard'),
    path('revenue/<int:pk>/', revenue.RevenueDetailView.as_view(), name='revenue_detail'),
    path('revenue/record/<int:app_id>/', revenue.record_revenue_form, name='record_app_revenue'),
    path('revenue/record/<int:app_id>/submit/', revenue.record_app_revenue, name='submit_app_revenue'),
    path('revenue/<int:revenue_id>/verify/', revenue.verify_revenue, name='verify_revenue'),
    path('revenue/<int:pk>/process/', revenue.process_distributions, name='process_distributions'),
    path('revenue/retry-distribution/', revenue.retry_distribution, name='retry_distribution'),
    path('revenue/<int:pk>/export/', revenue.export_revenue_data, name='revenue_export'),
    # Blog URLs
    path('blog/', include([
        path('', blog.BlogListView.as_view(), name='blog_list'),
        path('create/', blog.BlogCreateView.as_view(), name='blog_create'),
        path('category/create/', blog.BlogCategoryCreateView.as_view(), name='blog_category_create'),
        path('<slug:slug>/', blog.BlogDetailView.as_view(), name='blog_detail'),
        path('<slug:slug>/edit/', blog.BlogUpdateView.as_view(), name='blog_edit'),
        path('<slug:slug>/delete/', blog.BlogDeleteView.as_view(), name='blog_delete'),
        path('<int:post_id>/increment-views/', blog.increment_blog_views, name='blog_increment_views'),
    ])),
    # Blog Category URLs
    path('blog/category/<slug:slug>/edit/', blog.BlogCategoryUpdateView.as_view(), name='blog_category_edit'),
    
    # Blog API endpoints
    path('api/blog/generate-content/', blog_api.generate_blog_content, name='blog_generate_content'),
    path('api/check-session/', custom_auth_views.check_session, name='check_session'),
    # Project Management
    path('apps/<int:pk>/project/', project.project_dashboard, name='project_dashboard'),
    path('apps/<int:pk>/milestones/', project.milestone_list, name='milestone_list'),
    path('apps/<int:pk>/milestones/<int:milestone_id>/', project.milestone_detail, name='milestone_detail'),
    path('apps/<int:pk>/milestones/<int:milestone_id>/request-verification/', 
         project.request_milestone_verification, name='request_milestone_verification'),
    path('apps/<int:pk>/milestones/<int:milestone_id>/verify/', 
         project.verify_milestone, name='verify_milestone'),
    path('apps/<int:pk>/milestones/<int:milestone_id>/update-progress/', project.update_milestone_progress, name='update_milestone_progress'),
    path('administration/escrow/releases/', project.manage_escrow_releases, name='manage_escrow_releases'),
    path('administration/escrow/releases/<int:release_id>/process/', 
         project.process_escrow_release, name='process_escrow_release'),
    path('apps/<int:pk>/updates/', project.update_list, name='update_list'),
    path('apps/<int:pk>/tags/', project.manage_tags, name='manage_tags'),
    path('tags/create/', project.create_tag, name='create_tag'),
    # Escrow Management URLs - Admin
    path('administration/escrow/', escrow.escrow_reports_list, name='escrow-reports-list'),
    path('administration/escrow/transactions/<int:app_id>/', escrow.transaction_history, name='escrow-reports-transaction-history'),
    path('administration/escrow/monthly-report/<int:app_id>/', escrow.monthly_report, name='escrow-reports-monthly-report'),

    # Investor Escrow URLs
    path('investor/escrow/', escrow.investor_escrow_reports, name='investor-escrow-reports'),

    # Developer Escrow URLs
    path('developer/escrow/', developer_escrow.escrow_balance, name='developer-escrow'),
    path('developer/escrow/history/', developer_escrow.transaction_history, name='developer-escrow-history'),
    path('developer/escrow/app/<int:app_id>/', developer_escrow.app_transactions, name='developer-app-transactions'),

    # Dispute Management URLs
    path('disputes/', views.dispute.dispute_list, name='dispute_list'),
    path('disputes/create/', views.dispute.create_dispute, name='create_dispute'),
    path('disputes/<int:dispute_id>/', views.dispute.dispute_detail, name='dispute_detail'),
    path('disputes/<int:dispute_id>/evidence/', views.dispute.upload_evidence, name='upload_evidence'),
    path('disputes/<int:dispute_id>/manage/', views.dispute.manage_dispute, name='manage_dispute'),
    path('disputes/evidence/<int:evidence_id>/delete/', views.dispute.delete_evidence, name='delete_evidence'),

    path('project/milestone-samples/', views.milestone_samples, name='milestone_samples'),

    # Release Management URLs
    path('releases/', views.release.release_list, name='release_list'),
    path('releases/create/', views.release.create_release, name='create_release'),
    path('releases/<int:release_id>/', views.release.release_detail, name='release_detail'),
    path('releases/<int:release_id>/approve/', views.release.approve_release, name='approve_release'),
    path('releases/<int:release_id>/process/', views.release.process_release, name='process_release'),
    path('releases/<int:release_id>/request-approval/', views.release.request_approval, name='request_approval'),

    # Certificate URLs
    path('certificates/', views.certificate_list, name='certificate_list'),
    path('certificates/<int:pk>/', views.certificate_detail, name='certificate_detail'),
    path('certificates/<int:pk>/download/', views.download_certificate, name='download_certificate'),
    path('certificates/<int:pk>/revoke/', views.revoke_certificate, name='revoke_certificate'),
    path('verify-certificate/<int:certificate_id>/<str:transaction_hash>/', 
         views.verify_certificate, name='verify_certificate'),

    # Developer Payment URLs
    path('developer/payment-setup/', payment_settings.payment_info_setup, name='payment_setup'),
    path('developer/payment-verify/', payment_settings.verify_payment_account, name='verify_payment_account'),
    path('developer/payment-update/', payment_settings.update_payment_info, name='update_payment_info'),

    # Contact URLs
    path('contact/', contact.contact, name='contact'),

    # Support URLs
    path('support/', support.support_home, name='support_home'),
    path('support/submit/', support.submit_ticket, name='submit_ticket'),
    path('support/faq/', support.faq, name='faq'),
    path('about/', support.about_us, name='about'),

    # Advertisement Management URLs - temporarily disabled
    # path('ads/create/', ads.ad_create, name='ad_create'),
    # path('ads/<int:pk>/', ads.ad_detail, name='ad_detail'),
    # path('ads/<int:pk>/edit/', ads.ad_edit, name='ad_edit'),
    # path('ads/<int:pk>/delete/', ads.ad_delete, name='ad_delete'),
    # path('ads/<int:pk>/verify-payment/', ads.verify_ad_payment, name='verify_ad_payment'),
    # path('ads/', ads.ad_list, name='ad_list'),
    # path('ads/<int:pk>/click/', ads.ad_click, name='ad_click'),
    # path('ads/<int:pk>/review/', ads.ad_review, name='ad_review'),

    # Test routes (staff only)
    path('apps/<int:app_id>/test-fee/', apps.test_fee_collection, name='test_fee_collection'),

    # Public API endpoints
    path('api/apps/<int:app_id>/available-percentage/', apps.get_available_percentage, name='get_available_percentage'),

    # Subscription URLs
    path('subscriptions/', subscription.subscription_plans, name='subscription_plans'),
    path('subscriptions/upgrade/', subscription.upgrade_subscription, name='upgrade_subscription'),
    path('subscriptions/cancel/', subscription.cancel_subscription, name='cancel_subscription'),
    path('subscriptions/payment/', subscription.payment_page, name='payment_page'),
    path('subscriptions/process-payment/', subscription.process_payment, name='process_payment'),
    path('subscriptions/verify-payment/', subscription.verify_payment, name='verify_payment'),
    path('subscriptions/status/', subscription.subscription_status, name='subscription_status'),
    
    # Paystack webhook
    path('subscriptions/webhook/paystack/', subscription.paystack_webhook, name='paystack_webhook'),

    # Admin URLs
    path('administration/dashboard/', admin_views.admin_dashboard, name='admin_dashboard'),
    path('administration/base-template/', admin_views.base_template_view, name='base_template'),

    # API endpoints
    path('api/apps/<int:pk>/like/', api_views.app_like_api, name='app_like_api'),
    path('api/apps/<int:pk>/upvote/', api_views.app_upvote_api, name='app_upvote_api'),

    # Email verification
    path('verify-email/<str:token>/', custom_auth_views.verify_email, name='verify_email'),

    # Comment URLs
    path('apps/<int:app_id>/comments/<int:comment_id>/delete/', 
         apps.delete_comment, 
         name='delete_comment'),
    path('apps/<int:app_id>/comments/<int:comment_id>/report/', 
         apps.report_comment, 
         name='report_comment'),
] 