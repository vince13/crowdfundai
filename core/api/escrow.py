from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from datetime import datetime
from ..models import AppListing, EscrowTransaction
from ..services.escrow import EscrowService
from ..services.reporting import EscrowReportingService
from .serializers import (
    EscrowTransactionSerializer,
    MilestonePerformanceSerializer,
    DisputeAnalyticsSerializer
)

class EscrowReportingViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]
    
    def get_app_listing(self, pk):
        """Helper method to get app listing and verify permissions."""
        app = get_object_or_404(AppListing, pk=pk)
        if not (self.request.user.is_staff or 
                app.developer == self.request.user or 
                app.investors.filter(id=self.request.user.id).exists()):
            raise PermissionDenied("You don't have permission to access this app's reports")
        return app
    
    @action(detail=True, methods=['get'])
    def transaction_history(self, request, pk=None):
        """Get transaction history for an app."""
        app = self.get_app_listing(pk)
        
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d')
            
        transactions = EscrowReportingService.get_transaction_history(
            app, start_date, end_date
        )
        
        serializer = EscrowTransactionSerializer(transactions, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def milestone_performance(self, request, pk=None):
        """Get milestone performance metrics."""
        app = self.get_app_listing(pk)
        
        performance = EscrowReportingService.get_milestone_performance(app)
        serializer = MilestonePerformanceSerializer(performance, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def dispute_analytics(self, request, pk=None):
        """Get dispute statistics and trends."""
        app = self.get_app_listing(pk)
        
        analytics = EscrowReportingService.get_dispute_analytics(app)
        serializer = DisputeAnalyticsSerializer(analytics)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def monthly_report(self, request, pk=None):
        """Generate monthly escrow activity report."""
        app = self.get_app_listing(pk)
        
        year = int(request.query_params.get('year', timezone.now().year))
        month = int(request.query_params.get('month', timezone.now().month))
        
        report = EscrowReportingService.generate_monthly_report(app, year, month)
        return Response(report)
    
    @action(detail=True, methods=['get'])
    def export_transactions(self, request, pk=None):
        """Export transaction history to CSV."""
        app = self.get_app_listing(pk)
        
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d')
            
        df = EscrowReportingService.export_transaction_history(
            app, start_date, end_date
        )
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{app.name}_transactions.csv"'
        df.to_csv(response, index=False)
        return response 