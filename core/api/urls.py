from django.urls import path, include
from rest_framework.routers import DefaultRouter
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.conf import settings
from .views.user import UserViewSet
from .views import (
    AppListingViewSet,
    InvestmentViewSet,
    AnalyticsViewSet,
    APIMonitoringViewSet,
    NotificationViewSet
)
from .views.auth import (
    register_api, login_api, verify_email,
    request_password_reset, reset_password,
    change_password, setup_2fa, verify_2fa_setup,
    disable_2fa, delete_account, signout_all_devices
)

# Schema view for API documentation
schema_view = get_schema_view(
    openapi.Info(
        title="Crowdfund AI API",
        default_version='v1',
        description="API for AI Crowdfunding Platform",
        terms_of_service="https://www.crowdfundai.com/terms/",
        contact=openapi.Contact(email="contact@crowdfundai.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=[],
)

# API Router
router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'apps', AppListingViewSet)
router.register(r'investments', InvestmentViewSet)
router.register(r'analytics', AnalyticsViewSet, basename='analytics')
router.register(r'monitoring', APIMonitoringViewSet, basename='api-monitoring')
router.register(r'notifications', NotificationViewSet, basename='notification')

urlpatterns = [
    # API documentation
    path('docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    
    # API endpoints
    path('', include(router.urls)),
    
    # Authentication endpoints
    path('auth/register/', register_api, name='register'),
    path('auth/login/', login_api, name='login'),
    path('auth/verify-email/<str:token>/', verify_email, name='verify-email'),
    path('auth/request-password-reset/', request_password_reset, name='request-password-reset'),
    path('auth/reset-password/<str:token>/', reset_password, name='reset-password'),
    path('auth/change-password/', change_password, name='change-password'),
    
    # 2FA endpoints
    path('auth/setup-2fa/', setup_2fa, name='setup-2fa'),
    path('auth/verify-2fa-setup/', verify_2fa_setup, name='verify-2fa-setup'),
    path('auth/disable-2fa/', disable_2fa, name='disable-2fa'),
    
    # Account management
    path('auth/delete-account/', delete_account, name='delete-account'),
    path('auth/signout-all-devices/', signout_all_devices, name='signout_all_devices'),
] 