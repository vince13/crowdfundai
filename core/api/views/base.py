from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from ..serializers import (
    UserSerializer,
    AppListingSerializer,
    InvestmentSerializer
)
from ...models import User, AppListing, Investment

class BaseViewSet(viewsets.ModelViewSet):
    """
    Base ViewSet providing common functionality
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

class UserViewSet(BaseViewSet):
    """
    API endpoint for user management
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    
    @swagger_auto_schema(
        operation_description="Get current user profile",
        responses={200: UserSerializer()}
    )
    @action(detail=False, methods=['get'])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

class AppListingViewSet(BaseViewSet):
    """
    API endpoint for app listings
    """
    queryset = AppListing.objects.all()
    serializer_class = AppListingSerializer
    
    @swagger_auto_schema(
        operation_description="Get featured apps",
        responses={200: AppListingSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def featured(self, request):
        featured_apps = self.get_queryset().filter(is_featured=True)
        serializer = self.get_serializer(featured_apps, many=True)
        return Response(serializer.data)

class InvestmentViewSet(BaseViewSet):
    """
    API endpoint for investments
    """
    queryset = Investment.objects.all()
    serializer_class = InvestmentSerializer
    
    def get_queryset(self):
        return self.queryset.filter(investor=self.request.user) 